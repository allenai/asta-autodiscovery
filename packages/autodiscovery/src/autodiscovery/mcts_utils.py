import json
import os
from collections import defaultdict
from glob import glob
from typing import Literal

import regex as re
from autogen import GroupChat, GroupChatManager

from autodiscovery.deduplication import dedupe
from autodiscovery.nodes_to_csv import nodes_to_csv
from autodiscovery.transitions import SpeakerSelector


def load_mcts_from_json(json_obj_or_file_or_dir, args=None, replay_mcts=True):
    """Load and reconstruct MCTS nodes from a JSON object, log file, or directory.

    Args:
        json_obj_or_file_or_dir: Loaded JSON object or a path to the mcts_nodes.json file or to a directory with mcts_node_*.json files.

    Returns:
        root: Root MCTSNode
        nodes_by_level: Dictionary mapping levels to lists of MCTSNodes
    """
    from autodiscovery.mcts import MCTSNode  # Import here to avoid circular import issues

    node_data = get_nodes(json_obj_or_file_or_dir)

    # Initialize tree data structures
    nodes_by_level = defaultdict(list)
    node_map = {}  # Map (level, idx) to node objects for linking

    # Iterate over the nodes in level order and build the tree
    node_data.sort(key=lambda x: (int(x["id"].split("_")[1]), int(x["id"].split("_")[2])))
    for data in node_data:
        # Create an empty node and initialize from dict (parent links added in second pass)
        node = MCTSNode(
            allow_generate_experiments=args.allow_generate_experiments if args else True
        )
        node.init_from_dict(data)
        # Add to data structures
        nodes_by_level[node.level].append(node)
        node_map[(node.level, node.node_idx)] = node
        # Link to parent
        if node.parent_id is not None:
            parent_level = node.level - 1
            parent_idx = node.parent_idx
            try:
                node.parent = node_map[(parent_level, parent_idx)]
                node.parent.children.append(node)
            except KeyError:
                assert (parent_level, parent_idx) == (0, 0), (
                    f"Parent node ({parent_level}, {parent_idx}) not found in node_map."
                )

    # Create root node if it does not exist
    if (0, 0) not in node_map:
        node = MCTSNode(level=0, node_idx=0, creation_idx=0)
        nodes_by_level[0].append(node)  # Figure out creation_idx use
        node_map[(0, 0)] = node
        # Link root to the tree
        node.children = [node_map[(1, 0)]]
        node_map[(1, 0)].parent = node

    assert len(node_map) == MCTSNode._creation_counter
    root = node_map[(0, 0)]

    # Fix tried/untried experiments
    for node in node_map.values():
        _tried_experiments, _untried_experiments = [], []
        cur_untried_experiments = set(
            list(map(get_query_from_experiment, node.untried_experiments))
        )
        for child in node.children:
            # Keep only children in tried experiments
            _tried_experiments.append(get_experiment_from_query(child.query))
            # Remove child from untried experiments if exists
            if child.query in cur_untried_experiments:
                cur_untried_experiments.remove(child.query)
        _untried_experiments = list(map(get_experiment_from_query, list(cur_untried_experiments)))
        node.tried_experiments = _tried_experiments
        node.untried_experiments = _untried_experiments

    if replay_mcts:
        # Replay MCTS to assign correct visits and values in order of creation_idx
        _nodes = sorted(node_map.values(), key=lambda x: x.creation_idx)
        # Reset visits and value
        for _node in _nodes:
            _node.visits = 0
            _node.value = 0
        # Backpropagate visits and values
        for _node in _nodes:
            _node.update_counts(visits=1, reward=_node.self_value)

    return root, nodes_by_level


