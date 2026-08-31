"""Validate a candidate file budget without applying or promoting changes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memory_agent.continuous_improvement import CandidateChangeBudget, validate_candidate_changes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget", type=Path, required=True)
    parser.add_argument("--changed", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = json.loads(args.budget.read_text(encoding="utf-8"))
    budget = CandidateChangeBudget(
        candidate_id=raw["candidate_id"],
        component=raw["component"],
        baseline_manifest_sha256=raw["baseline_manifest_sha256"],
        allowed_paths=tuple(raw["allowed_paths"]),
        max_files=int(raw.get("max_files", 4)),
        max_total_bytes=int(raw.get("max_total_bytes", 250_000)),
    )
    report = validate_candidate_changes(ROOT, budget, args.changed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"candidate_id": budget.candidate_id, "within_budget": True}))


if __name__ == "__main__":
    main()
