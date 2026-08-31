"""Prepare the 1,000-expert Grand Tour without loading any model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from memory_agent.mat9f_expert_grand_tour_v1 import (  # noqa: E402
    GrandTourError,
    build_authoring_bundle,
    load_json,
)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        ),
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare a fail-closed four-probe queue for all 1,000 experts."
    )
    parser.add_argument("--fleet-snapshot", type=Path, required=True)
    parser.add_argument("--bindings", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        fleet = load_json(args.fleet_snapshot)
        bindings = load_json(args.bindings) if args.bindings else None
        bundle = build_authoring_bundle(fleet, binding_manifest=bindings)
        if not args.check:
            args.output.mkdir(parents=True, exist_ok=False)
            _write_json(args.output / "test-plan.json", bundle["plan"])
            _write_jsonl(
                args.output / "provider-binding-authoring-template.jsonl",
                bundle["binding_authoring_template"],
            )
            _write_jsonl(args.output / "public-case-authoring-queue.jsonl", bundle["public_cases"])
            _write_jsonl(
                args.output / "private-oracle-authoring-template.jsonl",
                bundle["private_oracle_template"],
            )
        print(json.dumps(bundle["plan"], ensure_ascii=False, sort_keys=True))
        return 0
    except (GrandTourError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
