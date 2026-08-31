"""Aggregate atomic Q001..Q030 receipts without contacting or starting Nexus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from memory_agent.mat9f_product_30q_gate_v1 import (
    CASES,
    CASE_SCHEMA_VERSION,
    case_sha256,
    evaluate_product_30q,
)
from memory_agent.mat9f_product_30q_runner_v1 import atomic_json


def collect(
    results_dir: Path, output: Path, *, provider_inventory: list[str]
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "schema_version": "mat9f-product-30q-collection-v2",
        "results": [],
        "pending": [],
        "xpu_started_by_runner": False,
        "publication_performed": False,
        "network_used": False,
    }
    atomic_json(output, state)
    for case in CASES:
        path = results_dir / f"{case['case_id']}.json"
        if not path.is_file():
            state["pending"].append(case["case_id"])
            atomic_json(output, state)
            continue
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(row, dict):
                raise ValueError("receipt_not_object")
            if (
                row.get("schema_version") != CASE_SCHEMA_VERSION
                or row.get("case_id") != case["case_id"]
                or row.get("case_sha256") != case_sha256(case)
            ):
                raise ValueError("receipt_identity_mismatch")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            row = {
                "schema_version": CASE_SCHEMA_VERSION,
                "case_id": case["case_id"],
                "case_sha256": case_sha256(case),
                "category": case["category"],
                "passed": False,
                "collector_error": f"{type(error).__name__}:{str(error)[:200]}",
            }
        state["results"].append(row)
        atomic_json(output, state)
    state["gate"] = evaluate_product_30q(
        state["results"], provider_inventory=provider_inventory
    )
    atomic_json(output, state)
    return state


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collecte hors ligne des reçus 30Q; ne démarre jamais XPU."
    )
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provider-inventory", nargs="+", required=True)
    arguments = parser.parse_args()
    state = collect(
        arguments.results_dir,
        arguments.output,
        provider_inventory=arguments.provider_inventory,
    )
    print(
        json.dumps(
            {
                "status": state["gate"]["status"],
                "collected": len(state["results"]),
                "pending": len(state["pending"]),
                "sha256": state["gate"]["sha256"],
            },
            sort_keys=True,
        )
    )
    return 0 if state["gate"]["status"] == "PASS_PRODUCT_30Q" else 1


if __name__ == "__main__":
    raise SystemExit(main())