def save_nodes(
    nodes_dict_or_list,
    log_dirname,
    run_dedupe=True,
    model="gpt-4o",
    save_csv=True,
    time_elapsed=None,
    usage_tracker=None,
):
    """Save MCTS nodes to JSON and optionally to CSV.

    Args:
        nodes_dict_or_list: Dictionary or list of MCTSNode objects or dicts.
        log_dirname: Directory to save the JSON and CSV files.
        run_dedupe: Whether to deduplicate nodes based on hypothesis.
        model: Model to use for deduplication.
        save_csv: Whether to save nodes to a CSV file.
        time_elapsed: Optional time elapsed for logging purposes.
        usage_tracker: Optional usage tracker for dedupe-related LLM calls.
    """
    from autodiscovery.mcts import MCTSNode  # Import here to avoid circular import issues

    if type(nodes_dict_or_list) in [dict, defaultdict]:
        nodes_list = []
        for level, nodes in nodes_dict_or_list.items():
            if level == 0:
                continue
            for node in nodes:
                nodes_list.append(node.to_dict())
    else:
        nodes_list = nodes_dict_or_list
        if type(nodes_list[0]) is MCTSNode:
            # Convert MCTSNode objects to dicts
            nodes_list = [node.to_dict() for node in nodes_list]

    # Save nodes to JSON
    nodes_list = save_nodes_to_json(
        nodes_list,
        log_dirname,
        run_dedupe=run_dedupe,
        dedupe_model=model,
        time_elapsed=time_elapsed,
        usage_tracker=usage_tracker,
    )

    # Save nodes to CSV
    if save_csv:
        csv_output_file = os.path.join(log_dirname, "mcts_nodes.csv")
        nodes_to_csv(nodes_list, csv_output_file)


def save_nodes_to_json(
    nodes_list,
    log_dirname,
    run_dedupe=True,
    dedupe_model="gpt-4o",
    log_dedupe_comparisons=False,
    time_elapsed=None,
    usage_tracker=None,
):
    """Save all MCTS nodes to a JSON file.

    Args:
        nodes_list: List of MCTS node objects.
        log_dirname: Directory to save the JSON file
        run_dedupe: Whether to deduplicate nodes based on hypothesis.
        dedupe_model: Model to use for deduplication.
        log_dedupe_comparisons: Whether to log deduplication comparisons to a file.
        time_elapsed: Optional time elapsed for logging purposes.
        usage_tracker: Optional usage tracker for dedupe-related LLM calls.
    """
    # Optionally deduplicate nodes based on hypothesis
    if run_dedupe:
        deduped_nodes, duplicates = dedupe(
            nodes_list,
            model=dedupe_model,
            log_comparisons_fname=None
            if not log_dedupe_comparisons
            else os.path.join(log_dirname, "dedupe_log.json"),
            verbose=False,
            usage_tracker=usage_tracker,
        )
        file_to_save = deduped_nodes
        nonempty_clusters = {k: v for k, v in duplicates.items() if len(v) > 0}
        if len(nonempty_clusters) > 0:
            print(f"\n[DEDUPE] Deduplicated MCTS nodes to n={len(deduped_nodes)}.\nMerged nodes:")
            print(json.dumps(nonempty_clusters, indent=2))
        else:
            print("\n[DEDUPE] No duplicate MCTS nodes found.")

        with open(os.path.join(log_dirname, "duplicate_nodes.json"), "w") as f:
            # Add hypothesis texts for each node in the clusters
            _hyp_by_node_id = {node["id"]: node["hypothesis"] for node in nodes_list}
            for cluster_id, node_ids in nonempty_clusters.items():
                nonempty_clusters[cluster_id] = {
                    "hypothesis": _hyp_by_node_id[cluster_id],
                    "duplicates": [
                        {"node_id": nid, "hypothesis": _hyp_by_node_id[nid]} for nid in node_ids
                    ],
                }
            json.dump(nonempty_clusters, f, indent=2)
            print(
                f"[DEDUPE] Duplicates saved to {os.path.join(log_dirname, 'duplicate_nodes.json')}."
            )
    else:
        file_to_save = nodes_list

    output_file = os.path.join(log_dirname, "mcts_nodes.json")
    with open(output_file, "w") as f:
        json.dump(file_to_save, f, indent=2)
    print(f"[JSON] MCTS nodes (n={len(file_to_save)}) saved to {output_file}.\n")
    # Also save the original nodes list for reference
    original_nodes_file = os.path.join(log_dirname, "mcts_nodes_all.json")
    with open(original_nodes_file, "w") as f:
        json.dump(nodes_list, f, indent=2)
    print(f"[JSON] Original MCTS nodes (n={len(nodes_list)}) saved to {original_nodes_file}.\n")
    if time_elapsed is not None:
        print(f"[Exploration] Time elapsed: {time_elapsed:.2f} seconds.\n")
    return file_to_save


def get_msgs_from_latest_query(messages):
    # Find last user_proxy message by iterating in reverse
    start_idx = None
    for i, message in enumerate(reversed(messages)):
        if message.get("name") == "user_proxy":
            start_idx = len(messages) - 1 - i
            break
    if start_idx is None:
        return []
    node_messages = messages[start_idx:]
    return node_messages


