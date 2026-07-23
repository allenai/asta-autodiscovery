import copy
import json
import os
import random
from datetime import UTC, datetime

import numpy as np

from autodiscovery.mcts_utils import (
    get_context_string,
    get_experiment_from_query,
    get_node_level_idx,
    get_query_from_experiment,
)
from autodiscovery.utils import try_loading_dict


# On-demand hypothesis-generation prompt, selected by the --hypothesis_mode
# config. "open_ended" preserves the original neutral framing; "related" anchors
# generation to the parent hypothesis so follow-ups stay on the same line of
# inquiry. Both take the parent hypothesis and the JSON of tried experiments.
# Mirrors HYPOTHESIS_RELATEDNESS_INSTRUCTION (the theorizer system message) in
# agents.py, which governs the primary in-chat generation path.
HYPOTHESIS_RELATEDNESS_ONDEMAND = {
    "open_ended": (
        "Generate new hypotheses given these previously attempted experiments: {tried}"
    ),
    "related": (
        "Generate new hypotheses that stay closely related to the current line of inquiry "
        "(parent hypothesis: {parent!r}). Each new hypothesis should probe the same "
        "phenomenon, variables, or mechanism explored so far — for example by refining it, "
        "extending it to an adjacent context, or testing a plausible causal driver, "
        "moderator, or boundary condition of the observed effect — rather than switching to "
        "an unrelated topic. Do not repeat any previously attempted experiment. "
        "Previously attempted experiments: {tried}"
    ),
}


def _warn_experiment_count(n_generated, expected, node_id, source):
    """Log a warning when the experiment_generator yields an unexpected count.

    Warns if it produced no parseable experiments (empty/unparseable output), or
    a number that differs from ``expected`` (k_experiments). ``source`` labels the
    generation path ("on-demand" or "end-of-chat"). No-op when expected is None.
    """
    if n_generated == 0:
        print(
            f"WARNING: experiment_generator produced no parseable experiments "
            f"({source}) for node {node_id} — empty or unparseable generation."
        )
    elif expected is not None and n_generated != expected:
        print(
            f"WARNING: experiment_generator produced {n_generated} experiments "
            f"({source}) for node {node_id}, expected {expected} (k_experiments)."
        )


