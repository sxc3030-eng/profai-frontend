#!/usr/bin/env python3
"""Diagnostic : capture la sortie brute de Granite pour voir ce qu'il produit."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from memory_agent.matlm_inference import (
    InferenceConfig,
    MATLMInferenceSession,
    _generate_text,
)
from memory_agent.native_llm_contract import build_capsule


def main() -> int:
    capsule = build_capsule(
        question="Quelle est la stratégie de cache pour une API ?",
        request_id="diag-brute",
        evidence=[{
            "evidence_id": "e1",
            "text": "La stratégie de cache pour une API repose sur la fraîcheur, "
                    "l'invalidation par clé et la mise en cache des réponses idempotentes.",
            "status": "verified",
            "confidence": 0.9,
            "space": "reference",
            "tags": ["cache", "api"],
            "temporal_context": None,
        }],
    )
    config = InferenceConfig(
        adapter_path=None,
        code_adapter_path=None,
        base_model=r"D:\LLM Mat\AI\models\granite-3.3-2b-instruct",
        load_mode="auto",
        device_index=0,
        max_input_tokens=1024,
        max_new_tokens=256,
        allow_model_download=False,
    )
    with MATLMInferenceSession(config) as session:
        raw = _generate_text(session._assets, capsule, config)
        print("[diag] SORTIE BRUTE:")
        print(raw[:3000])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
