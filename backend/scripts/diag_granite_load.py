#!/usr/bin/env python3
"""Diagnostic du chargement Granite sur XPU (hors serveur)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from memory_agent.matlm_inference import (
    InferenceConfig,
    MATLMInferenceSession,
)

def main() -> int:
    config = InferenceConfig(
        adapter_path=None,
        code_adapter_path=None,
        base_model=r"D:\LLM Mat\AI\models\granite-3.3-2b-instruct",
        load_mode="auto",
        device_index=0,
        max_input_tokens=512,
        max_new_tokens=64,
        allow_model_download=False,
    )
    t0 = time.monotonic()
    print("[diag] démarrage du chargement...", flush=True)
    with MATLMInferenceSession(config) as session:
        t_load = time.monotonic() - t0
        print(f"[diag] modèle chargé en {t_load:.1f}s", flush=True)
        status = session.status() if hasattr(session, "status") else {}
        print("[diag] status:", json.dumps(status, default=str)[:2000], flush=True)
    print("[diag] OK", flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
