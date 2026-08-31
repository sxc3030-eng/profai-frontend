from __future__ import annotations

import argparse
import json
from pathlib import Path

from memory_agent.mat9f_progressive_expert_queue_v1 import build_progressive_queue


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--report-root", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume-from", type=Path)
    parser.add_argument("--batch-size", type=int, default=25)
    args = parser.parse_args()
    reports = [path for root in args.report_root for path in root.rglob("qualification-report.json")]
    previous = json.loads(args.resume_from.read_text(encoding="utf-8")) if args.resume_from else None
    result = build_progressive_queue(args.source_dir, reports, batch_size=args.batch_size, previous=previous)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "batches": result["batch_count"],
                      "items": len(result["items"]), "counts": result["counts"],
                      "sha256": result["queue_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
