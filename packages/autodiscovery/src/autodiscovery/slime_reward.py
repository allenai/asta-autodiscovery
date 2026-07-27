"""Surprisal-based scalar reward for online RL training (slime integration).

Exposes AutoDiscovery's Bayesian-surprise computation as a standalone reward:
a hypothesis string goes in, one experiment is planned and executed through the
usual group chat (programmer -> executor -> analyst -> reviewer), prior and
posterior beliefs are elicited, and the same ``get_self_value`` used by MCTS
turns the belief change / KL divergence into the scalar reward.

Two ways to consume it from a slime training run:

1. In-process (rollout workers import autodiscovery directly)::

       from autodiscovery.slime_reward import compute_reward
       reward = compute_reward("Taller plants produce more seeds.")

2. As a reward server (recommended: keeps the heavy execution environment out
   of the training job). Single dataset::

       python -m autodiscovery.slime_reward \
           --dataset_metadata /path/to/metadata.json --port 8000

   Multiple datasets, routed per-request by ``dataset_id`` (a JSON registry
   mapping id -> metadata.json path, or id -> {"dataset_metadata": ...,
   "dataset_metadata_type": ...})::

       python -m autodiscovery.slime_reward \
           --dataset_registry /path/to/registry.json --port 8000 --concurrency 8

   The server answers ``POST /reward {"hypothesis", "dataset_id", "request_id"}``
   and returns the scored result (the scalar is under ``reward``). ``request_id``
   is deduplicated so an HTTP retry never re-runs a multi-minute experiment.
   slime reaches it through ``slime/rollout/rm_hub/autodiscovery.py`` (posts to
   ``--rm-url http://host:8000/reward``); this repo no longer needs to be
   importable inside the slime training job.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import queue
import tempfile
import threading
from collections import OrderedDict
from dataclasses import dataclass, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from autodiscovery.beliefs import calculate_prior_and_posterior_beliefs
from autodiscovery.dataset import get_datasets_fpaths, get_load_dataset_experiment
from autodiscovery.mcts import MCTSNode
from autodiscovery.mcts_utils import (
    get_context_string,
    get_msgs_from_latest_query,
    get_query_from_experiment,
    get_self_value,
)
from autodiscovery.transitions import SpeakerSelector


class _ExperimentOnlySelector(SpeakerSelector):
    """Speaker selector that ends the chat after the reviewer.

    The engine's selector hands the reviewer's turn to the experiment_generator
    to propose the next experiments; for reward scoring the hypothesis comes
    from the RL policy, so the chat stops once the experiment is reviewed
    (allowing the usual single revision round).
    """

    def select_next_speaker(self, last_speaker, groupchat):
        if last_speaker.name == "experiment_reviewer":
            content = groupchat.messages[-1].get("content", "")
            try:
                response = json.loads(content)
            except json.JSONDecodeError:
                response = {"success": False, "feedback": "Error parsing reviewer response"}
            if not response.get("success", True) and self.experiment_revision_count < 1:
                self.experiment_revision_count += 1
                return groupchat.agent_by_name("experiment_reviser")
            self.experiment_revision_count = 0
            return None
        return super().select_next_speaker(last_speaker, groupchat)


@dataclass
class SurpriseRewardConfig:
    """Configuration for the surprisal reward scorer (defaults mirror easy.py)."""

    dataset_metadata: str
    dataset_metadata_type: str = "asta"
    work_dir: str | None = None
    log_dir: str | None = None
    # Models. Defaults are GCP-free (OpenAI): the provider is chosen purely by
    # model-name prefix, so any non-"gemini*" id routes through the plain
    # OpenAI() client and honors OPENAI_API_KEY / OPENAI_BASE_URL. Point
    # OPENAI_BASE_URL at a local vLLM and set these to the served model id for
    # a fully local, GCP-free reward path. (A "gemini*" id here re-enables
    # Vertex.)
    execution_model: str = "gpt-4o"
    belief_model: str = "gpt-4o-mini"
    vision_model: str = "gpt-4o"
    temperature: float = 1.0
    belief_temperature: float = 1.0
    reasoning_effort: str = "medium"
    belief_reasoning_effort: str = "low"
    # Beliefs / reward
    belief_mode: str = "boolean_cat"
    n_belief_samples: int = 5
    implicit_bayes_posterior: bool = False
    surprisal_width: float = 0.2
    evidence_weight: float = 2.0
    kl_scale: float = 5.0
    reward_mode: str = "belief"
    use_binary_reward: bool = False
    failed_reward: float = 0.0
    # Execution
    backend: str = "process"
    code_timeout: int = 30 * 60
    max_rounds: int = 50
    run_data_loading: bool = True
    # When True, the scored result carries an ``execution_log`` string: the
    # experiment trace (hypothesis/plan query + code output + analysis + review)
    # that produced the surprise. Returned alongside the scalar so a slime run
    # can log it per sample or fold it into training.
    include_execution_log: bool = True

    @classmethod
    def from_env(cls) -> SurpriseRewardConfig:
        """Build a config from AUTODS_* environment variables.

        ``AUTODS_DATASET_METADATA`` is required; every other field can be
        overridden via ``AUTODS_<FIELD_NAME_UPPERCASED>``.
        """
        metadata = os.environ.get("AUTODS_DATASET_METADATA")
        if not metadata:
            raise ValueError(
                "AUTODS_DATASET_METADATA must point to a metadata.json to build "
                "a SurpriseRewardConfig from the environment."
            )
        config = cls(dataset_metadata=metadata)
        for f in dataclasses.fields(cls):
            if f.name == "dataset_metadata":
                continue
            raw = os.environ.get(f"AUTODS_{f.name.upper()}")
            if raw is None:
                continue
            current = getattr(config, f.name)
            if isinstance(current, bool):
                value: object = raw.strip().lower() in ("1", "true", "yes", "on")
            elif isinstance(current, int):
                value = int(raw)
            elif isinstance(current, float):
                value = float(raw)
            else:
                value = raw
            setattr(config, f.name, value)
        return config


class SurpriseRewardScorer:
    """Scores hypotheses by running one experiment and computing Bayesian surprise.

    Agents are built lazily on first use and reused across calls; ``score`` is
    serialized with a lock because the group-chat agents are stateful. For
    concurrent scoring create multiple scorers (see ``serve``).
    """

    def __init__(self, config: SurpriseRewardConfig):
        """Resolve datasets and prepare the work directory (agents built lazily)."""
        self.config = config
        self.dataset_paths, self.dataset_metadata = get_datasets_fpaths(
            config.dataset_metadata, is_blade=config.dataset_metadata_type == "blade"
        )
        self.work_dir = config.work_dir or tempfile.mkdtemp(prefix="autodiscovery_reward_")
        os.makedirs(self.work_dir, exist_ok=True)
        # Symlink datasets into the work dir so sandboxed code finds them by
        # relative path (same convention as run_mcts).
        for fpath in self.dataset_paths:
            abs_src = os.path.abspath(fpath)
            if abs_src.startswith(os.path.abspath(self.work_dir) + os.sep):
                continue
            dst = os.path.join(self.work_dir, os.path.basename(fpath))
            if not os.path.exists(dst):
                os.symlink(abs_src, dst)

        self._agents = None
        self._root_context: str | None = None
        self._warmed_up = False
        self._n_scored = 0
        self._lock = threading.Lock()

    # -- public API ----------------------------------------------------------

    def score(self, hypothesis: str, experiment_plan: dict | str | None = None) -> dict:
        """Run one experiment for *hypothesis* and return the surprisal reward.

        Args:
            hypothesis: Falsifiable hypothesis generated by the policy.
            experiment_plan: Optional pre-made plan. A dict must have
                ``objective``/``steps``/``deliverables`` keys; a string is
                wrapped into that structure. When omitted, the
                experiment_planner agent generates the plan.

        Returns:
            Dict with ``reward`` (float, ``config.failed_reward`` on any
            failure), ``success``, ``surprising``, ``belief_change``,
            ``kl_divergence``, ``prior_mean``, ``posterior_mean``,
            ``hypothesis``, and ``error``.
        """
        with self._lock:
            self._n_scored += 1
            try:
                result = self._score(hypothesis, experiment_plan)
            except Exception as e:  # noqa: BLE001 - reward calls must not crash training
                result = self._failed_result(hypothesis, f"{type(e).__name__}: {e}")
            self._log_result(result)
            return result

    # -- internals -----------------------------------------------------------

    def _score(self, hypothesis: str, experiment_plan: dict | str | None) -> dict:
        config = self.config
        self._ensure_warmup()

        if experiment_plan is None:
            experiment = self._plan(hypothesis)
        elif isinstance(experiment_plan, str):
            experiment = {
                "hypothesis": hypothesis,
                "experiment_plan": {
                    "objective": f"Test the hypothesis: {hypothesis}",
                    "steps": experiment_plan,
                    "deliverables": "Report the results of the analysis.",
                },
            }
        else:
            experiment = {"hypothesis": hypothesis, "experiment_plan": experiment_plan}

        query = get_query_from_experiment(experiment)
        node = MCTSNode(
            level=2,
            node_idx=self._n_scored,
            hypothesis=hypothesis,
            experiment_plan=experiment["experiment_plan"],
            query=query,
        )
        node.messages = self._run_chat(query)
        node.read_experiment_from_messages(store_new_experiments=False)
        # Keep the policy's hypothesis verbatim rather than the query round-trip.
        node.hypothesis = hypothesis

        execution_log = self._build_execution_log(node) if config.include_execution_log else None

        if not node.success:
            return self._failed_result(
                hypothesis,
                "experiment failed executor/reviewer checks",
                execution_log=execution_log,
            )

        # Same evidence construction as compute_and_store_reward (offline beliefs).
        evidence_msg = [
            {
                "role": "user",
                "content": "Current experiment:\n\n"
                + get_context_string(
                    hyp_exp_query=node.query,
                    code_output=node.code_output,
                    analysis=node.analysis,
                    review=node.review,
                    include_code_output=False,
                ),
            }
        ]
        prior, posterior, belief_change, kl_divergence = calculate_prior_and_posterior_beliefs(
            node,
            model=config.belief_model,
            temperature=config.belief_temperature,
            reasoning_effort=config.belief_reasoning_effort,
            n_samples=config.n_belief_samples,
            implicit_bayes_posterior=config.implicit_bayes_posterior,
            surprisal_width=config.surprisal_width,
            belief_mode=config.belief_mode,
            evidence_msg=evidence_msg,
            evidence_weight=config.evidence_weight,
        )
        reward, surprising = get_self_value(
            belief_change=belief_change,
            kl_divergence=kl_divergence,
            binary=config.use_binary_reward,
            width=config.surprisal_width,
            kl_scale=config.kl_scale,
            mode=config.reward_mode,
        )
        return {
            "reward": float(reward),
            "success": True,
            "surprising": bool(surprising),
            "belief_change": float(belief_change),
            "kl_divergence": float(kl_divergence),
            "prior_mean": float(prior.get_mean_belief()),
            "posterior_mean": float(posterior.get_mean_belief(prior=prior)),
            "hypothesis": hypothesis,
            "execution_log": execution_log,
            "error": None,
        }

    def _build_execution_log(self, node) -> str:
        """Assemble the experiment trace (query + code output + analysis + review)."""
        return get_context_string(
            hyp_exp_query=node.query,
            code_output=node.code_output,
            analysis=node.analysis,
            review=node.review,
            include_code_output=True,
        )

    def _failed_result(self, hypothesis: str, error: str, execution_log: str | None = None) -> dict:
        return {
            "reward": float(self.config.failed_reward),
            "success": False,
            "surprising": None,
            "belief_change": None,
            "kl_divergence": None,
            "prior_mean": None,
            "posterior_mean": None,
            "hypothesis": hypothesis,
            "execution_log": execution_log,
            "error": error,
        }

    def _ensure_agents(self) -> dict:
        if self._agents is None:
            from autodiscovery.agents import get_agents

            config = self.config
            self._agents = get_agents(
                self.work_dir,
                # The generator never speaks here; route it to the execution model.
                theorizer_model=config.execution_model,
                execution_model=config.execution_model,
                temperature=config.temperature,
                reasoning_effort=config.reasoning_effort,
                branching_factor=1,
                code_timeout=config.code_timeout,
                backend=config.backend,
                dataset_paths=self.dataset_paths,
                vision_model=config.vision_model,
            )
        return self._agents

    def _ensure_warmup(self) -> None:
        """Run the data-loading experiment once so scoring chats see summary stats."""
        if self._warmed_up or not self.config.run_data_loading:
            return
        self._warmed_up = True
        query = get_query_from_experiment(self._load_dataset_experiment())
        node = MCTSNode(level=1, node_idx=0, query=query)
        node.messages = self._run_chat(query)
        node.read_experiment_from_messages(store_new_experiments=False)
        self._root_context = node.get_context(include_code_output=True)

    def _load_dataset_experiment(self) -> dict:
        return get_load_dataset_experiment(
            self.dataset_paths,
            self.dataset_metadata,
            dataset_metadata_type=self.config.dataset_metadata_type,
        )

    def _context_messages(self) -> list[dict]:
        """Dataset context prepended to planner prompts and experiment chats."""
        if self._root_context:
            content = "PREVIOUS EXPLORATION:\n\n" + self._root_context
        else:
            # No data-loading run: fall back to the metadata description.
            content = get_query_from_experiment(self._load_dataset_experiment())
        return [{"name": "user_proxy", "role": "user", "content": content}]

    def _plan(self, hypothesis: str) -> dict:
        """Turn a plan-free hypothesis into a full experiment via the planner agent."""
        agents = self._ensure_agents()
        scratch = MCTSNode(level=1, node_idx=0)
        scratch.messages = self._context_messages()
        experiments = scratch._plan_hypotheses([hypothesis], agents["experiment_planner"])
        if not experiments:
            raise RuntimeError("experiment_planner returned no parseable experiment plan")
        experiment = experiments[0]
        experiment["hypothesis"] = hypothesis
        return experiment

    def _run_chat(self, query: str) -> list[dict]:
        """Run the experiment group chat for *query*; returns the node's messages."""
        from autogen import GroupChat, GroupChatManager

        agents = self._ensure_agents()
        chat_agents = [
            agents[name]
            for name in (
                "user_proxy",
                "experiment_programmer",
                "code_executor",
                "experiment_code_analyst",
                "experiment_reviewer",
                "experiment_reviser",
            )
        ]
        groupchat = GroupChat(
            agents=chat_agents,
            messages=[],
            max_round=self.config.max_rounds,
            speaker_selection_method=_ExperimentOnlySelector().select_next_speaker,
        )
        chat_manager = GroupChatManager(groupchat=groupchat, llm_config=None)

        messages = []
        if self._root_context:
            messages.extend(self._context_messages())
        messages.append({"name": "user_proxy", "role": "user", "content": query})
        _, last_message = chat_manager.resume(messages=messages)
        agents["user_proxy"].initiate_chat(
            recipient=chat_manager, message=last_message, clear_history=False
        )
        return get_msgs_from_latest_query(groupchat.messages)

    def _log_result(self, result: dict) -> None:
        if self.config.log_dir is None:
            return
        os.makedirs(self.config.log_dir, exist_ok=True)
        out_path = os.path.join(self.config.log_dir, f"reward_{self._n_scored:06d}.json")
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2)


