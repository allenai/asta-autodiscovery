import json
import math
import os
import shutil
import threading
import traceback
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from time import time

from autodiscovery.agents import get_agents
from autodiscovery.args import ArgParser
from autodiscovery.beliefs import calculate_prior_and_posterior_beliefs
from autodiscovery.dataset import get_datasets_fpaths, get_load_dataset_experiment
from autodiscovery.future_utils import gather_completed_futures
from autodiscovery.llm_retry import apply_openai_wrapper_usage_tracking
from autodiscovery.llm_usage import (
    UsageTracker,
    clear_ag2_usage_context,
    configure_ag2_usage_tracking,
    extract_local_image_usage_markers,
    set_ag2_usage_context,
    snapshot_agents_actual_usage,
)
from autodiscovery.logger import TreeLogger
from autodiscovery.mcts import (
    MCTSNode,
    beam_search,
    default_mcts_selection,
    progressive_widening,
    progressive_widening_all,
    ucb1_recursive,
)
from autodiscovery.mcts_utils import (
    get_context_string,
    get_msgs_from_latest_query,
    get_self_value,
    load_mcts_from_json,
    print_node_info,
    save_mcts_node,
    save_nodes,
    select_nodes,
    setup_group_chat,
)


def _theoretical_max_boolean_cat(
    n_samples: int, evidence_weight: float, prior_params: tuple[float, float] = (0.5, 0.5)
) -> float:
    """Compute the maximum possible mean shift for boolean_cat beliefs.

    Args:
        n_samples: Maximum number of prior-stage samples (N).
        evidence_weight: Weight applied to stage-2 (evidence) samples.
        prior_params: Beta prior parameters (alpha, beta).

    Returns:
        Theoretical maximum |mu2 - mu1| over all nodes given N and evidence weight.
    """
    n = float(n_samples)
    w = float(evidence_weight)
    if n <= 0 or w <= 0:
        return 0.0

    alpha, beta = prior_params
    s = alpha + beta
    d = min(alpha, beta)
    t = w * n

    # Unconstrained (relaxed) optimum in u = S + n space.
    u_star = d + math.sqrt(d * (d + t))
    # Clamp to feasible interval u in [S, S + N] because n in [0, N].
    u_opt = min(max(u_star, s), s + n)
    return (t * (u_opt - d)) / (u_opt * (u_opt + t))


