import argparse
import copy
import json
import random

import numpy as np
from pydantic import BaseModel, Field
from scipy.cluster.hierarchy import linkage
from tqdm import tqdm

from autodiscovery import llm
from autodiscovery.llm_usage import UsageTracker
from autodiscovery.utils import query_llm


class ArgParser(argparse.ArgumentParser):
    def __init__(self, group=None):
        """Initialize the argument parser for deduplication runs."""
        super().__init__(description="Get surprising nodes from MCTS logs")
        self.add_argument(
            "--in_fpath",
            type=str,
            required=True,
            help="mcts_nodes.json file path or directory containing mcts_node_*.json files",
        )
        self.add_argument("--out_fpath", type=str, help="output directory for clusters and labels")
        self.add_argument(
            "--n_samples", type=int, default=30, help="Number of samples for LLM decisions"
        )
        self.add_argument(
            "--merge_threshold",
            type=float,
            default=0.7,
            help="Threshold for merging hypotheses based on LLM decisions",
        )
        self.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
        self.add_argument(
            "--model",
            type=str,
            default="vertex_ai/gemini-3.7-flash",
            help="LLM model for hypothesis merging decisions, as litellm's <provider>/<model>.",
        )
        self.add_argument(
            "--embedding_model",
            type=str,
            default="openai/text-embedding-3-large",
            help="Embedding model for candidate clustering, as litellm's <provider>/<model>.",
        )
        self.add_argument(
            "--n_nodes",
            type=int,
            default=None,
            help="Number of nodes to process. If None, all nodes are processed.",
        )
        self.add_argument(
            "--verbose",
            action=argparse.BooleanOptionalAction,
            default=False,
            help="Whether to print verbose output during deduplication process.",
        )


def hyp_dict_to_str(d):
    """Render a hypothesis dictionary into a readable string.

    Args:
        d: Hypothesis dictionary.

    Returns:
        String representation of the hypothesis fields.
    """
    return (
        f"Hypothesis: {d.get('hypothesis', 'N/A')}\n"
        f"Contexts: {d.get('contexts', d.get('context', 'N/A'))}\n"
        f"Variables: {d.get('variables', 'N/A')}\n"
        f"Relationships: {d.get('relationships', 'N/A')}"
    )


def get_structured_hypothesis(node):
    """Extract a structured hypothesis payload from a node.

    Args:
        node: Node dictionary.

    Returns:
        Structured hypothesis dictionary or None when missing.
    """
    level, node_idx = node.get("level"), node.get("node_idx")
    h = node.get("hypothesis", None)
    if h is None:
        return None
    hyp_str = h.get("hypothesis", "")
    dims = h.get("dimensions", {"contexts": [], "variables": [], "relationships": []})
    return {"node_id": f"node_{level}_{node_idx}", "hypothesis": hyp_str, **dims}


def get_structured_hypotheses(in_nodes_list):
    """Collect structured hypotheses from a list of nodes.

    Args:
        in_nodes_list: List of node dictionaries.

    Returns:
        List of structured hypothesis dictionaries.
    """
    node_list = [
        hyp_obj
        for node in in_nodes_list
        if (hyp_obj := get_structured_hypothesis(node)) is not None
    ]
    return node_list


def get_hypothesis(node):
    """Extract a hypothesis payload from a node.

    Args:
        node: Node dictionary.

    Returns:
        Hypothesis dictionary or None when missing.
    """
    h = node.get("hypothesis", None)
    if h is None:
        return None
    node_id = node["id"]
    return {"node_id": node_id, "hypothesis": h}


def get_hypotheses(in_nodes_list):
    """Collect hypothesis payloads from a list of nodes.

    Args:
        in_nodes_list: List of node dictionaries.

    Returns:
        List of hypothesis dictionaries.
    """
    node_list = [hyp_obj for node in in_nodes_list if (hyp_obj := get_hypothesis(node)) is not None]
    return node_list


def get_embedding(
    texts,
    model,
    dimensions=None,
    batch_size=128,
    n_attempts=1,
    usage_tracker: UsageTracker | None = None,
):
    """Compute embeddings for a list of texts.

    Args:
        texts (list): A list of text strings to be embedded.
        model (str): Embedding model, as litellm's ``<provider>/<model>``.
        dimensions: Optional output dimensions for providers that support it.
        batch_size (int, optional): The number of texts to process in one API call.
        n_attempts: Number of attempts before giving up.
        usage_tracker: Optional usage tracker for embedding requests.

    Returns:
        numpy.ndarray: An array of embeddings for the input texts.
    """
    kwargs = {} if dimensions is None else {"dimensions": dimensions}

    for attempt in range(n_attempts):
        try:
            all_embeddings = []
            for i in range(0, len(texts), batch_size):
                response = llm.embed(model, texts[i : i + batch_size], **kwargs)
                if usage_tracker is not None:
                    usage_tracker.record_response(
                        response,
                        source=llm.provider_of(model),
                        component="dedupe.embeddings",
                        agent_name="dedupe",
                    )
                all_embeddings.extend(np.array(item["embedding"]) for item in response.data)
            return np.array(all_embeddings)
        except Exception as exc:
            if attempt < n_attempts - 1:
                print(f"Embeddings: Attempt {attempt + 1} failed: {exc}. Retrying...")
            else:
                raise RuntimeError(
                    f"Failed to get embeddings after {n_attempts} attempts."
                ) from exc


