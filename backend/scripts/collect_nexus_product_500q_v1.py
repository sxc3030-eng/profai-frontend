"""Collect Q001..Q500 receipts offline without contacting or starting Nexus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from memory_agent.mat9f_product_500q_gate_v1 import (
    CASES,
    CASE_SCHEMA_VERSION,
    case_sha256,
    evaluate_product_500q,
    matrix_contract,
)
from memory_agent.mat9f_product_500q_runner_v1 import atomic_json


def collect(
    results_dir: Path,
    output: Path,
    *,
    provider_inventory: list[str],
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "schema_version": "mat9f-product-500q-collection-v1",
        "matrix": matrix_contract(),
        "results": [],
        "pending": [],
        "private_targets_embedded": False,
        "visual_tk_validated": False,
        "xpu_started_by_collector": False,
        "service_contacted": False,
        "publication_performed": False,
        "hugging_face_used": False,
        "network_scope": "none",
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
                "family": case["family"],
                "surface": case["surface"],
                "passed": False,
                "collector_error": f"{type(error).__name__}:{str(error)[:200]}",
            }
        state["results"].append(row)
        atomic_json(output, state)
    state["gate"] = evaluate_product_500q(
        state["results"], provider_inventory=provider_inventory
    )
    atomic_json(output, state)
    return state


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collecte hors ligne des reçus 500Q; ne contacte jamais Nexus."
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
                "service_contacted": False,
            },
            sort_keys=True,
        )
    )
    return 0 if state["gate"]["status"] == "PASS_PRODUCT_500Q" else 1


if __name__ == "__main__":
    raise SystemExit(main())
