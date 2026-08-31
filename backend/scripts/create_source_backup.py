from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
from zipfile import ZIP_DEFLATED, ZipFile


DEFAULT_NAME = "MAT-9f-source-v7-20260809.zip"

SOURCE_DIRECTORIES = (
    "src",
    "tests",
    "scripts",
    "docs",
    "examples",
    "web",
    "windows",
    "benchmarks",
    "benchmark-models",
    "config",
    "1000tests/src",
    "1000tests/scripts",
    "1000tests/tests",
)

ROOT_FILES = (
    ".gitignore",
    ".gitattributes",
    "README.md",
    "pyproject.toml",
    "requirements-training.txt",
    "start_agent.py",
    "start_desktop.py",
    "lancer-agent.bat",
    "COMPETENCES_EXPERTS.md",
    "_regenerate_legacy.py",
    "1000tests/README.md",
    "1000tests/MAT9F_EXPERT_GRAND_TOUR_V1.md",
    "1000tests/ETAT-323-EXPERTS-2026-08-09.md",
    "1000tests/ETAT-FINAL-EXPERTS-2026-08-09.md",
    "1000tests/SYSTEM-WIRING-AUDIT-2026-08-09.md",
    "1000tests/run-tests.ps1",
    "1000tests/run-pilot-100.ps1",
    "1000tests/TESTER-1000TESTS.cmd",
    "1000tests/LANCER-PILOTE-100.cmd",
    "1000tests/REVERIFIER-223.cmd",
)

EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "build",
    "dist",
    "models",
    "reports",
    "source-backups",
    "tools",
    "training-data",
    "training-runs",
    "work",
}

EXCLUDED_SUFFIXES = {
    ".gguf",
    ".pyc",
    ".pyo",
    ".safetensors",
    ".sqlite3",
    ".sqlite3-shm",
    ".sqlite3-wal",
}


def is_safe_source(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    lowered = path.name.casefold()
    if path.suffix.casefold() in EXCLUDED_SUFFIXES:
        return False
    if lowered.startswith(".env"):
        return False
    if any(
        marker in lowered
        for marker in (
            "private-oracle",
            "private_oracle",
            "private-exam",
            "private_exam",
        )
    ):
        return False
    return path.is_file()


def source_files(root: Path) -> list[Path]:
    selected: set[Path] = set()
    for relative_directory in SOURCE_DIRECTORIES:
        directory = root / relative_directory
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if is_safe_source(path, root):
                selected.add(path)
    for relative_file in ROOT_FILES:
        path = root / relative_file
        if path.is_file() and is_safe_source(path, root):
            selected.add(path)
    return sorted(selected, key=lambda item: item.relative_to(root).as_posix())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_backup(root: Path, output: Path, external_directory: Path) -> dict[str, object]:
    files = source_files(root)
    if not files:
        raise RuntimeError("no source files selected")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    with ZipFile(temporary, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for path in files:
            archive.write(path, path.relative_to(root).as_posix())
    temporary.replace(output)

    digest = sha256_file(output)
    external_directory.mkdir(parents=True, exist_ok=True)
    external_copy = external_directory / output.name
    shutil.copy2(output, external_copy)
    if sha256_file(external_copy) != digest:
        raise RuntimeError("external backup hash mismatch")

    manifest = {
        "schema_version": "mat9f-source-backup-v1",
        "archive": output.name,
        "file_count": len(files),
        "size_bytes": output.stat().st_size,
        "sha256": digest,
        "external_copy": str(external_copy),
        "excludes": {
            "models_and_weights": True,
            "private_oracles_and_exams": True,
            "reports_and_runtime_logs": True,
            "sealed_training_material": True,
            "credentials_and_env_files": True,
        },
    }
    manifest_path = output.with_suffix(".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    shutil.copy2(manifest_path, external_directory / manifest_path.name)
    return {**manifest, "manifest": str(manifest_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a safe MAT-9f source backup.")
    parser.add_argument("--output-name", default=DEFAULT_NAME)
    parser.add_argument("--external-directory", default=r"D:\MAT-9f-backups")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    output = root / "source-backups" / Path(args.output_name).name
    result = build_backup(root, output, Path(args.external_directory))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
