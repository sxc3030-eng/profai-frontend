from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from memory_agent.mat9f_engine_stress import PROFILE_CASES, run_engine_stress  # noqa: E402


def _write_atomic(path: Path, report: dict[str, object], *, replace: bool) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not replace:
        raise FileExistsError(f"Le rapport existe déjà: {path}")
    data = (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Charge déterministe et hors ligne du noyau MAT-9F")
    parser.add_argument("--profile", choices=tuple(PROFILE_CASES), default="standard")
    parser.add_argument("--cases", type=int)
    parser.add_argument("--seed", type=int, default=20_260_721)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--replace", action="store_true")
    arguments = parser.parse_args()
    report = run_engine_stress(seed=arguments.seed, profile=arguments.profile, case_count=arguments.cases)
    if arguments.output is not None:
        _write_atomic(arguments.output, report, replace=arguments.replace)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
