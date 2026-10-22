"""Tests for the experiment list/detail serialization contract.

The list endpoint is polled for the whole tree, so `code`/`code_output` —
unbounded captured source and stdout — are detail-only.
"""

from autodiscovery import report
from autodiscovery_jobs import JobConfig
from runs.models import ExperimentModel
from utils.experiments import ExperimentNode, ExperimentTree


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


def test_html_report_serializes_experiments_as_the_api_does():
    """The standalone HTML report renders the web UI's run view from data it writes
    itself (autodiscovery/report.py), so its experiments must match the detail
    route's, field for field."""
    raw = [
        {"id": "node_1_0", "parent_id": None, "creation_idx": 1, "success": True},
        {
            "id": "node_2_0",
            "parent_id": "node_1_0",
            "creation_idx": 2,
            "success": False,
            "surprising": True,
            "normalized_surprisal": 0.4,
            "prior": {"_type": "boolean_cat", "mean": 0.2},
            "posterior": {"_type": "boolean_cat", "mean": 0.7},
            "time_elapsed": 1.5,
            "hypothesis": "h",
            "analysis": "a",
            "experiment_plan": {"objective": "o"},
            "review": "r",
            "code": "c",
            "code_output": "o",
            "created_at": "2026-01-01T00:00:00+00:00",
        },
        {"id": "node_2_1", "parent_id": "node_1_0", "creation_idx": 3, "hypothesis": "p"},
    ]
    tree = ExperimentTree(
        userid="user",
        jobid="job",
        config=JobConfig(bucket="bucket", project_id="project"),
        nodes=[ExperimentNode(n, f"mcts_{n['id']}.json") for n in raw],
    )
    api = [
        ExperimentModel(**d).model_dump(exclude={"rich_outputs"})
        for d in tree.to_experiment_models(include_code=True)
    ]

    html_report = report._experiments(raw, {})
    for experiment in html_report:
        experiment.pop("rich_outputs")

    assert html_report == api
