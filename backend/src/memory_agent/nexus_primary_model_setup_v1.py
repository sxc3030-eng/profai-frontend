"""Safe, explicit setup for the default local Nexus model.

No installation or download occurs at import time.  The caller must obtain
human consent before calling :func:`install_primary_model`.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import subprocess
from typing import Callable
from urllib.request import Request, urlopen


SCHEMA_VERSION = "nexus-primary-model-setup-v1"
PRIMARY_MODEL = "granite3.3:2b"
OLLAMA_URL = "http://127.0.0.1:11434"
MAX_JSON_BYTES = 2_000_000


class PrimaryModelSetupError(RuntimeError):
    pass


@dataclass(frozen=True)
class PrimaryModelStatus:
    runtime_available: bool
    service_available: bool
    model_available: bool
    model_id: str = PRIMARY_MODEL


def find_ollama_executable() -> Path | None:
    found = shutil.which("ollama")
    candidates = [
        Path(found) if found else None,
        Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe",
        Path(r"C:\Program Files\Ollama\ollama.exe"),
    ]
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate.resolve(strict=False)
    return None


def inspect_primary_model(base_url: str = OLLAMA_URL) -> PrimaryModelStatus:
    executable = find_ollama_executable()
    try:
        request = Request(base_url.rstrip("/") + "/api/tags", method="GET")
        with urlopen(request, timeout=3.0) as response:
            payload = json.loads(response.read(MAX_JSON_BYTES).decode("utf-8"))
        names = {
            str(item.get("name", "")).strip()
            for item in payload.get("models", [])
            if isinstance(item, dict)
        }
        service = True
    except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        names, service = set(), False
    return PrimaryModelStatus(executable is not None, service, PRIMARY_MODEL in names)


def install_primary_model(
    *,
    consent: bool,
    progress: Callable[[str], None] | None = None,
    timeout_seconds: int = 3600,
) -> PrimaryModelStatus:
    """Pull the fixed primary model through an existing Ollama installation."""

    if consent is not True:
        raise PrimaryModelSetupError("consentement_explicit_requis")
    executable = find_ollama_executable()
    if executable is None:
        raise PrimaryModelSetupError("runtime_local_absent")
    if progress:
        progress("Téléchargement et vérification du moteur principal…")
    try:
        completed = subprocess.run(
            [str(executable), "pull", PRIMARY_MODEL],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PrimaryModelSetupError("installation_moteur_echouee") from exc
    if completed.returncode != 0:
        tail = completed.stdout[-500:].strip()
        raise PrimaryModelSetupError(f"installation_moteur_echouee: {tail}")
    status = inspect_primary_model()
    if not status.model_available:
        raise PrimaryModelSetupError("moteur_installe_non_detecte")
    return status


__all__ = [
    "PRIMARY_MODEL", "PrimaryModelSetupError", "PrimaryModelStatus",
    "find_ollama_executable", "inspect_primary_model", "install_primary_model",
]
