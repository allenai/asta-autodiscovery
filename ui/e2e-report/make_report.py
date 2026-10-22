"""Write a synthetic finished run and its HTML report, for report-viewer.spec.ts.

Usage: python make_report.py <dir>  (the report lands in <dir>/output/report)

The run is invented, small, and covers what the page must render: a root node,
a surprising experiment with an image figure and a text output, an
unsurprising one, and a failed one.
"""

import json
import sys
from pathlib import Path

from autodiscovery.report import generate_report

# A 1x1 PNG, as the engine stores figures: base64 under its MIME type.
PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="


def belief(mean: float) -> dict:
    return {"_type": "boolean_cat", "prior_params": [0.5, 0.5], "n": 5.0, "mean": mean}


def main(root: Path) -> None:
    out = root / "output"
    (out / "rich_outputs").mkdir(parents=True)
    (root / "metadata.json").write_text(
        json.dumps(
            {
                "name": "Synthetic soil study",
                "description": "A made-up run for the report viewer's smoke test.",
                "datasets": [{"name": "soil.csv", "description": "Invented measurements."}],
            }
        )
    )
    (out / "args.json").write_text(
        json.dumps(
            {
                "dataset_metadata": str(root / "metadata.json"),
                "n_experiments": 3,
                "exploration_weight": 2.0,
                "mcts_selection": "pw",
                "surprisal_width": 0.2,
                "evidence_weight": 2.0,
            }
        )
    )
    experiment = {
        "parent_id": "node_1_0",
        # As the engine writes plans: three markdown strings.
        "experiment_plan": {
            "objective": "Test it.",
            "steps": "1. Fit a model.",
            "deliverables": "A coefficient.",
        },
        "code": "print('fit')",
        "code_output": "fit",
        "analysis": "The data support it.",
        "review": "Sound.",
        "time_elapsed": 12.5,
    }
    nodes = [
        {"id": "node_1_0", "parent_id": None, "creation_idx": 1, "success": True},
        {
            **experiment,
            "id": "node_2_0",
            "creation_idx": 2,
            "success": True,
            "surprising": True,
            "normalized_surprisal": 0.6,
            "hypothesis": "Nitrogen raises yield only in acidic soil.",
            "prior": belief(0.3),
            "posterior": belief(0.9),
            "created_at": "2026-01-01T00:00:00+00:00",
        },
        {
            **experiment,
            "id": "node_2_1",
            "creation_idx": 3,
            "success": True,
            "surprising": False,
            "normalized_surprisal": 0.1,
            "hypothesis": "Rainfall predicts yield.",
            "prior": belief(0.8),
            "posterior": belief(0.85),
            "created_at": "2026-01-01T00:10:00+00:00",
        },
        {
            **experiment,
            "id": "node_3_0",
            "parent_id": "node_2_0",
            "creation_idx": 4,
            "success": False,
            "hypothesis": "Clay content explains the acidity effect.",
            "created_at": "2026-01-01T00:20:00+00:00",
        },
    ]
    (out / "mcts_nodes.json").write_text(json.dumps(nodes))
    (out / "rich_outputs" / "ro_2_0.json").write_text(
        json.dumps([{"image/png": PNG}, {"text/plain": "yield ~ nitrogen * pH"}])
    )
    print(generate_report(str(out)))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python make_report.py <dir>")
    main(Path(sys.argv[1]))