def compute_and_store_reward(
    node,
    belief_model_name,
    belief_temperature,
    belief_reasoning_effort,
    n_belief_samples,
    implicit_bayes_posterior,
    surprisal_width,
    belief_mode,
    use_binary_reward,
    all_surprisals=None,
    use_online_beliefs=False,
    evidence_weight=1.0,
    kl_scale=20.0,
    reward_mode="belief",
    TEMP_LOG=None,
    usage_tracker: UsageTracker | None = None,
):
    """Compute node belief metrics, reward, and surprisal flags.

    Args:
        node: Node whose reward will be computed.
        belief_model_name: Model name for belief elicitation.
        belief_temperature: Temperature for belief sampling.
        belief_reasoning_effort: Reasoning effort for belief-model calls.
        n_belief_samples: Number of belief samples.
        implicit_bayes_posterior: Whether posterior uses implicit prior knowledge.
        surprisal_width: Width threshold for binary surprisal.
        belief_mode: Belief elicitation mode.
        use_binary_reward: Whether to compute binary reward.
        all_surprisals: Running list of surprising nodes.
        use_online_beliefs: Whether to condition prior on prior surprising nodes.
        evidence_weight: Weight for current evidence in posterior update.
        kl_scale: Scale factor for KL reward normalization.
        reward_mode: Reward mode combining belief and KL terms.
        TEMP_LOG: Optional debug log collector.
        usage_tracker: Optional usage tracker.
    """
    s_conditioned_prior = None
    evidence_msg = []

    # If there are past surprisal, computed the s-conditioned prior
    if all_surprisals is not None and len(all_surprisals) > 0 and use_online_beliefs:
        # Build evidence message for prior belief elicitation
        evidence_msg = [
            {
                "role": "user",
                "content": "Previous study:\n\n"
                + get_context_string(
                    hyp_exp_query=f"Hypothesis: {nodes_by_level[level_index[0]][level_index[1]].hypothesis}",
                    analysis=nodes_by_level[level_index[0]][level_index[1]].analysis,
                    review=nodes_by_level[level_index[0]][level_index[1]].review,
                    belief_mean=nodes_by_level[level_index[0]][level_index[1]].posterior.mean,
                    include_code_output=False,
                ),
            }
            for level_index in all_surprisals
        ]
        try:
            pt_prior, s_conditioned_prior, _, _ = calculate_prior_and_posterior_beliefs(
                node,
                model=belief_model_name,
                temperature=belief_temperature,
                reasoning_effort=belief_reasoning_effort,
                n_samples=n_belief_samples,
                implicit_bayes_posterior=implicit_bayes_posterior,
                surprisal_width=surprisal_width,
                belief_mode=belief_mode,
                evidence_msg=evidence_msg,
                usage_tracker=usage_tracker,
                usage_node_id=node.id,
                usage_context_label="surprisal_conditioned",
            )
        except ValueError as e:
            print(f"Error for node {node.id}: {e}")
            node.success = False
            return

        # TEMPORARY LOGGING
        if TEMP_LOG is not None:
            TEMP_LOG.append(
                {
                    "node_id": node.id,
                    "belief_change": None,
                    "kl_divergence": None,
                    "hypothesis": node.hypothesis,
                    "pt_prior": pt_prior.to_dict(),
                    "surprisal_evidence": [e["content"] for e in evidence_msg],
                    "s_conditioned_prior": s_conditioned_prior.to_dict(),
                }
            )

    # Build the evidence message for the current node
    evidence_msg.append(
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
    )

    # Compute the prior and posterior beliefs for the current node
    try:
        prior, posterior, belief_change, kl_divergence = calculate_prior_and_posterior_beliefs(
            node,
            model=belief_model_name,
            temperature=belief_temperature,
            reasoning_effort=belief_reasoning_effort,
            n_samples=n_belief_samples,
            implicit_bayes_posterior=implicit_bayes_posterior,
            surprisal_width=surprisal_width,
            belief_mode=belief_mode,
            prior=s_conditioned_prior,
            evidence_msg=evidence_msg,
            evidence_weight=evidence_weight,
            usage_tracker=usage_tracker,
            usage_node_id=node.id,
            usage_context_label="main",
        )
    except ValueError as e:
        print(f"Error for node {node.id}: {e}")
        node.success = False
        return

    normalized_surprisal = None
    if belief_mode == "boolean_cat" and prior is not None and posterior is not None:
        prior_params = getattr(prior, "prior_params", (0.5, 0.5))
        theoretical_max = _theoretical_max_boolean_cat(
            n_belief_samples, evidence_weight, prior_params=prior_params
        )
        if theoretical_max != 0:
            prior_mean = prior.get_mean_belief(recompute=True)
            posterior_mean = posterior.get_mean_belief(prior=prior, recompute=True)
            normalized_surprisal = (posterior_mean - prior_mean) / theoretical_max

    # TEMPORARY LOGGING
    if TEMP_LOG is not None and len(TEMP_LOG) > 0:
        # Generate the posterior without surprisals
        _, _posterior, _belief_change, _kl_divergence = calculate_prior_and_posterior_beliefs(
            node,
            model=belief_model_name,
            temperature=belief_temperature,
            reasoning_effort=belief_reasoning_effort,
            n_samples=n_belief_samples,
            implicit_bayes_posterior=implicit_bayes_posterior,
            surprisal_width=surprisal_width,
            belief_mode=belief_mode,
            prior=pt_prior,
            evidence_msg=evidence_msg[-1:],
            evidence_weight=evidence_weight,
            usage_tracker=usage_tracker,
            usage_node_id=node.id,
            usage_context_label="offline_diagnostic",
        )

        TEMP_LOG[-1]["current_evidence"] = evidence_msg[-1]["content"]
        TEMP_LOG[-1]["online_posterior"] = posterior.to_dict()
        TEMP_LOG[-1]["belief_change"] = belief_change
        TEMP_LOG[-1]["kl_divergence"] = kl_divergence
        TEMP_LOG[-1]["offline_posterior"] = _posterior.to_dict()
        TEMP_LOG[-1]["offline_belief_change"] = _belief_change
        TEMP_LOG[-1]["offline_kl_divergence"] = _kl_divergence
        TEMP_LOG[-1]["current_surprisals"] = all_surprisals.copy()

        print("\n\n======================= SURPRISAL-CONDITION BELIEFS =======================\n")
        print(
            json.dumps(
                {
                    k: v
                    for k, v in TEMP_LOG[-1].items()
                    if k
                    in ["pt_prior", "s_conditioned_prior", "online_posterior", "offline_posterior"]
                },
                indent=2,
            )
        )

    node.prior = prior
    node.posterior = posterior
    node.belief_change = belief_change
    node.normalized_surprisal = normalized_surprisal
    node.kl_divergence = kl_divergence
    # Compute reward and surprisal
    node.self_value, node.surprising = get_self_value(
        belief_change=node.belief_change,
        kl_divergence=node.kl_divergence,
        binary=use_binary_reward,
        width=surprisal_width,
        kl_scale=kl_scale,
        mode=reward_mode,
    )
    if node.surprising:
        # Store the surprisal
        all_surprisals.append((node.level, node.node_idx))
        # TODO: Update all past nodes with the new surprisal set