# -- module-level convenience (in-process use from slime) ---------------------

_scorer: SurpriseRewardScorer | None = None
_scorer_lock = threading.Lock()


def get_scorer(config: SurpriseRewardConfig | None = None) -> SurpriseRewardScorer:
    """Return the process-wide scorer, building it from *config* or the env."""
    global _scorer
    with _scorer_lock:
        if _scorer is None:
            _scorer = SurpriseRewardScorer(config or SurpriseRewardConfig.from_env())
        return _scorer


def compute_reward(
    hypothesis: str,
    experiment_plan: dict | str | None = None,
    config: SurpriseRewardConfig | None = None,
) -> float:
    """Score *hypothesis* with the shared scorer and return the scalar reward."""
    return float(get_scorer(config).score(hypothesis, experiment_plan)["reward"])


# -- reward server ------------------------------------------------------------


class _DatasetRouter:
    """Routes reward requests to per-dataset pools of scorers.

    Each ``dataset_id`` gets its own pool of *concurrency* scorers (own work
    dir, agents, and warmed dataset context), built lazily on the first request
    for that dataset so unused datasets cost nothing. ``request_id`` results are
    memoized so an HTTP retry never re-runs a multi-minute experiment.
    """

    def __init__(
        self,
        base_config: SurpriseRewardConfig,
        registry: dict[str, str | dict],
        concurrency: int = 1,
        dedup_cache_size: int = 4096,
    ):
        self._base_config = base_config
        self._registry = registry
        self._concurrency = concurrency
        self._dedup_cache_size = dedup_cache_size
        self._pools: dict[str, queue.Queue[SurpriseRewardScorer]] = {}
        self._pools_lock = threading.Lock()
        self._dedup: OrderedDict[str, dict] = OrderedDict()
        self._dedup_lock = threading.Lock()

    def _config_for(self, dataset_id: str) -> SurpriseRewardConfig:
        entry = self._registry[dataset_id]
        overrides = entry if isinstance(entry, dict) else {"dataset_metadata": entry}
        return replace(self._base_config, **overrides)

    def _get_pool(self, dataset_id: str) -> queue.Queue[SurpriseRewardScorer]:
        with self._pools_lock:
            pool = self._pools.get(dataset_id)
            if pool is None:
                cfg = self._config_for(dataset_id)
                pool = queue.Queue()
                for i in range(self._concurrency):
                    worker_cfg = replace(
                        cfg,
                        work_dir=(
                            os.path.join(cfg.work_dir, dataset_id, f"worker_{i}")
                            if cfg.work_dir
                            else None
                        ),
                        log_dir=(
                            os.path.join(cfg.log_dir, dataset_id, f"worker_{i}")
                            if cfg.log_dir
                            else None
                        ),
                    )
                    pool.put(SurpriseRewardScorer(worker_cfg))
                self._pools[dataset_id] = pool
            return pool

    def _resolve_dataset_id(self, requested: str | None) -> str:
        if requested is not None:
            if requested not in self._registry:
                raise KeyError(requested)
            return requested
        if len(self._registry) == 1:
            return next(iter(self._registry))
        if "default" in self._registry:
            return "default"
        raise KeyError(None)

    def score(self, payload: dict) -> dict:
        dataset_id = self._resolve_dataset_id(payload.get("dataset_id"))
        request_id = payload.get("request_id")
        if request_id is not None:
            with self._dedup_lock:
                if request_id in self._dedup:
                    return self._dedup[request_id]

        pool = self._get_pool(dataset_id)
        scorer = pool.get()
        try:
            result = scorer.score(payload["hypothesis"], payload.get("experiment_plan"))
        finally:
            pool.put(scorer)
        result = {**result, "dataset_id": dataset_id}

        if request_id is not None:
            with self._dedup_lock:
                self._dedup[request_id] = result
                while len(self._dedup) > self._dedup_cache_size:
                    self._dedup.popitem(last=False)
        return result