def get_llm_merge_decision(
    hyp1: str,
    hyp2: str,
    *,
    model: str,
    n_samples: int = 30,
    threshold: float = 0.7,
    temperature: float = 1.0,
    reasoning_effort: str = "medium",
    usage_tracker: UsageTracker | None = None,
):
    """Determine whether two hypotheses are semantically equivalent.

    Args:
        hyp1: First hypothesis string.
        hyp2: Second hypothesis string.
        n_samples: Number of LLM samples to draw.
        threshold: Proportion threshold for merging decisions.
        model: LLM model, as litellm's ``<provider>/<model>``.
        temperature: Sampling temperature.
        reasoning_effort: Reasoning effort for the model.
        usage_tracker: Optional usage tracker for merge decision calls.

    Returns:
        True if the hypotheses should be merged, False otherwise.
    """

    class ResponseFormat(BaseModel):
        is_same: bool = Field(..., description="Whether the two hypotheses are the same or not.")

    system_prompt = "You are a research scientist skilled at analyzing statistical hypotheses."
    prompt = (
        f"You are given two hypotheses. Your task is to determine whether the two hypotheses are semantically the same or not. "
        f"Carefully consider the meaning, context, and implications of each hypothesis. "
        f"If there is an additional or different clause/condition in one hypothesis that is not present in the other, consider them different.\n\n"
        f"HYPOTHESIS 1:\n{hyp1}\n\nHYPOTHESIS 2:\n{hyp2}"
    )
    all_msgs = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
    response = query_llm(
        all_msgs,
        model=model,
        n_samples=n_samples,
        temperature=temperature,
        reasoning_effort=reasoning_effort,
        response_format=ResponseFormat,
        usage_tracker=usage_tracker,
        usage_component="dedupe.merge",
        usage_agent_name="dedupe",
    )
    true_prop = sum([1 for _res in response if _res["is_same"]]) / n_samples

    return true_prop >= threshold


