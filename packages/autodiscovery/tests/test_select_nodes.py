"""select_nodes must stop selecting a root that has nothing left to try (#79)."""

from collections import defaultdict

from autodiscovery.mcts import MCTSNode
from autodiscovery.mcts_utils import select_nodes


def test_select_nodes_returns_nothing_when_root_is_exhausted():
    root = MCTSNode(
        level=0,
        node_idx=0,
        hypothesis=None,
        query=None,
        allow_generate_experiments=False,
        untried_experiments=[{"hypothesis": None, "experiment_plan": {}}],
    )
    nodes_by_level = defaultdict(list)
    nodes_by_level[0].append(root)

    assert select_nodes(None, root, nodes_by_level) == [root]

    # The data-loader experiment was consumed by an expansion that failed.
    root.untried_experiments = []

    assert select_nodes(None, root, nodes_by_level) == []
