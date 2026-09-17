"""Tests for the experiment list/detail serialization contract.

The list endpoint is polled for the whole tree, so its payload must stay bounded:
`code`/`code_output` are detail-only and the page is capped.
"""

from autodiscovery_jobs import JobConfig
from utils.experiments import EXPERIMENT_PAGE_SIZE, ExperimentNode, ExperimentTree


def make_node(idx: int) -> ExperimentNode:
    return ExperimentNode(
        {
            "id": f"node_0_{idx}",
            "parent_id": None if idx == 0 else "node_0_0",
            "creation_idx": idx,
            "hypothesis": f"hypothesis {idx}",
            "code": "print('x')",
            "code_output": "x" * 1024,
            "success": True,
        },
        f"mcts_node_0_{idx}.json",
    )


def make_tree(count: int) -> ExperimentTree:
    return ExperimentTree(
        userid="user",
        jobid="job",
        config=JobConfig(bucket="bucket", project_id="project"),
        nodes=[make_node(i) for i in range(count)],
    )


def test_to_dict_omits_code_fields_by_default():
    node = make_node(0)

    payload = node.to_dict()

    assert "code" not in payload
    assert "code_output" not in payload
    assert payload["hypothesis"] == "hypothesis 0"


def test_to_dict_includes_code_fields_on_request():
    node = make_node(0)

    payload = node.to_dict(include_code=True)

    assert payload["code"] == "print('x')"
    assert payload["code_output"] == "x" * 1024


def test_list_payload_excludes_code_fields():
    tree = make_tree(3)

    payloads = tree.to_experiment_models()

    assert len(payloads) == 3
    assert all("code" not in payload for payload in payloads)
    assert all("code_output" not in payload for payload in payloads)


def test_to_experiment_models_respects_limit():
    tree = make_tree(5)

    payloads = tree.to_experiment_models(limit=2)

    assert [payload["experiment_id"] for payload in payloads] == ["node_0_0", "node_0_1"]


def test_count_reflects_exclusions_so_paging_can_detect_more():
    tree = make_tree(5)

    assert tree.count() == 5
    assert tree.count(exclude_experiment_ids=["node_0_0", "node_0_1"]) == 3


def test_paging_with_known_ids_drains_the_tree():
    tree = make_tree(5)
    known: list[str] = []

    pages = 0
    while tree.count(exclude_experiment_ids=known) > 0:
        page = tree.to_experiment_models(exclude_experiment_ids=known, limit=2)
        known.extend(payload["experiment_id"] for payload in page)
        pages += 1
        assert pages <= 5, "paging failed to make forward progress"

    assert sorted(known) == [f"node_0_{i}" for i in range(5)]


def test_page_size_is_bounded():
    assert 0 < EXPERIMENT_PAGE_SIZE <= 1000