def serve(
    config: SurpriseRewardConfig,
    registry: dict[str, str | dict],
    host: str = "0.0.0.0",
    port: int = 8000,
    concurrency: int = 1,
    dedup_cache_size: int = 4096,
) -> None:
    """Serve rewards over HTTP with per-dataset routing.

    ``POST /reward {"hypothesis", "dataset_id"?, "experiment_plan"?,
    "request_id"?} -> result dict``. *registry* maps each ``dataset_id`` to a
    metadata path (or a dict of ``SurpriseRewardConfig`` overrides). When only
    one dataset is registered, ``dataset_id`` may be omitted.
    """
    router = _DatasetRouter(config, registry, concurrency, dedup_cache_size)

    class _Handler(BaseHTTPRequestHandler):
        def _respond(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler API
            if self.path == "/health":
                self._respond(200, {"status": "ok", "datasets": sorted(registry)})
            else:
                self._respond(404, {"error": "not found"})

        def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler API
            if self.path != "/reward":
                self._respond(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length) or b"{}")
                payload["hypothesis"]  # presence check
            except (ValueError, KeyError, json.JSONDecodeError) as e:
                self._respond(400, {"error": f"bad request: {e}"})
                return
            try:
                result = router.score(payload)
            except KeyError as e:
                self._respond(
                    400,
                    {"error": f"unknown dataset_id {e.args[0]!r}; known: {sorted(registry)}"},
                )
                return
            self._respond(200, result)

        def log_message(self, format, *args):  # noqa: A002 - BaseHTTPRequestHandler API
            print(f"[slime_reward] {self.address_string()} {format % args}")  # noqa: T201

    server = ThreadingHTTPServer((host, port), _Handler)
    print(  # noqa: T201
        f"Surprisal reward server on http://{host}:{port} "
        f"(concurrency={concurrency}/dataset, datasets={sorted(registry)})"
    )
    server.serve_forever()