class MCTSNode:
    _creation_counter = 0

    def __init__(
        self,
        level=None,
        node_idx=None,
        hypothesis=None,
        query=None,
        parent_idx=None,
        parent=None,
        untried_experiments=None,
        allow_generate_experiments=False,
        experiment_plan=None,
        code=None,
        code_output=None,
        analysis=None,
        review=None,
        creation_idx=None,
        created_at=None,
    ):
        # Tree attributes
        self.creation_idx = creation_idx if creation_idx is not None else MCTSNode._creation_counter
        MCTSNode._creation_counter += 1  # Used to replay MCTS from log files
        self.created_at = created_at if created_at is not None else datetime.now(UTC).isoformat()
        self.time_elapsed = None
        self.level = level
        self.node_idx = node_idx
        self.id = (
            f"node_{self.level}_{self.node_idx}"
            if self.level is not None and self.node_idx is not None
            else None
        )
        self.children = []
        self.parent = parent  # MCTSNode
        if self.parent is not None:
            self.parent_idx = self.parent.node_idx
            self.parent_id = self.parent.id
            self.parent.children.append(self)
        else:
            self.parent_idx = parent_idx
            self.parent_id = (
                f"node_{self.level - 1}_{self.parent_idx}" if self.parent_idx is not None else None
            )
        self.success = None

        # Agent attributes
        self.query = query
        self.messages = []
        self.untried_experiments = (
            copy.deepcopy(untried_experiments) if untried_experiments is not None else []
        )
        self.tried_experiments = []  # Track all tried experiments
        self.allow_generate_experiments = allow_generate_experiments

        # Experiment attributes
        self.hypothesis = hypothesis
        self.experiment_plan = experiment_plan
        self.code = code
        self.code_output = code_output
        self.analysis = analysis
        self.review = review

        # MCTS attributes
        self.visits = 0  # Visits to this node or its children
        self.value = 0.0  # Number of surprising hypotheses
        self.self_value = 0.0  # Value of this node only (not aggregated from children)

        # Belief attributes
        self.surprising: bool | None = None
        self.prior = None
        self.posterior = None
        self.belief_change: float | None = None  # Change in belief from prior to posterior
        self.normalized_surprisal: float | None = None
        self.kl_divergence: float | None = None

    def init_from_dict(self, data):
        """Initialize node attributes from a dictionary."""
        # Tree attributes
        self.creation_idx = data.get("creation_idx", MCTSNode._creation_counter)
        self.created_at = data.get("created_at", self.created_at)
        self.time_elapsed = data.get("time_elapsed", self.time_elapsed)
        self.id = data.get("id", None)
        if self.id is not None:
            self.level, self.node_idx = get_node_level_idx(self.id)
        else:
            self.level = data["level"]
            self.node_idx = data["node_idx"]
            self.id = f"node_{self.level}_{self.node_idx}"
        self.parent_id = data.get("parent_id", self.parent_id)
        if self.parent_id is not None:
            _, self.parent_idx = get_node_level_idx(self.parent_id)
        else:
            self.parent_idx = data.get("parent_idx", self.parent_idx)
            if self.parent_idx is not None:
                self.parent_id = f"node_{self.level - 1}_{self.parent_idx}"
        self.success = data.get("success", self.success)

        # Agent attributes
        self.query = data.get("query", "N/A")
        self.messages = data.get("messages", self.messages)
        self.untried_experiments = data.get("untried_experiments", self.untried_experiments)
        # self.tried_experiments = data.get('tried_experiments', self.tried_experiments)
        self.allow_generate_experiments = self.allow_generate_experiments and self.level > 0

        # Experiment attributes
        self.hypothesis = data.get("hypothesis", self.hypothesis)
        self.experiment_plan = data.get("experiment_plan", self.experiment_plan)
        self.code = data.get("code", self.code)
        self.code_output = data.get("code_output", self.code_output)
        self.analysis = data.get("analysis", self.analysis)
        self.review = data.get("review", self.review)

        # MCTS attributes
        self.visits = data.get("visits", self.visits)
        self.value = data.get("value", self.value)
        self.self_value = data.get("self_value", self.self_value)

        # Belief attributes
        self.surprising = data.get("surprising", self.surprising)
        from autodiscovery.beliefs import (
            BELIEF_MODE_TO_CLS,
        )  # Import here to avoid circular import issues

        if "prior" in data and data["prior"]:
            belief_cls = BELIEF_MODE_TO_CLS[data["prior"]["_type"]]
            self.prior = belief_cls.DistributionFormat(**data["prior"])
        if "posterior" in data and data["posterior"]:
            belief_cls = BELIEF_MODE_TO_CLS[data["posterior"]["_type"]]
            self.posterior = belief_cls.DistributionFormat(**data["posterior"])
        self.belief_change = data.get("belief_change", self.belief_change)
        self.normalized_surprisal = data.get("normalized_surprisal", self.normalized_surprisal)
        self.kl_divergence = data.get("kl_divergence", self.kl_divergence)

    def get_next_experiment(
        self,
        experiment_generator=None,
        experiment_planner=None,
        n_retry=3,
        expected_experiments=None,
        hypothesis_mode="open_ended",
    ):
        """Returns the next untried experiment, generating more on demand.

        When the queue is empty and generation is allowed, experiments are
        produced in two steps: the experiment_generator proposes plan-free
        hypotheses, then the experiment_planner turns them into full experiments
        (hypothesis + experiment_plan). The resulting experiments are stored in
        ``untried_experiments`` just as single-step generation did before.

        expected_experiments: the branching factor (k_experiments). When set, a
        warning is logged if generation returns no parseable experiments or a
        count that differs from this expectation.
        hypothesis_mode: selects the on-demand generation prompt ("open_ended"
        or "related"); see HYPOTHESIS_RELATEDNESS_ONDEMAND.
        """
        new_experiment, new_query = None, None

        if n_retry > 0:
            if self.untried_experiments:
                idx = random.randrange(len(self.untried_experiments))
                new_experiment = self.untried_experiments.pop(idx)
                self.tried_experiments.append(new_experiment)
            elif self.allow_generate_experiments and experiment_generator is not None:
                # Two-step generation: propose hypotheses, then plan each one.
                _prompt_template = HYPOTHESIS_RELATEDNESS_ONDEMAND.get(
                    hypothesis_mode, HYPOTHESIS_RELATEDNESS_ONDEMAND["open_ended"]
                )
                _messages = self.messages + [
                    {
                        "role": "user",
                        "content": _prompt_template.format(
                            parent=self.hypothesis or "N/A",
                            tried=json.dumps(self.tried_experiments),
                        ),
                    }
                ]
                gen_reply = experiment_generator.generate_reply(messages=_messages)
                try:
                    hypotheses = try_loading_dict(gen_reply).get("hypotheses", [])
                except (json.JSONDecodeError, TypeError):
                    hypotheses = []
                experiments = self._plan_hypotheses(hypotheses, experiment_planner, _messages)
                _warn_experiment_count(len(experiments), expected_experiments, self.id, "on-demand")
                self.untried_experiments = experiments.copy()
                if self.untried_experiments:
                    idx = random.randrange(len(self.untried_experiments))
                    new_experiment = self.untried_experiments.pop(idx)
                    self.tried_experiments.append(new_experiment)

            if new_experiment is not None:
                try:
                    new_query = get_query_from_experiment(new_experiment)
                except Exception:
                    pass
            if new_query is None:
                return self.get_next_experiment(
                    experiment_generator=experiment_generator,
                    experiment_planner=experiment_planner,
                    n_retry=n_retry - 1,
                    expected_experiments=expected_experiments,
                    hypothesis_mode=hypothesis_mode,
                )

        return new_experiment, new_query

    def _plan_hypotheses(self, hypotheses, experiment_planner, context_messages=None):
        """Turn a batch of plan-free hypotheses into full experiments via the planner.

        Returns a list of ``{hypothesis, experiment_plan}`` dicts (empty if the
        planner is unavailable or produced nothing parseable).
        """
        if not hypotheses or experiment_planner is None:
            return []
        _messages = (context_messages or self.messages) + [
            {
                "role": "user",
                "content": (
                    "You are a research scientist skilled at designing rigorous, informative, and implementable data-analysis experiments. "
                    "You are given one or more hypotheses and your goal is to produce a self-contained and detailed experiment plan for each hypothesis. "
                    "Explain in natural language what this experiment plan is so that a programmer can implement it (do not provide the code yourself). "
                    "Here are some instructions that you must follow:\n"
                    "1. Use only the provided dataset(s). Do not invent, simulate, or assume access to variables that are unavailable or cannot be deterministically derived from existing columns.\n"
                    "2. Preserve the central hypothesis. Use prior experiments only to avoid redundancy and identify useful controls, failure modes, and follow-up analyses.\n"
                    "3. Prefer the simplest analysis that can reliably test the hypothesis. Do not add models, visualizations, subgroup analyses, or statistical tests unless they serve a clear purpose.\n"
                    "4. Do not make causal claims from observational data unless the proposed design and assumptions support causal identification.\n"
                    "5. If the hypothesis cannot be adequately tested with the available data, clearly explain why and propose the closest valid analysis without changing the hypothesis silently.\n\n"
                    "Here is a possible approach to constructing an experiment plan given a hypothesis:\n"
                    "1. Translate the hypothesis into one or more precise, falsifiable predictions. Clearly identify the outcome variable(s), explanatory variable(s), target population or context, and the expected relationship.\n"
                    "2. Verify that the hypothesis can be tested using only the provided dataset(s). Specify any required filtering, joins, feature engineering, or derived variables without inventing new data.\n"
                    "3. Design the primary analysis needed to test the hypothesis. Choose appropriate statistical tests or predictive/causal models, explain why they are suitable, and define what evidence would support or refute the hypothesis.\n"
                    "4. Identify potential confounders, alternative explanations, and sources of bias. Include appropriate controls, robustness checks, subgroup analyses, or sensitivity analyses to distinguish genuine effects from artifacts.\n"
                    "5. Specify the expected workflow, including data preparation, exploratory analyses, model fitting, diagnostics, statistical validation, and the final interpretation of results. Organize the steps so that a programmer can implement them directly.\n"
                    "6. Clearly state the possible conclusions of the experiment, including what results would support the hypothesis, refute it, or remain inconclusive, and discuss any important limitations of the analysis.\n\n"
                    "Generally, in typical data-driven research, you will need to explore and visualize the data for possible high-level insights, clean, transform, or derive new variables from the dataset to be suited for the investigation, deep-dive into specific parts of the data for fine-grained analysis, perform data modeling, and run statistical tests. "
                    "Now, generate one experiment plan for each of the given hypotheses, returning one experiment per hypothesis."
                    f"Hypotheses: {json.dumps({'hypotheses': hypotheses})}"
                ),
            }
        ]
        _reply = experiment_planner.generate_reply(messages=_messages)
        try:
            return try_loading_dict(_reply).get("experiments", [])
        except (json.JSONDecodeError, TypeError):
            return []

    def has_untried_experiments(self):
        return bool(self.untried_experiments) or self.allow_generate_experiments

    def to_dict(self):
        return {
            "id": self.id,
            "success": self.success,
            "parent_id": self.parent_id,
            "creation_idx": self.creation_idx,
            "created_at": self.created_at,
            "time_elapsed": self.time_elapsed,
            "visits": self.visits,
            "value": self.value,
            "self_value": self.self_value,
            "surprising": self.surprising,
            "belief_change": self.belief_change,
            "normalized_surprisal": self.normalized_surprisal,
            "kl_divergence": self.kl_divergence,
            "prior": self.prior.to_dict() if self.prior else None,
            "posterior": self.posterior.to_dict() if self.posterior else None,
            "hypothesis": self.hypothesis,
            "experiment_plan": self.experiment_plan,
            "code": self.code,
            "code_output": self.code_output,
            "analysis": self.analysis,
            "review": self.review,
            "untried_experiments": self.untried_experiments,
            "tried_experiments": self.tried_experiments,
            "query": self.query,
            "messages": self.messages,
        }

    def read_experiment_from_messages(self, store_new_experiments=False, expected_experiments=None):
        """Extracts experiment details from messages and updates the node's attributes.

        expected_experiments: the branching factor (k_experiments). When
        store_new_experiments is set, a warning is logged if the generator's
        end-of-chat message yielded no parseable experiments or a count that
        differs from this expectation.
        """
        latest_experiment = None
        was_revised = False
        latest_programmer = None
        latest_code_executor = None
        latest_analyst = None
        latest_reviewer = None
        latest_reviewer_feedback = "N/A"
        latest_reviewer_success = False
        latest_experiment_generator = None

        for msg in reversed(self.messages):
            if not latest_experiment and msg.get("name") in ["user_proxy", "experiment_reviser"]:
                latest_experiment = msg.get("content")
                if msg.get("name") == "experiment_reviser":
                    was_revised = True
            elif not latest_programmer and msg.get("name") == "experiment_programmer":
                latest_programmer = try_loading_dict(msg.get("content")).get("code", "N/A")
            elif not latest_code_executor and msg.get("name") == "code_executor":
                latest_code_executor = msg.get("content")
            elif not latest_analyst and msg.get("name") in [
                "experiment_analyst",
                "experiment_code_analyst",
            ]:
                latest_analyst = try_loading_dict(msg.get("content")).get("analysis", "N/A")
            elif not latest_reviewer and msg.get("name") == "experiment_reviewer":
                latest_reviewer = try_loading_dict(msg.get("content"))
                latest_reviewer_feedback = latest_reviewer.get("feedback", "N/A")
                if latest_reviewer_feedback == "":
                    latest_reviewer_feedback = "N/A"
                latest_reviewer_success = latest_reviewer.get("success", False)
            elif not latest_experiment_generator and msg.get("name") == "experiment_planner":
                # Two-step generation: the generator emits plan-free hypotheses and
                # the planner (running right after it in the chat) turns them into
                # full experiments. Harvest the planner's experiments for the queue.
                latest_experiment_generator = try_loading_dict(msg.get("content")).get(
                    "experiments", []
                )

            if (
                latest_experiment
                and latest_programmer
                and latest_code_executor
                and latest_analyst
                and latest_reviewer
            ):
                break

        if was_revised:
            latest_experiment_obj = try_loading_dict(latest_experiment)
            # Change what the query should now be based on the revised experiment
            self.query = get_query_from_experiment(latest_experiment_obj)
        else:
            latest_experiment_obj = get_experiment_from_query(
                latest_experiment
            )  # assuming it is a query string

        self.hypothesis = latest_experiment_obj.get("hypothesis", "N/A")
        self.experiment_plan = latest_experiment_obj.get("experiment_plan", "N/A")
        self.code = latest_programmer
        self.code_output = latest_code_executor
        self.analysis = latest_analyst
        self.review = latest_reviewer_feedback
        self.success = latest_reviewer_success

        # Store new experiments into untried_experiments
        if store_new_experiments:
            n_generated = len(latest_experiment_generator) if latest_experiment_generator else 0
            _warn_experiment_count(n_generated, expected_experiments, self.id, "end-of-chat")
            if latest_experiment_generator:
                self.untried_experiments += latest_experiment_generator

    def get_context(self, include_code_output=False) -> None | str:
        """Returns the node's hypothesis, experiment, output, analysis, and review."""
        if len(self.messages) == 0:
            return None
        context_str = get_context_string(
            self.query,
            self.code_output,
            self.analysis,
            self.review,
            include_code_output=include_code_output,
        )
        return context_str

    def get_path_context(self, k: int | None = None, skip_root=True) -> list:
        """Returns messages from the node to the root

        Args:
            k: Optional maximum number of parent levels to include. If None, includes all parents.
            skip_root: If True, skips the root node in the context.
        """
        if self.parent is None:
            return []

        current_context = self.parent.get_context()
        context: list = []
        if current_context is not None and not (skip_root and self.parent.level <= 1):
            context = [current_context]

        k_remaining = None if k is None else k - 1
        if self.parent is not None and (k_remaining is None or k_remaining > 0):
            parent_context = self.parent.get_path_context(k=k_remaining, skip_root=skip_root)
            if parent_context:
                context = parent_context + context

        return context

    def update_counts(self, visits: int = 1, reward: float = 0):
        """Update the visit count and value of this node and its parents."""
        self.visits += visits
        self.value += reward
        if self.parent is not None:
            self.parent.update_counts(visits=visits, reward=reward)