def dedupe(
    nodes_or_json_path,
    *,
    model,
    embedding_model,
    n_samples=10,
    merge_threshold=0.7,
    seed=42,
    rep_mode="biggest",
    embedding_dimensions=None,
    n_nodes=None,
    verbose=False,
    log_comparisons_fname=None,
    usage_tracker: UsageTracker | None = None,
):
    """Deduplicate hypotheses using embeddings + LLM similarity checks.

    Args:
        nodes_or_json_path: Nodes list or path to nodes JSON.
        n_samples: Number of LLM samples per comparison.
        merge_threshold: Merge threshold for LLM votes.
        seed: Random seed.
        rep_mode: Representative selection mode for merged clusters.
        model: LLM model, as litellm's ``<provider>/<model>``.
        embedding_model: Embedding model, as litellm's ``<provider>/<model>``.
        embedding_dimensions: Optional embedding dimensions override.
        n_nodes: Optional cap on nodes processed.
        verbose: Whether to print verbose details.
        log_comparisons_fname: Optional JSON path to log LLM comparisons.
        usage_tracker: Optional usage tracker.

    Returns:
        Tuple of (deduplicated nodes list, duplicates mapping).
    """
    random.seed(seed)
    np.random.seed(seed)

    from autodiscovery.mcts_utils import get_nodes  # Importing here to avoid circular import issues

    nodes_list = get_nodes(nodes_or_json_path)[:n_nodes]
    # Remove nodes without hypotheses
    nodes_list = [node for node in nodes_list if node.get("hypothesis", None) is not None]

    dedup_hyp, hyp_to_index, orig_to_dedup = [], {}, []

    # Deduplicate hypotheses by exact match
    for node in nodes_list:
        hyp = node["hypothesis"]  # Hypothesis string
        if hyp not in hyp_to_index:
            hyp_to_index[hyp] = len(dedup_hyp)
            dedup_hyp.append(hyp)
        orig_to_dedup.append(hyp_to_index[hyp])
    n_dedup = len(dedup_hyp)

    # Generate embeddings for deduplicated hypotheses
    embeds = np.array(
        get_embedding(
            dedup_hyp,
            model=embedding_model,
            dimensions=embedding_dimensions,
            n_attempts=3,
            usage_tracker=usage_tracker,
        )
    )

    # Initialize assignment structures
    clusters = {i: [i] for i in range(n_dedup)}
    cluster_assignment = {i: i for i in range(n_dedup)}
    hac_to_current = {i: i for i in range(n_dedup)}
    cluster_rep = {i: i for i in range(n_dedup)}

    # Map dedup indices back to original node indices (for duplicates output).
    dedup_to_orig = {i: [] for i in range(n_dedup)}
    for orig_idx, dedup_idx in enumerate(orig_to_dedup):
        dedup_to_orig[dedup_idx].append(orig_idx)

    def build_output_from_clusters(in_clusters, in_cluster_rep):
        """Build deduplicated nodes and duplicates mapping from clusters."""
        deduped_nodes, duplicates = [], {}
        for cluster_id, cluster in in_clusters.items():
            rep_dedup_idx = in_cluster_rep[cluster_id]
            rep_orig_idx = dedup_to_orig[rep_dedup_idx][0]
            node_copy = copy.deepcopy(nodes_list[rep_orig_idx])
            dup_orig_indices = []
            for dedup_idx in cluster:
                for orig_idx in dedup_to_orig[dedup_idx]:
                    if orig_idx != rep_orig_idx:
                        dup_orig_indices.append(orig_idx)
            node_copy["duplicate_nodes"] = [nodes_list[i]["id"] for i in dup_orig_indices]
            duplicates[node_copy["id"]] = node_copy["duplicate_nodes"]
            deduped_nodes.append(node_copy)
        return deduped_nodes, duplicates

    if n_dedup < 2:
        return build_output_from_clusters(clusters, cluster_rep)

    # Perform HAC over LM embeddings and get the linkage matrix
    linkage_matrix = linkage(embeds, method="ward")

    # Iterate through the linkage matrix to additionally merge clusters based on LLM decisions
    pbar = tqdm(linkage_matrix, desc="Deduplicating")
    pbar.set_postfix({"n_clusters": len(clusters)})
    llm_comparisons = []
    for r, row in enumerate(pbar):
        hac_node_id = n_dedup + r
        left_hac, right_hac = int(row[0]), int(row[1])
        left_current = hac_to_current.get(left_hac)
        right_current = hac_to_current.get(right_hac)
        if left_current is None or right_current is None or left_current == right_current:
            hac_to_current[hac_node_id] = (
                left_current if left_current is not None else right_current
            )
            continue
        rep_left, rep_right = cluster_rep[left_current], cluster_rep[right_current]
        # struct_left, struct_right = dedup_struct_hyp[rep_left], dedup_struct_hyp[rep_right]
        struct_left, struct_right = dedup_hyp[rep_left], dedup_hyp[rep_right]
        # Get the LLM merge decision
        llm_decision = get_llm_merge_decision(
            struct_left,
            struct_right,
            n_samples=n_samples,
            threshold=merge_threshold,
            model=model,
            usage_tracker=usage_tracker,
        )
        if verbose:
            print(f"""\n\n
Cluster left (size: {len(clusters[left_current])}):
{struct_left}

Cluster right (size: {len(clusters[right_current])}):
{struct_right}

LLM Decision: {"Merge" if llm_decision else "Do not merge"}\n\n""")
        if log_comparisons_fname is not None:
            llm_comparisons.append(
                {
                    "left_size": len(clusters[left_current]),
                    "right_size": len(clusters[right_current]),
                    "left_hypothesis": struct_left,
                    "right_hypothesis": struct_right,
                    "llm_decision": llm_decision,
                }
            )

        if llm_decision:
            if rep_mode == "random":
                new_rep = random.choice([rep_left, rep_right])
            elif rep_mode == "biggest":
                new_rep = (
                    rep_left
                    if len(clusters[left_current]) >= len(clusters[right_current])
                    else rep_right
                )
            else:
                raise NotImplementedError
            merged_cluster_id = min(left_current, right_current)
            other_cluster_id = max(left_current, right_current)
            clusters[merged_cluster_id] += clusters[other_cluster_id]
            for idx in clusters[merged_cluster_id]:
                cluster_assignment[idx] = merged_cluster_id
            cluster_rep[merged_cluster_id] = new_rep
            del clusters[other_cluster_id]
            del cluster_rep[other_cluster_id]
            hac_to_current[hac_node_id] = merged_cluster_id
        else:
            hac_to_current[hac_node_id] = None

        # Update pbar with number of clusters
        pbar.set_postfix({"n_clusters": len(clusters)})

    if log_comparisons_fname is not None:
        with open(log_comparisons_fname, "w") as f:
            json.dump(llm_comparisons, f, indent=2)
        print(f"LLM comparisons logged to {log_comparisons_fname}")

    # Return final deduplicated nodes and the list of clusters
    return build_output_from_clusters(clusters, cluster_rep)


if __name__ == "__main__":
    parser = ArgParser()
    args = parser.parse_args()
    deduped_nodes, clusters = dedupe(
        nodes_or_json_path=args.in_fpath,
        n_samples=args.n_samples,
        merge_threshold=args.merge_threshold,
        seed=args.seed,
        model=args.model,
        embedding_model=args.embedding_model,
        n_nodes=args.n_nodes,
        verbose=args.verbose,
    )
    print("Clusters:", clusters)

    if args.out_fpath is not None:
        # Save the results to the output file
        output_data = {"clusters": clusters, "deduped_nodes": deduped_nodes}
        with open(args.out_fpath, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"Results saved to {args.out_fpath}")
