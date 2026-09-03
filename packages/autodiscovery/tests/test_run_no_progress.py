"""Exploration must stop -- not spin -- when node expansion keeps failing."""

import json
from collections import defaultdict

import pytest
from autodiscovery import run as run_module
from autodiscovery.mcts import MCTSNode
from autodiscovery.mcts_utils import select_nodes
from autodiscovery.run import NoProgressError, run_mcts

LOAD_DATASET_EXPERIMENT = {
    "hypothesis": None,
    "experiment_plan": {
        "objective": "Load the dataset.",
        "steps": "1. Load data.csv",
        "deliverables": "1. Dataset loaded.",
    },
}


class _AlwaysGeneratesExperiments:
    """Experiment generator that always returns one valid experiment."""

    def generate_reply(self, messages=None, **kwargs):
        return (
            '{"experiments": [{"hypothesis": "h", "experiment_plan": '
            '{"objective": "o", "steps": "s", "deliverables": "d"}}]}'
        )


class _NeverGeneratesExperiments:
    """Experiment generator whose replies never parse into an experiment."""

    def __init__(self):
        self.calls = 0

    def generate_reply(self, messages=None, **kwargs):
        self.calls += 1
        return "Vertex AI project not set."


class _UserProxy:
    """Stand-in for the user proxy agent; the chat itself is not under test."""

    def initiate_chat(self, recipient=None, message=None, clear_history=False):
        return None


class _FakeGroupChat:
    def __init__(self):
        self.messages = [
            {
                "name": "user_proxy",
                "role": "user",
                "content": (
                    "Hypothesis: h\n\nExperiment objective: o\n\n"
                    "Steps for the programmer:\ns\n\nDeliverables:\nd"
                ),
            }
        ]


class _FakeChatManager:
    def resume(self, messages=None):
        return None, "last message"

    def messages_to_string(self, messages):
        return json.dumps(messages)


def _succeeding_group_chat(agents, max_rounds):
    """Group chat stub whose node expansion always completes, committing the node."""
    return _FakeGroupChat(), _FakeChatManager()


def _make_root(untried_experiments=None, allow_generate_experiments=False):
    root = MCTSNode(
        level=0,
        node_idx=0,
        hypothesis=None,
        query=None,
        allow_generate_experiments=allow_generate_experiments,
        untried_experiments=untried_experiments,
    )
    nodes_by_level = defaultdict(list)
    nodes_by_level[0].append(root)
    return root, nodes_by_level


def _install_stubs(monkeypatch, experiment_generator, on_group_chat):
    """Replace the agent/chat/persistence layers so no model or filesystem work happens."""
    agent_objs = {
        "experiment_generator": experiment_generator,
        "user_proxy": _UserProxy(),
        "code_executor": object(),
    }
    monkeypatch.setattr(run_module, "get_agents", lambda *args, **kwargs: agent_objs)
    monkeypatch.setattr(run_module, "setup_group_chat", on_group_chat)
    monkeypatch.setattr(run_module, "save_nodes", lambda *args, **kwargs: None)


def _run(root, nodes_by_level, tmp_path, **kwargs):
    return run_mcts(
        root=root,
        nodes_by_level=nodes_by_level,
        dataset_paths=[],
        log_dirname=str(tmp_path / "logs"),
        work_dir=str(tmp_path / "work"),
        model_name="openai/gpt-4o",
        belief_model_name="openai/gpt-4o",
        vision_model="openai/gpt-4o",
        embedding_model="openai/text-embedding-3-small",
        max_iterations=50,
        **kwargs,
    )


def test_run_mcts_aborts_when_data_loader_node_cannot_be_created(tmp_path, monkeypatch, capsys):
    """A durable failure at the data-loader step ends the run instead of looping forever."""
    root, nodes_by_level = _make_root(untried_experiments=[LOAD_DATASET_EXPERIMENT])

    def _fail(*args, **kwargs):
        raise RuntimeError("Vertex AI project not set")

    _install_stubs(monkeypatch, _AlwaysGeneratesExperiments(), _fail)

    with pytest.raises(NoProgressError) as excinfo:
        _run(root, nodes_by_level, tmp_path)

    # The underlying cause is surfaced, not buried under repeated selection noise.
    assert "Vertex AI project not set" in str(excinfo.value)
    assert isinstance(excinfo.value.last_error, RuntimeError)
    assert nodes_by_level[1] == []

    # Log output is bounded: the loop cannot have run more iterations than the guard allows.
    output = capsys.readouterr().out
    assert output.count("######### ITERATION") <= 3


def test_run_mcts_aborts_when_experiment_generation_always_fails(tmp_path, monkeypatch, capsys):
    """Replies that never parse into an experiment stop the run after a bounded number of tries."""
    root, nodes_by_level = _make_root(allow_generate_experiments=True)
    generator = _NeverGeneratesExperiments()

    def _unreachable(*args, **kwargs):  # pragma: no cover - no node ever gets that far
        raise AssertionError("no node should be expanded")

    _install_stubs(monkeypatch, generator, _unreachable)

    with pytest.raises(NoProgressError):
        _run(root, nodes_by_level, tmp_path)

    output = capsys.readouterr().out
    assert output.count("######### ITERATION") <= 3
    assert output.count("No new experiment generated") <= 3


def test_run_mcts_aborts_after_max_no_progress_iterations(tmp_path, monkeypatch, capsys):
    """A node that keeps generating experiments but never commits one stops at the threshold."""
    root, nodes_by_level = _make_root(
        untried_experiments=[LOAD_DATASET_EXPERIMENT], allow_generate_experiments=True
    )

    def _fail(*args, **kwargs):
        raise RuntimeError("quota exhausted")

    _install_stubs(monkeypatch, _AlwaysGeneratesExperiments(), _fail)

    with pytest.raises(NoProgressError) as excinfo:
        _run(root, nodes_by_level, tmp_path, max_no_progress_iterations=2)

    assert excinfo.value.iterations == 2
    assert "quota exhausted" in str(excinfo.value)
    assert capsys.readouterr().out.count("######### ITERATION") == 2


def test_run_mcts_exits_cleanly_when_the_tree_is_exhausted(tmp_path, monkeypatch):
    """Running out of nodes after committing work is a normal ending, not a failure."""
    root, nodes_by_level = _make_root(
        untried_experiments=[LOAD_DATASET_EXPERIMENT], allow_generate_experiments=True
    )
    generator = _NeverGeneratesExperiments()

    _install_stubs(monkeypatch, generator, _succeeding_group_chat)

    # First iteration commits the data-loader node; then generation dries up and selection
    # runs out of nodes. That must return normally, keeping the committed node.
    _run(root, nodes_by_level, tmp_path)

    assert len(nodes_by_level[1]) == 1
    assert generator.calls > 0


def test_select_nodes_returns_nothing_when_root_is_exhausted():
    """The root is no longer selected once it can neither retry nor generate an experiment."""
    root, nodes_by_level = _make_root(untried_experiments=[LOAD_DATASET_EXPERIMENT])

    assert select_nodes(None, root, nodes_by_level) == [root]

    # Simulate the data-loader experiment being consumed by an expansion that failed.
    root.untried_experiments = []
    root.allow_generate_experiments = False

    assert select_nodes(None, root, nodes_by_level) == []
