"""Supervise the native Nexus service and desktop as one local application."""

from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
INSTALL_ROOT = Path(r"D:\LLM Mat")
DATA_ROOT = INSTALL_ROOT / "data"
LOG_ROOT = DATA_ROOT / "logs"
PORT = 8765
BASE_URL = f"http://127.0.0.1:{PORT}"


def _message(text: str) -> None:
    ctypes.windll.user32.MessageBoxW(None, text, "Nexus", 0x10)


def _health() -> bool:
    try:
        with urlopen(f"{BASE_URL}/api/health", timeout=2.0) as response:
            payload = json.loads(response.read(65_536).decode("utf-8"))
        return (
            payload.get("ok") is True
            and payload.get("service_role") == "desktop"
        )
    except Exception:
        return False


def _start_engine() -> None:
    request = Request(
        f"{BASE_URL}/api/matlm/start",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=15.0) as response:
        payload = json.loads(response.read(65_536).decode("utf-8"))
    status = payload.get("matlm") if isinstance(payload, dict) else None
    if payload.get("ok") is not True or not isinstance(status, dict):
        raise RuntimeError("Le moteur Granite n'a pas confirmé son démarrage.")


def _stop_engine() -> None:
    request = Request(
        f"{BASE_URL}/api/matlm/stop",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20.0) as response:
            response.read(65_536)
    except Exception:
        # Service termination below remains the final bounded cleanup.
        pass


def _legacy_main_unused() -> int:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    pythonw = Path(sys.executable)
    python = pythonw.with_name("python.exe")
    if not python.is_file():
        _message("Le moteur Python local de Nexus est absent.")
        return 2

    env = os.environ.copy()
    env.update({
        "PYTHONPATH": str(ROOT / "src"),
        "MAT_NEXUS_INSTALL_ROOT": str(INSTALL_ROOT),
        "MAT_NEXUS_DATA_ROOT": str(DATA_ROOT),
        "MAT_NEXUS_CONTROL_ROOT": str(INSTALL_ROOT / "config"),
        "MAT_NEXUS_MODEL_ROOT": str(INSTALL_ROOT / "AI"),
        "MAT_NEXUS_INDEX_ROOT": str(INSTALL_ROOT / "indexes"),
        "MAT_NEXUS_BACKUP_ROOT": str(INSTALL_ROOT / "backups"),
        "MAT_NEXUS_MODEL_PYTHON": r"D:\LLM Mat\AI\.venv\Scripts\python.exe",
        "MAT_NEXUS_PRODUCT_VERSION": "0.9.2-dev",
        "MAT_NEXUS_AI_ENABLED": "1",
    })
    env.pop("MAT_NEXUS_OLLAMA_MODEL", None)
    env.pop("MAT_NEXUS_OLLAMA_URL", None)

    owned_service = False
    service: subprocess.Popen[bytes] | None = None
    log = (LOG_ROOT / "nexus-current-service.log").open("ab", buffering=0)
    desktop_log = (LOG_ROOT / "nexus-current-desktop.log").open("ab", buffering=0)
    try:
        if not _health():
            service_args = [
                str(python), str(ROOT / "start_agent.py"), "--no-browser",
                "--host", "127.0.0.1", "--port", str(PORT),
                "--service-role", "desktop", "--async-injection",
                "--nexus-core-manifest",
                str(ROOT / "src" / "memory_agent" / "manifests"
                    / "mat9f-public-prudent-core-manifest-v1.json"),
                "--db", str(DATA_ROOT / "memory.sqlite3"), "--enable-matlm",
                "--matlm-python",
                str(INSTALL_ROOT / "AI" / ".venv" / "Scripts" / "python.exe"),
                "--matlm-model",
                str(INSTALL_ROOT / "AI" / "models" / "granite-3.3-2b-instruct"),
                "--matlm-load-mode", "bf16", "--matlm-max-new-tokens", "768",
                "--matlm-timeout-seconds", "180", "--matlm-adapter",
                str(INSTALL_ROOT / "AI" / "adapters" / "nexus-bridge"),
                "--matlm-code-adapter",
                str(INSTALL_ROOT / "AI" / "adapter_code_planner"),
            ]
            service = subprocess.Popen(
                service_args, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            owned_service = True
            deadline = time.monotonic() + 90.0
            while time.monotonic() < deadline:
                if service.poll() is not None:
                    _message("Le service Nexus s'est arrêté. Consultez nexus-current-service.log.")
                    return 3
                if _health():
                    break
                time.sleep(0.5)
            else:
                _message("Le service Nexus n'a pas démarré dans le délai prévu.")
                return 4

        _start_engine()

        desktop = subprocess.Popen(
            [str(pythonw), str(ROOT / "start_desktop.py"), "--host", "127.0.0.1",
             "--port", str(PORT), "--no-auto-server"],
            cwd=ROOT, env=env,
            stdout=desktop_log, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        exit_code = desktop.wait()
        desktop_log.write(f"desktop_exit_code={exit_code}\n".encode("utf-8"))
        return exit_code
    except Exception as error:
        _message(f"Nexus n'a pas pu démarrer : {error}")
        return 5
    finally:
        if owned_service and service is not None and service.poll() is None:
            _stop_engine()
            service.terminate()
            try:
                service.wait(timeout=10.0)
            except subprocess.TimeoutExpired:
                service.kill()
                service.wait(timeout=5.0)
        log.close()
        desktop_log.close()


from nexus_native_supervisor_v1 import main


if __name__ == "__main__":
    # Keep this stable entry point for installed shortcuts while lifecycle
    # ownership lives in the independently testable strict supervisor.
    raise SystemExit(main())
