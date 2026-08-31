#!/usr/bin/env python3
"""Execute le petit banc de charge local du Noyau Zero."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from memory_agent.mat9f_zero_stress import (  # noqa: E402
    MAT9FZeroStressError,
    PROFILE_CASES,
    run_zero_stress,
)


def _write_atomic(path: Path, report: dict[str, object], *, replace: bool) -> None:
    destination = path.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not replace:
        raise FileExistsError(f"Le rapport existe deja: {destination}")
    data = (
        json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)
        + "\n"
    ).encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, destination)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=tuple(PROFILE_CASES), default="smoke")
    parser.add_argument("--cases", type=int)
    parser.add_argument("--seed", type=int, default=20_260_721)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--replace", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        arguments = _parser().parse_args(argv)
        report = run_zero_stress(
            profile=arguments.profile,
            seed=arguments.seed,
            case_count=arguments.cases,
        )
        if arguments.output is not None:
            _write_atomic(arguments.output, report, replace=arguments.replace)
    except (MAT9FZeroStressError, FileExistsError, OSError, ValueError) as error:
        sys.stderr.write(f"Erreur stress Noyau Zero: {error}\n")
        return 2
    sys.stdout.write(
        json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)
        + "\n"
    )
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