def run_mcts(
    root,
    nodes_by_level,
    dataset_paths,
    log_dirname,
    work_dir,
    model_name="gpt-4o",
    belief_model_name="gpt-4o",
    max_iterations=100,
    branching_factor=8,
    max_rounds=100000,
    selection_method=None,
    allow_generate_experiments=False,
    n_belief_samples=30,
    k_parents=3,
    temperature=1.0,
    belief_temperature=1.0,
    reasoning_effort="medium",
    belief_reasoning_effort="minimal",
    implicit_bayes_posterior=False,
    surprisal_width=0.2,
    user_query=None,
    belief_mode="categorical",
    use_binary_reward=True,
    run_dedupe=True,
    experiment_first=False,
    code_timeout=30 * 60,
    n_warmstart=0,
    use_online_beliefs=False,
    evidence_weight=1.0,
    kl_scale=20.0,
    reward_mode="belief_and_kl",
    warmstart_experiments=None,
    use_modal_sandbox=False,
    bucket_path=None,
    vision_model="gpt-4o",
    batch_size=1,
    n_threads=1,
    agent_usage_mode: str = "per_response",
):
    """Run AutoDS exploration. In MCTS, root node level=0 is a dummy node with no experiment, level=1 is the first real node with the dataset loading experiment, levels > 1 are the actual MCTS nodes with hypotheses and experiments.

    Args:
        root: Root MCTSNode to continue from.
        nodes_by_level: Dictionary to store nodes by level.
        dataset_paths: List of paths to dataset files.
        log_dirname: Directory to save logs and MCTS nodes.
        work_dir: Working directory for agents.
        model_name: LLM model name for agents.
        belief_model_name: LLM model name for belief distribution agent.
        max_iterations: Maximum number of MCTS iterations.
        branching_factor: Maximum number of children per node.
        max_rounds: Maximum number of rounds for the group chat.
        selection_method: Function to select nodes in MCTS (default is UCB1).
        allow_generate_experiments: Whether to allow nodes to generate new experiments on demand.
        n_belief_samples: Number of samples for belief distribution evaluation.
        k_parents: Number of parent levels to include in logs (None for all).
        temperature: Temperature setting for all agents (except belief agent).
        belief_temperature: Temperature setting for the belief agent.
        reasoning_effort: Reasoning effort for non-belief agent model calls.
        belief_reasoning_effort: Reasoning effort for belief-model calls.
        implicit_bayes_posterior: Whether to use the belief samples with evidence as the direct posterior or to use a Bayesian update that explicitly combines it with the prior.
        surprisal_width: Minimum difference in mean prior and posterior probabilities required to count as a surprisal.
        user_query: Custom user query to condition experiment generation during exploration.
        belief_mode: Belief elicitation mode (boolean, categorical, categorical_numeric, or probability).
        use_binary_reward: Whether to use binary reward for MCTS instead of a continuous reward (belief change).
        run_dedupe: Whether to deduplicate nodes before saving to JSON and CSV.
        experiment_first: If True, an experiment will be generated before its hypothesis.
        code_timeout: Timeout for code execution in seconds (default is 30 minutes).
        n_warmstart: Number of warmstart experiments to run after data loading but before MCTS selection.
        use_online_beliefs: Whether to use online beliefs (i.e., beliefs updated with evidence from previous nodes).
        evidence_weight: Weight for the experimental evidence for posterior calculation.
        kl_scale: Normalization factor for KL divergence in reward calculation.
        reward_mode: Mode for reward calculation (belief, kl, or belief_and_kl).
        warmstart_experiments: Path to JSON file with warmstart experiments to run after data loading but before MCTS selection.
        use_modal_sandbox: Whether to use ModalSandboxIPythonBackend for code execution.
        bucket_path: GCS bucket path for Modal sandbox (e.g., gs://example-gcp-project/discoverybench/).
        vision_model: Model used for image analysis in code execution.
        batch_size: Number of nodes to select and expand per iteration.
        n_threads: Number of threads to use for parallel node expansion.
        agent_usage_mode: Tracking mode for agents chat usage. ``per_response`` records
            usage from each AG2 model response. ``summary_delta`` records usage from
            AG2 usage-summary deltas.
    """

    def _get_executor_rich_outputs(code_executor_agent) -> list:
        """Return the most recent rich outputs from the code executor, if available."""
        executor = getattr(code_executor_agent, "code_executor", None)
        if executor is None or not hasattr(executor, "get_last_rich_outputs"):
            return []
        return executor.get_last_rich_outputs() or []

    def _write_rich_outputs(level: int, node_idx: int, rich_outputs: list) -> None:
        """Persist rich outputs for a node to the rich_outputs directory."""
        rich_outputs_dir = os.path.join(log_dirname, "rich_outputs")
        os.makedirs(rich_outputs_dir, exist_ok=True)
        output_path = os.path.join(rich_outputs_dir, f"ro_{level}_{node_idx}.json")
        with open(output_path, "w") as f:
            json.dump(rich_outputs, f, indent=2)

    def _set_executor_usage_context(code_executor_agent, node_id: str | None) -> None:
        """Set usage context on executors that support direct image-analysis tracking."""
        executor = getattr(code_executor_agent, "code_executor", None)
        if executor is not None and hasattr(executor, "set_usage_context"):
            executor.set_usage_context(usage_tracker, node_id=node_id)

    # Setup logger
    logger = TreeLogger(log_dirname)

    # Track time
    start_time = time()

    # Create work directory if it doesn't exist
    os.makedirs(work_dir, exist_ok=True)

    usage_tracker = UsageTracker()
    usage_tracker.save_events(log_dirname)

    try:
        if agent_usage_mode == "per_response":
            if not apply_openai_wrapper_usage_tracking():
                raise RuntimeError(
                    "Agent usage mode 'per_response' requires AG2 OpenAIWrapper patching, "
                    "but the patch could not be applied. Rerun with "
                    "--agent_usage_mode=summary_delta to use explicit fallback mode."
                )
            configure_ag2_usage_tracking(usage_tracker)
        elif agent_usage_mode == "summary_delta":
            configure_ag2_usage_tracking(None)
        else:
            raise ValueError(
                f"Unknown agent_usage_mode '{agent_usage_mode}'. "
                "Expected one of ['per_response', 'summary_delta']."
            )

        # Copy the dataset file paths to the working directory (to avoid modifying the original dataset)
        # Note: For Modal sandbox, files are in GCS and will be mounted directly
        if not use_modal_sandbox:
            for dataset_fpath in dataset_paths:
                shutil.copy(dataset_fpath, work_dir)

        base_agent_objs = None
        if n_threads <= 1:
            base_agent_objs = get_agents(
                work_dir,
                model_name=model_name,
                temperature=temperature,
                reasoning_effort=reasoning_effort,
                branching_factor=branching_factor,
                user_query=user_query,
                experiment_first=experiment_first,
                code_timeout=code_timeout,
                use_modal_sandbox=use_modal_sandbox,
                bucket_path=bucket_path,
                dataset_paths=dataset_paths,
                vision_model=vision_model,
                usage_tracker=usage_tracker,
            )

        if selection_method is None:
            # Default selection method is UCB1
            selection_method = default_mcts_selection(exploration_weight=1.0)

        # Store the list of (level, node_idx) tuples for surprising nodes; if resuming, load them from the previous run
        all_surprisals = []
        for level in nodes_by_level:
            for node in nodes_by_level[level]:
                if node.surprising:
                    all_surprisals.append((node.level, node.node_idx))

        # Load warmstart experiments if provided
        _warmstart_experiments = None
        if warmstart_experiments is not None:
            with open(warmstart_experiments) as f:
                _warmstart_experiments = json.load(f)

        # TEMPORARY LOGGING
        TEMP_LOG = []

        total_to_sample = max_iterations
        n_root_iteration = 1 if len(nodes_by_level[1]) == 0 else 0
        warmstart_remaining = max(0, n_warmstart - len(nodes_by_level[2]))
        remaining_after_warmstart = max(0, total_to_sample - n_root_iteration - warmstart_remaining)
        n_iterations = (
            n_root_iteration
            + math.ceil(warmstart_remaining / batch_size)
            + math.ceil(remaining_after_warmstart / batch_size)
        )
        n_sampled = 0

        for iteration_idx in range(n_iterations):
            # MCTS SELECTION, EXPANSION, and EXECUTION
            print(f"\n\n######### ITERATION {iteration_idx + 1} / {n_iterations} #########\n")

            next_nodes = select_nodes(
                selection_method,
                root,
                nodes_by_level,
                n_warmstart,
                return_n=batch_size,
            )[: total_to_sample - n_sampled]
            if not next_nodes:
                break
            print(
                "SAMPLED "
                f"{len(next_nodes)} NODE(S) FOR EXPANSION: "
                f"{[f'{node.level}_{node.node_idx}' for node in next_nodes]}\n"
            )
            n_sampled += len(next_nodes)

            def _expand_node(
                inbatch_idx,
                node,
                agent_objs,
                logger_obj,
                get_node_idx,
                update_mcts_lock=None,
                is_threaded=False,
            ):
                print(
                    f"({inbatch_idx + 1}/{len(next_nodes)}): "
                    f"EXPANDING NODE {node.level}_{node.node_idx}\n"
                    "==========================\n"
                )

                experiment_generator = agent_objs["experiment_generator"]
                user_proxy_local = agent_objs["user_proxy"]

                # Fetch or generate the next experiment from the selected node (retries built in)
                new_experiment, new_query = node.get_next_experiment(
                    experiment_generator=experiment_generator
                )

                if new_query is None:
                    print(
                        f"No new experiment generated for node {node.level}_{node.node_idx}. "
                        "Skipping this iteration."
                    )
                    return None

                # Create a new node for the next experiment
                new_level = node.level + 1
                new_node_idx = get_node_idx(new_level)
                node = MCTSNode(
                    level=new_level,
                    node_idx=new_node_idx,
                    hypothesis=new_experiment["hypothesis"],
                    experiment_plan=new_experiment["experiment_plan"],
                    query=new_query,
                    parent=node,
                    allow_generate_experiments=allow_generate_experiments and new_level > 0,
                    untried_experiments=_warmstart_experiments if new_level == 1 else None,
                )

                # Update logger state
                logger_obj.level = node.level
                logger_obj.node_idx = node.node_idx

                # Load previous explorations (make sure the root is always included)
                node_context = []
                if node.level > 1:
                    node_context = [
                        root.children[0].get_context(include_code_output=True)
                    ] + node.get_path_context(k=k_parents - 1, skip_root=True)
                node_messages = []
                if node_context is not None:
                    node_messages += [
                        {
                            "name": "user_proxy",
                            "role": "user",
                            "content": "PREVIOUS EXPLORATION:\n\n" + n,
                        }
                        for n in node_context
                    ]
                node_messages += [
                    {
                        "name": "user_proxy",
                        "role": "user",
                        "content": node.query
                        + (
                            "\n\nNote for the programmer: Dataset files are present one level above the current "
                            "working directory."
                            if is_threaded
                            else ""
                        ),
                    }
                ]

                # Set up the group chat
                groupchat, chat_manager = setup_group_chat(agent_objs, max_rounds)
                _, last_message = chat_manager.resume(messages=node_messages)
                agent_usage_before = None
                if agent_usage_mode == "summary_delta":
                    agent_usage_before = snapshot_agents_actual_usage(agent_objs)
                _set_executor_usage_context(agent_objs["code_executor"], node.id)
                if agent_usage_mode == "per_response":
                    set_ag2_usage_context(node_id=node.id, component="agents.chat")

                # Track time per node
                _node_start_time = time()

                # Execute current experiment and generate new experiments
                try:
                    user_proxy_local.initiate_chat(
                        recipient=chat_manager, message=last_message, clear_history=False
                    )
                finally:
                    if agent_usage_mode == "per_response":
                        clear_ag2_usage_context()
                if agent_usage_mode == "summary_delta":
                    assert agent_usage_before is not None
                    agent_usage_after = snapshot_agents_actual_usage(agent_objs)
                    usage_tracker.record_agent_usage_deltas(
                        agent_usage_before,
                        agent_usage_after,
                        node_id=node.id,
                        component="agents.chat",
                    )

                # Store the raw message logs for the node
                logger_obj.log_node(
                    node.level, node.node_idx, chat_manager.messages_to_string(groupchat.messages)
                )

                # Get messages starting from the current query and update the node
                node.messages = get_msgs_from_latest_query(groupchat.messages)
                node.read_experiment_from_messages(
                    store_new_experiments=False
                    if node.level == 1 and _warmstart_experiments is not None
                    else True
                )
                if node.code_output:
                    image_usage_entries, cleaned_output = extract_local_image_usage_markers(
                        node.code_output
                    )
                    for usage_entry in image_usage_entries:
                        usage_tracker.record_event(
                            source=usage_entry.get("source", "openai"),
                            component=usage_entry.get("component", "image_analysis.local"),
                            model=usage_entry.get("model"),
                            prompt_tokens=usage_entry.get("prompt_tokens", 0),
                            completion_tokens=usage_entry.get("completion_tokens", 0),
                            total_tokens=usage_entry.get("total_tokens"),
                            agent_name=usage_entry.get("agent_name", "code_executor"),
                            node_id=node.id,
                        )
                    node.code_output = cleaned_output
                rich_outputs = _get_executor_rich_outputs(agent_objs["code_executor"])
                _write_rich_outputs(node.level, node.node_idx, rich_outputs)

                # Calculate beliefs and rewards
                if node.success and node.level > 1:
                    compute_and_store_reward(
                        node,
                        belief_model_name,
                        belief_temperature,
                        belief_reasoning_effort,
                        n_belief_samples,
                        implicit_bayes_posterior,
                        surprisal_width,
                        belief_mode,
                        use_binary_reward,
                        all_surprisals,
                        use_online_beliefs=use_online_beliefs,
                        evidence_weight=evidence_weight,
                        kl_scale=kl_scale,
                        reward_mode=reward_mode,
                        TEMP_LOG=TEMP_LOG,
                        usage_tracker=usage_tracker,
                    )

                    if node.success:  # i.e., reward was computed successfully
                        # Print debug information
                        print_node_info(node)

                        # TEMPORARY LOGGING
                        if TEMP_LOG:
                            temp_log_file = os.path.join(log_dirname, "temp_log.json")
                            with open(temp_log_file, "w") as f:
                                json.dump(TEMP_LOG, f, indent=2)
                            print(f"Temporary log saved to {temp_log_file}")

                # End time tracking for the node
                _node_end_time = time()
                node.time_elapsed = round(_node_end_time - _node_start_time, 2)

                def _backprop_and_save():
                    # MCTS BACKPROPAGATION
                    node.update_counts(visits=1, reward=node.self_value)
                    # Save the new node and its parents' updated counts to JSON files
                    save_mcts_node(node, log_dirname, to_root=True)
                    usage_tracker.save_events(log_dirname)

                if update_mcts_lock is not None:
                    with update_mcts_lock:
                        _backprop_and_save()
                else:
                    _backprop_and_save()

                return node

            if n_threads > 1 and len(next_nodes) > 1:
                # Parallel expansion of nodes
                index_lock = threading.Lock()
                update_mcts_lock = threading.Lock()
                next_node_idx_by_level = defaultdict(
                    int, {level: len(nodes) for level, nodes in nodes_by_level.items()}
                )
                thread_local = threading.local()

                def _get_node_idx(new_level):
                    with index_lock:
                        new_node_idx = next_node_idx_by_level[new_level]
                        next_node_idx_by_level[new_level] += 1
                    return new_node_idx

                def _get_thread_agents():
                    if not hasattr(thread_local, "agent_objs"):
                        thread_id = threading.get_ident()
                        thread_work_dir = os.path.join(work_dir, f"thread_{thread_id}")
                        os.makedirs(thread_work_dir, exist_ok=True)
                        thread_local.agent_objs = get_agents(
                            thread_work_dir,
                            model_name=model_name,
                            temperature=temperature,
                            reasoning_effort=reasoning_effort,
                            branching_factor=branching_factor,
                            user_query=user_query,
                            experiment_first=experiment_first,
                            code_timeout=code_timeout,
                            use_modal_sandbox=use_modal_sandbox,
                            bucket_path=bucket_path,
                            dataset_paths=dataset_paths,
                            vision_model=vision_model,
                            usage_tracker=usage_tracker,
                        )
                    return thread_local.agent_objs

                def _expand_node_parallel(inbatch_idx, node):
                    return _expand_node(
                        inbatch_idx,
                        node,
                        _get_thread_agents(),
                        TreeLogger(log_dirname),
                        _get_node_idx,
                        update_mcts_lock=update_mcts_lock,
                        is_threaded=True,
                    )

                expanded_nodes = []
                with ThreadPoolExecutor(max_workers=n_threads) as executor:
                    future_labels = {
                        executor.submit(_expand_node_parallel, inbatch_idx, node): (
                            f"{node.level}_{node.node_idx}"
                        )
                        for inbatch_idx, node in enumerate(next_nodes)
                    }

                    def _on_expand_error(node_id: str, exc: Exception) -> None:
                        # Keep exploration running when one node expansion fails.
                        print(
                            f"[run_mcts] Failed expanding node {node_id}: "
                            f"{exc.__class__.__name__}: {exc}"
                        )
                        traceback.print_exception(type(exc), exc, exc.__traceback__)

                    expanded_nodes = gather_completed_futures(
                        future_labels,
                        on_error=_on_expand_error,
                    )
            else:
                # Sequential expansion of nodes
                if base_agent_objs is None:
                    base_agent_objs = get_agents(
                        work_dir,
                        model_name=model_name,
                        temperature=temperature,
                        reasoning_effort=reasoning_effort,
                        branching_factor=branching_factor,
                        user_query=user_query,
                        experiment_first=experiment_first,
                        code_timeout=code_timeout,
                        use_modal_sandbox=use_modal_sandbox,
                        bucket_path=bucket_path,
                        dataset_paths=dataset_paths,
                        vision_model=vision_model,
                        usage_tracker=usage_tracker,
                    )

                next_node_idx_by_level = defaultdict(
                    int, {level: len(nodes) for level, nodes in nodes_by_level.items()}
                )

                def _get_node_idx(new_level):
                    new_node_idx = next_node_idx_by_level[new_level]
                    next_node_idx_by_level[new_level] += 1
                    return new_node_idx

                expanded_nodes = []
                for inbatch_idx, node in enumerate(next_nodes):
                    new_node = _expand_node(
                        inbatch_idx,
                        node,
                        base_agent_objs,
                        logger,
                        _get_node_idx,
                    )
                    if new_node is not None:
                        expanded_nodes.append(new_node)

            # Add expanded nodes to the tree
            expanded_nodes.sort(key=lambda n: (n.level, n.node_idx))
            for node in expanded_nodes:
                nodes_by_level[node.level].append(node)
    except KeyboardInterrupt:
        print("\n\n######### EXPLORATION INTERRUPTED! SAVING THE CURRENT STATE... #########\n\n")
    finally:
        clear_ag2_usage_context()
        configure_ag2_usage_tracking(None)

    # End time tracking
    end_time = time()
    time_elapsed = end_time - start_time

    # Save all MCTS nodes
    save_nodes(
        nodes_by_level,
        log_dirname,
        run_dedupe,
        belief_model_name,
        time_elapsed=time_elapsed,
        usage_tracker=usage_tracker,
    )
    usage_tracker.save_events(log_dirname)
    usage_tracker.save_summary(log_dirname)