def default_mcts_selection(exploration_weight):
    """Create a selection function that returns nodes with available experiments by UCB1 score.

    Args:
        exploration_weight: Exploration weight for UCB1 selection.

    Returns:
        Callable selection function.
    """

    def select(node, nodes_by_level, return_n=1):
        return_nodes = []
        queue = [node]

        while len(return_nodes) < return_n and queue:
            current_node = queue.pop(0)
            if current_node.has_untried_experiments():
                return_nodes.append(current_node)
            if current_node.children:
                sorted_children = sorted(
                    current_node.children, key=lambda n: ucb1(n, exploration_weight), reverse=True
                )
                queue += sorted_children

        return return_nodes

    return select


def progressive_widening(k, alpha, exploration_weight=1.0):
    """Create a progressive widening selection function.

    Args:
        k: Progressive widening constant.
        alpha: Progressive widening exponent.
        exploration_weight: Exploration weight for UCB1 selection method.

    Returns:
        A callable function that accepts a `node` and returns the selected node.
    """

    def select(node, nodes_by_level, return_n=1):
        return_nodes = []
        queue = [node]

        while len(return_nodes) < return_n and queue:
            current_node = queue.pop(0)
            num_visits = current_node.visits
            num_children = len(current_node.children)
            if (
                num_children == 0 or num_children < k * (num_visits**alpha)
            ) and current_node.has_untried_experiments():
                return_nodes.append(current_node)
                if len(return_nodes) >= return_n:
                    break

            if current_node.children:
                sorted_children = sorted(
                    current_node.children, key=lambda n: ucb1(n, exploration_weight), reverse=True
                )
                queue += sorted_children

        return return_nodes

    return select


