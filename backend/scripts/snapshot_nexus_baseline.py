"""Create a deterministic baseline manifest for continuous improvement."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memory_agent.continuous_improvement import build_baseline_manifest


def baseline_files(root: Path) -> list[Path]:
    files = [root / "config" / "mat-nexus-expert-work-ownership-v1.json"]
    files.extend((root / "src" / "memory_agent").glob("mat9f_*_expert_v1.py"))
    files.extend(
        root / "src" / "memory_agent" / name
        for name in (
            "continuous_improvement.py",
            "nexus_trial_cascade.py",
            "mat9f_sparse_router.py",
            "mat9f_mesh_circle_router.py",
            "mat9f_nexus_sphere.py",
        )
    )
    files.extend((root / "tests").glob("test_mat9f_*_expert_v1.py"))
    files.extend((root / "tests").glob("test_qualify_mat_nexus_*_v1.py"))
    files.append(root / "tests" / "test_continuous_improvement.py")
    files.extend(
        root / "scripts" / name
        for name in (
            "analyze_nexus_improvement_history.py",
            "compare_nexus_candidate.py",
            "run_nexus_improvement_pilot.py",
            "snapshot_nexus_baseline.py",
            "validate_nexus_candidate.py",
        )
    )
    files.append(root / "docs" / "MAT_NEXUS_CONTINUOUS_IMPROVEMENT_PLAN_V1.md")
    return [path for path in files if path.is_file()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_baseline_manifest(ROOT, baseline_files(ROOT))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"files": len(manifest["files"]), "sha256": manifest["manifest_sha256"]}))


if __name__ == "__main__":
    main()
