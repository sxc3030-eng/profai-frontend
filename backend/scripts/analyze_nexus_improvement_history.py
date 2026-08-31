"""Read a verified history and emit proposed improvement opportunities."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memory_agent.continuous_improvement import AppendOnlyHistory, detect_opportunities


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--minimum-occurrences", type=int, default=2)
    args = parser.parse_args()
    rows = AppendOnlyHistory(args.history).read_verified()
    opportunities = [
        item.to_dict()
        for item in detect_opportunities(rows, minimum_occurrences=args.minimum_occurrences)
    ]
    report = {
        "schema_version": "mat9f-improvement-opportunities-v1",
        "history_events": len(rows),
        "opportunities": opportunities,
        "automatic_mutation_allowed": False,
        "human_approval_required": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"events": len(rows), "opportunities": len(opportunities)}))


if __name__ == "__main__":
    main()