def progressive_widening_all(k, alpha, exploration_weight=1.0):
    """Create a progressive widening selection function with an alternative implementation that selects the node
    which has the highest UCB1 value from the entire set of nodes.

    Args:
        k: Progressive widening constant.
        alpha: Progressive widening exponent.
        exploration_weight: Exploration weight for UCB1 selection method.

    Returns:
        A callable function that accepts a `node` and returns the selected node.
    """

    def select(node, nodes_by_level, return_n=1):
        return_nodes = []
        all_nodes = [n for level, nodes in nodes_by_level.items() if level > 0 for n in nodes]
        # Sort all nodes by UCB1 value
        all_nodes_sorted = sorted(
            all_nodes, key=lambda n: ucb1(n, exploration_weight), reverse=True
        )

        for _node in all_nodes_sorted:
            num_visits = _node.visits
            num_children = len(_node.children)
            # If we can add a new child based on the progressive widening condition
            if (
                num_children == 0 or num_children < k * (num_visits**alpha)
            ) and _node.has_untried_experiments():
                return_nodes.append(_node)
                if len(return_nodes) >= return_n:
                    break

        return return_nodes

    return select


def ucb1_recursive(exploration_weight=1.0):
    """Create a UCB1 traversal selection function.

    Args:
        exploration_weight: Exploration weight for UCB1 selection method.

    Returns:
        A callable function that accepts a `node` and returns the selected node.
    """

    def select(node, nodes_by_level, return_n=1):
        # Sort self and children by UCB1 value
        all_nodes = [node] + node.children
        sorted_nodes = sorted(all_nodes, key=lambda n: ucb1(n, exploration_weight), reverse=True)

        return_nodes = []
        for best_node in sorted_nodes:
            if len(return_nodes) >= return_n:
                break
            if best_node.has_untried_experiments():
                if best_node is node:
                    return_nodes.append(best_node)
                else:
                    return_nodes.extend(
                        select(best_node, nodes_by_level, return_n=return_n - len(return_nodes))
                    )

        return return_nodes

    return select