def setup_group_chat(agents, max_rounds):
    # Set up the group chat with agents and rules
    group_chat = GroupChat(
        agents=list(agents.values()),
        messages=[],
        max_round=max_rounds,
        speaker_selection_method=SpeakerSelector().select_next_speaker,
    )
    chat_manager = GroupChatManager(groupchat=group_chat, llm_config=None)
    return group_chat, chat_manager


def select_nodes(selection_method, root, nodes_by_level, n_warmstart=0, return_n=1):
    """Select the next nodes to expand in MCTS using the provided selection method.

    Args:
        selection_method: Function to select nodes in MCTS.
        root: Root MCTSNode to select from.
        nodes_by_level: Dictionary of nodes by level.
        n_warmstart: Number of warmstart experiments to run after data loading but before MCTS selection.
        return_n: Number of nodes to return.

    Returns:
        List of selected MCTSNode instances for expansion.
    """
    # If the data loader node hasn't been executed, return the root. This is not run in batch mode.
    if len(nodes_by_level[1]) == 0:
        return [root]

    # If there are warmstart experiments left to run, select the data loader node.
    n_children_at_data_loader = len(nodes_by_level[2])
    if (n_warmstart - n_children_at_data_loader) > 0:
        return [nodes_by_level[1][0]] * min(return_n, n_warmstart - n_children_at_data_loader)

    # Otherwise, use the selection policy to select the next nodes.
    try:
        selected = selection_method(root, nodes_by_level, return_n=return_n)
    except TypeError:
        selected = selection_method(root, nodes_by_level)
    return_nodes = selected if isinstance(selected, list) else [selected]
    if len(return_nodes) == 0:
        return []
    # Repeat return_nodes sequentially if needed to fill the batch
    return_nodes = (
        return_nodes * (return_n // len(return_nodes))
        + return_nodes[: return_n % len(return_nodes)]
    )
    return return_nodes


def save_mcts_node(node, log_dirname, to_root=False, root_id="node_1_0"):
    """Save an MCTS node to JSON and optionally persist parent updates.

    Args:
        node: MCTSNode to save.
        log_dirname: Directory to save node JSON files.
        to_root: Whether to recursively save parent nodes up to the root.
        root_id: Root node id used to stop recursion.
    """
    if node is None:
        return
    node_file = os.path.join(log_dirname, f"mcts_{node.id}.json")
    with open(node_file, "w") as f:
        json.dump(node.to_dict(), f, indent=2)
    if to_root and node.id != root_id:
        save_mcts_node(node.parent, log_dirname, to_root=to_root, root_id=root_id)


def get_nodes(in_fpath_or_json: str | list[dict[str, any]]) -> list[dict[str, any]] | None:
    """Load MCTS nodes from a file, directory, or a list of dictionaries without creating class objects.

    Args:
        in_fpath_or_json: Path to the MCTS nodes JSON file, a directory containing MCTS node files, or a list of MCTS nodes as dictionaries.

    Returns:
        List of MCTS nodes as dictionaries.
    """
    if type(in_fpath_or_json) is list:
        mcts_nodes = in_fpath_or_json
    else:
        # Load the MCTS nodes from the input file
        if os.path.isdir(in_fpath_or_json):
            mcts_nodes = []
            filenames = glob(os.path.join(in_fpath_or_json, "mcts_node_*.json"))
            for filename in filenames:
                with open(filename) as f:
                    obj = json.load(f)
                    mcts_nodes.append(obj)
        else:
            with open(in_fpath_or_json) as f:
                mcts_nodes = json.load(f)
    return mcts_nodes


def print_node_info(node):
    prior_mean = node.prior.get_mean_belief()
    posterior_mean = node.posterior.get_mean_belief(prior=node.prior)
    direction = (
        "+" if posterior_mean > prior_mean else ("-" if posterior_mean < prior_mean else "=")
    )
    print(f"""\n\n\
================================================================================

NODE_LEVEL={node.level}, NODE_IDX={node.node_idx}:
-------------------------

Hypothesis: {node.hypothesis}
Prior: {prior_mean:.4f}
Posterior: {posterior_mean:.4f}
Surprisal: {node.surprising}
Belief Change: {node.belief_change:.4f} ({direction})
KL Divergence: {node.kl_divergence:.4f}
Reward: {node.self_value:.4f}

================================================================================\n\n""")


def get_query_from_experiment(exp):
    hypothesis = exp["hypothesis"]
    exp_plan = exp["experiment_plan"]
    new_query = ""
    if hypothesis is not None:
        new_query += f"Hypothesis: {hypothesis}\n\n"
    new_query += f"""\
Experiment objective: {exp_plan["objective"]}

Steps for the programmer:
{exp_plan["steps"]}

Deliverables:
{exp_plan["deliverables"]}"""
    return new_query


def get_experiment_from_query(query):
    # Extract the hypothesis and experiment plan from the query
    hypothesis_match = re.search(r"Hypothesis:\s*(.*)", query)
    hypothesis = hypothesis_match.group(1).strip() if hypothesis_match else None

    exp_plan_match = re.search(r"Experiment objective:\s*(.*?)(?=\n\n|$)", query, re.DOTALL)
    exp_plan = exp_plan_match.group(1).strip() if exp_plan_match else None

    steps_match = re.search(r"Steps for the programmer:\s*(.*?)(?=\n\n|$)", query, re.DOTALL)
    steps = steps_match.group(1).strip() if steps_match else None

    deliverables_match = re.search(r"Deliverables:\s*(.*?)(?=\n\n|$)", query, re.DOTALL)
    deliverables = deliverables_match.group(1).strip() if deliverables_match else None

    return {
        "hypothesis": hypothesis,
        "experiment_plan": {"objective": exp_plan, "steps": steps, "deliverables": deliverables},
    }


def get_node_level_idx(node_or_id):
    from autodiscovery.mcts import MCTSNode

    # Get the level and index of a node from its ID (e.g., "node_<level>_<idx>") or MCTSNode/dict.
    if type(node_or_id) is MCTSNode:
        id = node_or_id.id
    elif type(node_or_id) is dict:
        id = node_or_id["id"]
    elif type(node_or_id) is str:
        id = node_or_id

    return map(int, id.split("_")[1:])


def get_context_string(
    hyp_exp_query,
    code_output=None,
    analysis=None,
    review=None,
    belief_mean=None,
    include_code_output=False,
):
    # Format the experiment to include as context in, e.g., an LLM call.
    context_str = hyp_exp_query
    if include_code_output and code_output is not None:
        context_str += f"\n\nCode Output:\n{code_output}"
    if analysis is not None:
        context_str += f"\n\nAnalysis:\n{analysis}"
    if review is not None:
        context_str += f"\n\nReview:\n{review}"
    if belief_mean is not None:
        context_str += f"\n\nBelief about this hypothesis (range 0-1: definitely false -> uncertain -> definitely true): {belief_mean:.4f}"

    return context_str


def get_self_value(
    belief_change,
    kl_divergence,
    binary=True,
    width=0.2,
    kl_scale=20.0,
    mode: Literal["belief", "kl", "belief_and_kl"] = "belief_and_kl",
):
    """Get self value for a node based on its belief.

    Args:
        belief_change (float): Change in belief from prior to posterior.
        kl_divergence (float): KL divergence between prior and posterior beliefs.
        binary (bool): Whether the surprisal reward is binary or continuous.
        width (float): Surprisal width for belief change.
        kl_scale (float): Normalization factor for KL divergence.
        mode (str): Mode to use for self value calculation. Choices: "belief", "kl", "both".

    Returns:
        float: Self value based on the belief type.
        bool: Whether it is a surprisal.
    """
    if mode == "belief":
        if binary:
            return float(belief_change >= width), bool(belief_change >= width)
        else:
            # Continuous reward normalized by the surprisal width
            return belief_change / width, bool((belief_change / width) >= 1.0)
    elif mode == "kl":
        # KL divergence reward normalized by the KL scale
        if binary:
            return float(kl_divergence >= kl_scale), bool(kl_divergence >= kl_scale)
        else:
            return kl_divergence / kl_scale, bool((kl_divergence / kl_scale) >= 1.0)
    elif mode == "belief_and_kl":
        # Satisfy both modes
        belief_value, is_surprising_belief = get_self_value(
            belief_change, kl_divergence, binary, width, kl_scale, mode="belief"
        )
        kl_value, is_surprising_kl = get_self_value(
            belief_change, kl_divergence, binary, width, kl_scale, mode="kl"
        )
        # Combine both values
        combined_value = max(belief_value, kl_value)
        is_surprising = bool(is_surprising_belief or is_surprising_kl)
        return combined_value, is_surprising

    raise ValueError(f"Invalid mode: {mode}. Choose from 'belief', 'kl', or 'belief_and_kl'.")
