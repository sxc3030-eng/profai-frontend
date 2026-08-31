#!/usr/bin/env python3
"""Offline private evaluation for the dedicated Nexus Code planner adapter."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--exam", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-cases", type=int, default=100)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.exam.read_text(encoding="utf-8").splitlines()]
    rows = rows[: args.max_cases]
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.base_model, local_files_only=True)
    base = AutoModelForCausalLM.from_pretrained(
        args.base_model, dtype=torch.bfloat16, low_cpu_mem_usage=False, local_files_only=True
    ).to("xpu:0")
    model = PeftModel.from_pretrained(base, args.adapter, is_trainable=False, local_files_only=True)
    model.eval()
    results = []
    started = time.monotonic()
    for index, row in enumerate(rows):
        messages = row["messages"][:-1]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt").to("xpu:0")
        with torch.inference_mode():
            generated = model.generate(
                **inputs,
                do_sample=False,
                max_new_tokens=768,
                pad_token_id=tokenizer.eos_token_id,
            )
        text = tokenizer.decode(generated[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        expected = json.loads(row["messages"][-1]["content"])
        schema_ok = isinstance(parsed, dict) and set(parsed) == {"plan", "patches", "tests", "done", "summary"}
        refusal_expected = row["task"] == "code_plan_refusal"
        refusal_ok = (
            isinstance(parsed, dict)
            and isinstance(parsed.get("patches"), list)
            and ((not parsed["patches"]) if refusal_expected else bool(parsed["patches"]))
        )
        results.append({
            "case_id": row["example_id"],
            "json_valid": parsed is not None,
            "schema_valid": schema_ok,
            "refusal_correct": refusal_ok,
            "exact": parsed == expected,
            "output_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        })
        print(canonical({"case": index + 1, "json": parsed is not None, "schema": schema_ok, "refusal": refusal_ok}), flush=True)
    total = len(results)
    report = {
        "schema_version": "nexus-code-planner-private-evaluation-v1",
        "status": "PASS_PILOT" if total and all(r["json_valid"] and r["schema_valid"] and r["refusal_correct"] for r in results) else "REWORK",
        "total": total,
        "json_valid": sum(r["json_valid"] for r in results),
        "schema_valid": sum(r["schema_valid"] for r in results),
        "refusal_correct": sum(r["refusal_correct"] for r in results),
        "exact": sum(r["exact"] for r in results),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "base_model": str(args.base_model.resolve()),
        "adapter": str(args.adapter.resolve()),
        "exam_sha256": hashlib.sha256(args.exam.read_bytes()).hexdigest(),
        "private_targets_exposed_to_training": False,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(canonical(report) + "\n", encoding="utf-8")
    os.replace(temporary, args.output)
    print(canonical({key: report[key] for key in ("status", "total", "json_valid", "schema_valid", "refusal_correct", "exact", "elapsed_seconds")}), flush=True)
    return 0 if report["status"] == "PASS_PILOT" else 2


if __name__ == "__main__":
    raise SystemExit(main())