def beam_search(branching_factor, beam_width, log_dirname=None):
    """Create a beam search selection function.

    Args:
        branching_factor: Maximum number of children per node
        beam_width: Number of nodes to keep in beam

    Returns:
        A callable function that accepts a root node and returns selected nodes.
    """

    def select(root, nodes_by_level, return_n=1):
        return_nodes = []
        beam = [root]

        while beam and len(return_nodes) < return_n:
            for node in beam:
                if node.has_untried_experiments() and len(node.children) < branching_factor:
                    return_nodes.append(node)
                    if len(return_nodes) >= return_n:
                        break
            if len(return_nodes) >= return_n:
                break

            candidates = []
            for node in beam:
                children = node.children
                if not children:
                    continue
                if len(children) > branching_factor:
                    candidates.extend(
                        sorted(children, key=lambda n: ucb1(n), reverse=True)[:branching_factor]
                    )
                else:
                    candidates.extend(children)

            if not candidates:
                break

            if len(candidates) > beam_width:
                beam = sorted(candidates, key=lambda n: ucb1(n), reverse=True)[:beam_width]
            else:
                beam = candidates

        if log_dirname:
            beam_state = [{"level": node.level, "node_idx": node.node_idx} for node in beam]
            level = beam[0].level if beam else 0
            with open(os.path.join(log_dirname, f"beam_level_{level}.json"), "w") as f:
                json.dump(beam_state, f, indent=2)

        return return_nodes

    return select


def ucb1(node, exploration_weight=1.0):
    """Upper Confidence Bound 1 calculation for node selection"""
    if node.visits == 0:
        return float("inf")
    exploitation_term = node.value / node.visits
    exploration_term = 0
    if node.parent:
        exploration_term = np.sqrt(2 * np.log(node.parent.visits) / node.visits)
    return exploitation_term + exploration_weight * exploration_term