def _load_registry(registry_path: str | None, single_metadata: str | None) -> dict[str, str | dict]:
    """Build the ``dataset_id -> metadata`` registry from a file and/or a single path."""
    registry: dict[str, str | dict] = {}
    if registry_path:
        with open(registry_path) as f:
            raw = json.load(f)
        if not isinstance(raw, dict) or not raw:
            raise ValueError(f"{registry_path} must be a non-empty JSON object of id -> metadata")
        registry.update({str(k): v for k, v in raw.items()})
    if single_metadata:
        registry.setdefault("default", single_metadata)
    if not registry:
        raise ValueError("no datasets registered: pass --dataset_registry or --dataset_metadata")
    return registry


def cli_main(argv: list[str] | None = None) -> None:
    """Start the reward server from CLI args (env vars fill unset fields)."""
    parser = argparse.ArgumentParser(
        prog="python -m autodiscovery.slime_reward",
        description="Serve AutoDiscovery surprisal rewards for slime RL training.",
    )
    parser.add_argument("--dataset_metadata", type=str, default=None)
    parser.add_argument(
        "--dataset_registry",
        type=str,
        default=os.environ.get("AUTODS_DATASET_REGISTRY"),
        help=(
            "JSON mapping dataset_id -> metadata path (or config-override dict) "
            "for per-request routing."
        ),
    )
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--dedup_cache_size", type=int, default=4096)
    parser.add_argument("--work_dir", type=str, default=None)
    parser.add_argument("--log_dir", type=str, default=None)
    parser.add_argument("--execution_model", type=str, default=None)
    parser.add_argument("--belief_model", type=str, default=None)
    parser.add_argument("--belief_mode", type=str, default=None)
    parser.add_argument("--n_belief_samples", type=int, default=None)
    parser.add_argument("--surprisal_width", type=float, default=None)
    parser.add_argument("--evidence_weight", type=float, default=None)
    parser.add_argument("--kl_scale", type=float, default=None)
    parser.add_argument(
        "--reward_mode", type=str, choices=["belief", "kl", "belief_and_kl"], default=None
    )
    parser.add_argument("--use_binary_reward", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--backend", type=str, choices=["local", "process", "modal"], default=None)
    parser.add_argument("--code_timeout", type=int, default=None)
    parser.add_argument(
        "--run_data_loading", action=argparse.BooleanOptionalAction, default=None
    )
    parser.add_argument(
        "--include_execution_log", action=argparse.BooleanOptionalAction, default=None
    )
    args = parser.parse_args(argv)

    registry = _load_registry(args.dataset_registry, args.dataset_metadata)

    # The base config just needs a valid dataset_metadata to construct; the
    # router overrides it per dataset. Seed it from the first registered entry.
    first = registry.get("default", next(iter(registry.values())))
    first_path = first["dataset_metadata"] if isinstance(first, dict) else first
    os.environ.setdefault("AUTODS_DATASET_METADATA", first_path)

    config = SurpriseRewardConfig.from_env()
    for f in dataclasses.fields(SurpriseRewardConfig):
        # dataset_metadata is per-dataset (set by the router), never a global override.
        if f.name == "dataset_metadata":
            continue
        value = getattr(args, f.name, None)
        if value is not None:
            setattr(config, f.name, value)

    serve(
        config,
        registry,
        host=args.host,
        port=args.port,
        concurrency=args.concurrency,
        dedup_cache_size=args.dedup_cache_size,
    )


if __name__ == "__main__":
    cli_main()
