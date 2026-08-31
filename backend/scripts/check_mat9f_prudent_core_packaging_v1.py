from __future__ import annotations

import argparse
import json
from pathlib import Path

from memory_agent.mat9f_granite_prudent_core_v1 import validate_prudent_core_manifest

MANIFEST_NAME = "mat9f-public-prudent-core-manifest-v1.json"
EXPERT_FILES = (
    "mat9f_cpp_expert_v1.py",
    "mat9f_cryptography_expert_v1.py",
    "mat9f_document_routing_expert_v1.py",
)


def check_packaging(desktop: Path, spec: Path, manifest: Path, source_dir: Path) -> dict[str, object]:
    issues: list[str] = []
    try:
        validate_prudent_core_manifest(json.loads(manifest.read_text(encoding="utf-8")), source_dir)
    except Exception as exc:
        issues.append("manifest_invalid:" + type(exc).__name__)
    try:
        spec_text = spec.read_text(encoding="utf-8")
    except OSError:
        spec_text = ""; issues.append("service_spec_missing")
    for filename in (MANIFEST_NAME,) + EXPERT_FILES:
        if filename not in spec_text:
            issues.append("service_bundle_missing:" + filename)
    try:
        desktop_text = desktop.read_text(encoding="utf-8")
    except OSError:
        desktop_text = ""; issues.append("desktop_launcher_missing")
    if '"--nexus-core-manifest"' not in desktop_text:
        issues.append("launcher_argument_missing:--nexus-core-manifest")
    if MANIFEST_NAME not in desktop_text:
        issues.append("launcher_manifest_resolution_missing")
    return {"status": "PASS" if not issues else "FAIL_CLOSED", "issues": issues,
            "release_allowed": not issues}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--desktop", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    args = parser.parse_args()
    result = check_packaging(args.desktop, args.spec, args.manifest, args.source_dir)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["release_allowed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
