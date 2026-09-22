"""Stall detection for MCTS exploration: stop when iterations stop committing nodes.

A durable failure -- bad model credentials, exhausted quota, replies that never parse
into an experiment -- otherwise leaves the exploration loop selecting and failing at
full speed, burying its own cause in log noise (see issue #79).
"""

import threading
import traceback


class NoProgressError(RuntimeError):
    """Raised when exploration stops committing nodes and cannot recover.

    Attributes:
        iterations: Number of consecutive iterations that committed no node.
        last_error: The last per-node expansion error, when one was raised.
    """

    def __init__(self, message, *, iterations, last_error=None):
        """Initialize the error.

        Args:
            message: Human-readable description of the stall.
            iterations: Number of consecutive iterations that committed no node.
            last_error: The last per-node expansion error, when one was raised.
        """
        super().__init__(message)
        self.iterations = iterations
        self.last_error = last_error


class ProgressGuard:
    """Per-run tally of whether exploration iterations are committing nodes.

    One instance per run. ``record_expansion_error`` is called from expansion threads;
    the two ``check_*`` methods are called from the exploration loop and are the only
    places that raise.
    """

    def __init__(self, max_no_progress_iterations=3, *, total_to_sample=None):
        """Initialize the guard.

        Args:
            max_no_progress_iterations: Consecutive iterations that may commit no node
                before ``check_iteration`` aborts the run.
            total_to_sample: Experiment budget, used only in the abort message.
        """
        self.max_no_progress_iterations = max_no_progress_iterations
        self.total_to_sample = total_to_sample
        self.consecutive_no_progress = 0
        self.last_error = None
        self._error_guard = threading.Lock()

    def record_expansion_error(self, node_id, exc):
        """Report a failed node expansion and remember it as the latest failure cause."""
        with self._error_guard:
            self.last_error = exc
        # Keep exploration running when one node expansion fails.
        print(f"[run_mcts] Failed expanding node {node_id}: {exc.__class__.__name__}: {exc}")
        traceback.print_exception(type(exc), exc, exc.__traceback__)

    def check_iteration(self, n_committed, n_sampled):
        """Record one iteration's outcome, raising once too many commit nothing.

        Args:
            n_committed: Nodes committed by the iteration that just finished.
            n_sampled: Experiments completed so far, for the abort message.

        Raises:
            NoProgressError: If ``max_no_progress_iterations`` consecutive iterations
                have now committed no node.
        """
        if n_committed:
            self.consecutive_no_progress = 0
            self.last_error = None
            return

        self.consecutive_no_progress += 1
        print(
            "NO NODE COMMITTED IN THIS ITERATION "
            f"({self.consecutive_no_progress}/{self.max_no_progress_iterations} consecutive)\n"
        )
        if self.consecutive_no_progress >= self.max_no_progress_iterations:
            raise self._abort(
                f"{self.consecutive_no_progress} consecutive iterations committed no node",
                n_sampled,
            )

    def check_exhausted(self, n_sampled):
        """Judge a tree that has run out of selectable nodes.

        Running out is the normal way exploration ends early. It is a failure only when
        the tree ran dry because expansion kept erroring, or when the run never committed
        a single node (e.g. the data loader could never be created).

        Raises:
            NoProgressError: If the tree ran dry abnormally.
        """
        if self.consecutive_no_progress and (self.last_error is not None or n_sampled == 0):
            raise self._abort(
                f"no node is left to expand after {self.consecutive_no_progress} "
                "consecutive iteration(s) that committed no node",
                n_sampled,
            )

    def _abort(self, reason, n_sampled):
        """Build the abort error for a stalled run, naming the last underlying failure."""
        cause = (
            f"{self.last_error.__class__.__name__}: {self.last_error}"
            if self.last_error is not None
            else "no usable experiment was generated"
        )
        return NoProgressError(
            f"Exploration aborted: {reason} "
            f"({n_sampled}/{self.total_to_sample} experiments completed). Last failure: {cause}",
            iterations=self.consecutive_no_progress,
            last_error=self.last_error,
        )