if __name__ == "__main__":
    parser = ArgParser()
    args = parser.parse_args()
    print("Script arguments:")
    print(args.__dict__, "\n")

    # Validate and fix arguments
    if "o4-mini" in args.model and args.temperature is not None:
        print("Warning: Setting temperature for o4-mini is not permitted. Using default None.")
        args.temperature = None
    if "o4-mini" in args.belief_model and args.belief_temperature is not None:
        print(
            "Warning: Setting temperature for o4-mini belief model is not permitted. Using default None."
        )
        args.belief_temperature = None

    # Create log directory
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_dirname = os.path.join(args.out_dir, timestamp) if args.timestamp_dir else args.out_dir
    work_dirname = os.path.join(args.work_dir, timestamp) if args.timestamp_dir else args.work_dir

    # Setup logger
    logger = TreeLogger(log_dirname)

    # Save args
    args_file = os.path.join(log_dirname, "args.json")
    with open(args_file, "w") as f:
        json.dump(vars(args), f, indent=2)
    print(f"\nArguments saved to {args_file}\n")

    # Get dataset paths
    dataset_paths, dataset_metadata = get_datasets_fpaths(
        args.dataset_metadata, is_blade=args.dataset_metadata_type == "blade"
    )
    load_dataset_experiment = get_load_dataset_experiment(
        dataset_paths,
        dataset_metadata,
        run_eda=args.run_eda,
        dataset_metadata_type=args.dataset_metadata_type,
    )

    if args.continue_from_dir or args.continue_from_json:
        if args.continue_from_dir is not None:
            # Load nodes from a directory
            root, nodes_by_level = load_mcts_from_json(args.continue_from_dir, args)
            # Copy all files except args.json from continue_from_dir to the new log directory
            for filename in os.listdir(args.continue_from_dir):
                if filename != "args.json":
                    shutil.copy(
                        os.path.join(args.continue_from_dir, filename),
                        os.path.join(log_dirname, filename),
                    )
        else:
            # Load from a JSON file that contains all the nodes (not de-duplicated)
            root, nodes_by_level = load_mcts_from_json(args.continue_from_json, args)

        if args.only_save_results:
            # Save nodes to JSON and exit
            save_nodes(nodes_by_level, log_dirname, run_dedupe=args.dedupe, model=args.belief_model)
            exit(0)

        if args.continue_from_dir is not None:
            # Copy all files except args.json from continue_from_dir to the new log directory
            for filename in os.listdir(args.continue_from_dir):
                if filename != "args.json":
                    shutil.copy(
                        os.path.join(args.continue_from_dir, filename),
                        os.path.join(log_dirname, filename),
                    )
        else:
            # Create the individual node files in the log directory
            for node in nodes_by_level.values():
                for n in node:
                    node_file = os.path.join(log_dirname, f"mcts_{n.id}.json")
                    with open(node_file, "w") as f:
                        json.dump(n.to_dict(), f, indent=2)

        # Calculate remaining iterations to reach n_experiments
        total_nodes = sum(len(nodes) for nodes in nodes_by_level.values())
        remaining_iters = (args.n_experiments + 1) - total_nodes  # + 1 to account for root node
        if remaining_iters <= 0:
            print(f"Already reached or exceeded target of {args.n_experiments} experiments")
            exit(0)
        print(
            f"RESUMING: Running {remaining_iters} more experiments to reach the target experiment count of {args.n_experiments}.\n"
        )
    else:
        root = MCTSNode(
            level=0,
            node_idx=0,
            hypothesis=None,
            query=None,
            allow_generate_experiments=False,
            untried_experiments=[load_dataset_experiment],
        )
        nodes_by_level = defaultdict(list)
        nodes_by_level[0].append(root)
        remaining_iters = args.n_experiments + 1  # + 1 to account for root node

    # Set up selection method based on args
    if args.mcts_selection == "pw":
        # Progressive Widening
        assert args.pw_k is not None and args.pw_alpha is not None
        selection_method = progressive_widening(args.pw_k, args.pw_alpha, args.exploration_weight)
    elif args.mcts_selection == "pw_all":
        # Progressive Widening
        assert args.pw_k is not None and args.pw_alpha is not None
        selection_method = progressive_widening_all(
            args.pw_k, args.pw_alpha, args.exploration_weight
        )
    elif args.mcts_selection == "beam_search":
        # Beam Search
        selection_method = beam_search(args.k_experiments, args.beam_width, args.out_dir)
    elif args.mcts_selection == "ucb1":
        # UCB1
        selection_method = default_mcts_selection(args.exploration_weight)
    elif args.mcts_selection == "ucb1_recursive":
        # UCB1 recursive
        selection_method = ucb1_recursive(args.exploration_weight)
    else:
        raise ValueError(f"Unknown MCTS selection method: {args.mcts_selection}")
    print(f"MCTS selection method: {args.mcts_selection}\n")

    # Run exploration
    run_mcts(
        root=root,
        nodes_by_level=nodes_by_level,
        dataset_paths=dataset_paths,
        log_dirname=log_dirname,
        work_dir=work_dirname,
        max_iterations=remaining_iters,
        branching_factor=args.k_experiments,
        selection_method=selection_method,
        allow_generate_experiments=args.allow_generate_experiments,
        n_belief_samples=args.n_belief_samples,
        k_parents=args.k_parents,
        model_name=args.model,
        belief_model_name=args.belief_model,
        temperature=args.temperature,
        belief_temperature=args.belief_temperature,
        reasoning_effort=args.reasoning_effort,
        belief_reasoning_effort=args.belief_reasoning_effort,
        implicit_bayes_posterior=args.implicit_bayes_posterior,
        surprisal_width=args.surprisal_width,
        user_query=args.user_query,
        belief_mode=args.belief_mode,
        use_binary_reward=args.use_binary_reward,
        run_dedupe=args.dedupe,
        experiment_first=args.experiment_first,
        code_timeout=args.code_timeout,
        n_warmstart=args.n_warmstart,
        use_online_beliefs=args.use_online_beliefs,
        evidence_weight=args.evidence_weight,
        kl_scale=args.kl_scale,
        reward_mode=args.reward_mode,
        warmstart_experiments=args.warmstart_experiments,
        use_modal_sandbox=args.use_modal_sandbox,
        bucket_path=args.bucket_path,
        vision_model=args.vision_model,
        batch_size=args.batch_size,
        n_threads=args.n_threads,
        agent_usage_mode=args.agent_usage_mode,
    )

    if args.delete_work_dir:
        shutil.rmtree(args.work_dir)
        print(f"\nDELETED WORKING DIRECTORY: {args.work_dir}")

    print(f"\nRUN FINISHED!\n\nLOGS: {log_dirname}")
