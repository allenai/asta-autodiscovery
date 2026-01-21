"""Experiment tree management for autodiscovery jobs."""

from __future__ import annotations

import logging
from typing import Any

from autodiscovery_jobs import JobConfig
from autodiscovery_jobs.gcs import list_experiment_files, read_experiment_node


class ExperimentNode:
    """Represents a single experiment node with tree relationships."""

    def __init__(self, node_data: dict[str, Any], filename: str):
        """Initialize experiment node from JSON data.

        Args:
            node_data: Dictionary containing experiment node data
            filename: Original filename (e.g., "mcts_node_0_0.json")
        """
        # Core fields from file
        self.id: str = node_data.get("id", "")
        self.parent_id: str | None = node_data.get("parent_id")
        self.creation_idx: int = node_data.get("creation_idx", 0)
        self.filename: str = filename

        # Derive level and index from filename if not in data
        # Format: mcts_node_{level}_{index}.json
        if "_" in filename:
            parts = filename.replace(".json", "").split("_")
            if len(parts) >= 4:
                try:
                    self.level: int = int(parts[2])
                    self.index: int = int(parts[3])
                except (ValueError, IndexError):
                    self.level = 0
                    self.index = 0
            else:
                self.level = 0
                self.index = 0
        else:
            self.level = 0
            self.index = 0

        # Experiment content fields
        self.hypothesis: str | None = node_data.get("hypothesis")
        self.experiment_plan: dict | None = node_data.get("experiment_plan")
        self.review: str | None = node_data.get("review")

        # Status derived from success field
        success = node_data.get("success")
        if success is None:
            self.status: str = "pending"
        elif success:
            self.status = "success"
        else:
            self.status = "failed"

        # Metrics
        self.is_surprising: bool | None = node_data.get("surprising")

        # Convert time_elapsed (seconds) to runtime_ms (milliseconds)
        time_elapsed = node_data.get("time_elapsed")
        self.runtime_ms: float | None = time_elapsed * 1000.0 if time_elapsed is not None else None

        # Tree relationships (populated during tree building)
        self.parent: ExperimentNode | None = None
        self.children: list[ExperimentNode] = []

    def to_experiment_model(self) -> dict[str, Any]:
        """Convert node to ExperimentModel dict for API response.

        Returns:
            Dictionary matching ExperimentModel schema
        """
        return {
            "experiment_id": self.id,
            "status": self.status,
            "parent_id": self.parent_id,
            "creation_idx": self.creation_idx,
            "is_surprising": self.is_surprising,
            "runtime_ms": self.runtime_ms,
            "hypothesis": self.hypothesis,
            "experiment_plan": self.experiment_plan,
            "review": self.review,
        }

    def __repr__(self) -> str:
        return f"ExperimentNode(id={self.id}, parent_id={self.parent_id}, status={self.status})"


class ExperimentTree:
    """Loads and provides access to experiment tree from GCS."""

    def __init__(
        self,
        userid: str,
        jobid: str,
        config: JobConfig | None = None,
        nodes: list[ExperimentNode] | None = None,
    ):
        """Initialize experiment tree.

        Args:
            userid: User identifier
            jobid: Job identifier
            config: Optional configuration
            nodes: Optional pre-loaded nodes (for testing)
        """
        self.userid = userid
        self.jobid = jobid
        self.config = config or JobConfig()
        self._nodes: dict[str, ExperimentNode] = {}
        self._root: ExperimentNode | None = None
        self._list_cache: list[ExperimentNode] | None = None

        if nodes:
            for node in nodes:
                self._nodes[node.id] = node
            self._build_tree_relationships()

    @classmethod
    def load(cls, userid: str, jobid: str, config: JobConfig | None = None) -> ExperimentTree:
        """Factory method to load tree from GCS.

        Args:
            userid: User identifier
            jobid: Job identifier
            config: Optional configuration

        Returns:
            ExperimentTree instance with loaded nodes
        """
        config = config or JobConfig()
        tree = cls(userid, jobid, config)
        tree._load_from_gcs()
        return tree

    def _load_from_gcs(self) -> None:
        """Load all experiment nodes from GCS."""
        try:
            filenames = list_experiment_files(self.userid, self.jobid, self.config)
        except Exception as e:
            logging.warning(f"Failed to list experiment files: {e}")
            filenames = []

        for filename in filenames:
            node_data = read_experiment_node(self.userid, self.jobid, filename, self.config)
            if node_data:
                try:
                    node = ExperimentNode(node_data, filename)
                    self._nodes[node.id] = node
                except Exception as e:
                    logging.warning(f"Failed to parse experiment node {filename}: {e}")
                    continue

        self._build_tree_relationships()

    def _build_tree_relationships(self) -> None:
        """Build parent-child relationships between nodes."""
        # First pass: find root and link children to parents
        for node_id, node in self._nodes.items():
            if node.parent_id is None:
                self._root = node
            else:
                # Find parent and add this node as child
                parent = self._nodes.get(node.parent_id)
                if parent:
                    node.parent = parent
                    parent.children.append(node)
                else:
                    logging.warning(
                        f"Node {node_id} references missing parent {node.parent_id}"
                    )

        # Sort children by creation index for consistent ordering
        for node in self._nodes.values():
            node.children.sort(key=lambda n: n.creation_idx)

    def get_node(self, node_id: str) -> ExperimentNode | None:
        """Get single node by ID.

        Args:
            node_id: Node identifier

        Returns:
            ExperimentNode if found, None otherwise
        """
        return self._nodes.get(node_id)

    def as_list(self, after_experiment_id: str | None = None) -> list[ExperimentNode]:
        """Get flat list of nodes, optionally filtered.

        Args:
            after_experiment_id: If provided, only return nodes with creation_idx
                                 greater than the node with this ID

        Returns:
            List of ExperimentNode sorted by creation_idx
        """
        if self._list_cache is None:
            self._list_cache = sorted(self._nodes.values(), key=lambda n: n.creation_idx)

        if after_experiment_id is None:
            return self._list_cache

        # Find the creation_idx of the after_experiment_id
        after_node = self._nodes.get(after_experiment_id)
        if after_node is None:
            # If node not found, return all nodes
            return self._list_cache

        # Filter to nodes created after this one
        after_idx = after_node.creation_idx
        return [node for node in self._list_cache if node.creation_idx > after_idx]

    def as_tree(self) -> ExperimentNode | None:
        """Get root node with children populated.

        Returns:
            Root ExperimentNode with full tree structure, or None if no root
        """
        return self._root

    @property
    def root(self) -> ExperimentNode | None:
        """Access root node directly."""
        return self._root

    def to_experiment_models(
        self, after_experiment_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Convert to list of ExperimentModel dicts for API response.

        Args:
            after_experiment_id: Optional filter for pagination

        Returns:
            List of dictionaries matching ExperimentModel schema
        """
        nodes = self.as_list(after_experiment_id=after_experiment_id)
        return [node.to_experiment_model() for node in nodes]

    def __len__(self) -> int:
        """Return number of nodes in tree."""
        return len(self._nodes)

    def __repr__(self) -> str:
        return f"ExperimentTree(userid={self.userid}, jobid={self.jobid}, nodes={len(self._nodes)})"
