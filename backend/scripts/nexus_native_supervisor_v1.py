"""Strict lifecycle supervisor for the native Nexus desktop candidate.

The supervisor never adopts a service unless its complete product identity
matches, never stops a foreign process, and never starts the native model while
Ollama reports a loaded model.
"""

from __future__ import annotations

import argparse
import ctypes
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
INSTALL_ROOT = Path(r"D:\LLM Mat")
DATA_ROOT = INSTALL_ROOT / "data"
LOG_ROOT = DATA_ROOT / "logs"
PORT = 8765
BASE_URL = f"http://127.0.0.1:{PORT}"
OLLAMA_URL = "http://127.0.0.1:11434/api/ps"

EXPECTED_ENGINE = "memory"
EXPECTED_APPLICATION = "mat-zero-cortex"
EXPECTED_PROTOCOL = "mat-zero-desktop-v1"
EXPECTED_ROLE = "desktop"
EXPECTED_PRODUCT_VERSION = "0.9.2-dev"
EXPECTED_BUILD_ID = "nexus-moe-native-0.9.2-dev"
EXPECTED_CAPABILITIES = frozenset(
    {
        "granite-native-v1",
        "conversation-list-v1",
        "activity-status-v1",
        "expert-receipt-v1",
    }
)

# The global mutex serializes native XPU ownership across Windows sessions.
# The local guards prevent older launchers from racing the current candidate.
GLOBAL_MUTEX_NAME = r"Global\Nexus-MoE-Native-XPU-v1"
LEGACY_MUTEX_NAMES = (
    r"Local\Nexus-MoE-Current-v1",
    r"Local\MAT-Nexus-Portable-Desktop-v1",
)

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
WAIT_OBJECT_0 = 0
WAIT_ABANDONED = 0x80
ERROR_ALREADY_EXISTS = 183


@dataclass(frozen=True)
class RuntimePaths:
    host_python: Path
    model_python: Path
    base_model: Path
    general_adapter: Path
    code_adapter: Path
    core_manifest: Path
    service_entry: Path
    desktop_entry: Path

    @classmethod
    def current(cls) -> "RuntimePaths":
        executable = Path(sys.executable).resolve()
        return cls(
            host_python=executable.with_name("python.exe"),
            model_python=INSTALL_ROOT / "AI" / ".venv" / "Scripts" / "python.exe",
            base_model=INSTALL_ROOT / "AI" / "models" / "granite-3.3-2b-instruct",
            general_adapter=INSTALL_ROOT / "AI" / "adapters" / "nexus-bridge",
            code_adapter=INSTALL_ROOT / "AI" / "adapter_code_planner",
            core_manifest=(
                ROOT
                / "src"
                / "memory_agent"
                / "manifests"
                / "mat9f-public-prudent-core-manifest-v1.json"
            ),
            service_entry=ROOT / "start_agent.py",
            desktop_entry=ROOT / "start_desktop.py",
        )


@dataclass(frozen=True)
class ServiceProbe:
    state: str
    compatible: bool
    detail: str
    http_status: int | None = None
    payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class OllamaProbe:
    state: str
    conflict: bool
    detail: str
    loaded_models: tuple[str, ...] = ()


def _message(text: str) -> None:
    ctypes.windll.user32.MessageBoxW(None, text, "Nexus", 0x10)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _append_event(event: str, **fields: Any) -> None:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    record = {"timestamp_utc": _utc_now(), "event": event, **fields}
    with (LOG_ROOT / "nexus-current-supervisor.jsonl").open(
        "a", encoding="utf-8", newline="\n"
    ) as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _decode_json(raw: bytes) -> dict[str, Any]:
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("La réponse JSON n'est pas un objet.")
    return payload


def _http_json(
    target: str | Request,
    *,
    timeout: float,
    opener: Callable[..., Any] = urlopen,
) -> tuple[int, dict[str, Any]]:
    try:
        with opener(target, timeout=timeout) as response:
            return int(getattr(response, "status", 200)), _decode_json(
                response.read(65_536)
            )
    except HTTPError as error:
        # Current Nexus can deliberately answer 503 while the model is down;
        # the JSON body still carries the service identity.
        return int(error.code), _decode_json(error.read(65_536))


def _port_open(
    port: int,
    *,
    connector: Callable[..., Any] = socket.create_connection,
) -> bool:
    try:
        connection = connector(("127.0.0.1", port), timeout=0.4)
        close = getattr(connection, "close", None)
        if callable(close):
            close()
        return True
    except OSError:
        return False


def _has_expected_identity(payload: dict[str, Any]) -> bool:
    readable = payload.get("ok") is True or payload.get("read_available") is True
    capabilities = payload.get("service_capabilities")
    return bool(
        readable
        and payload.get("engine") == EXPECTED_ENGINE
        and payload.get("application") == EXPECTED_APPLICATION
        and payload.get("desktop_protocol") == EXPECTED_PROTOCOL
        and payload.get("service_role") == EXPECTED_ROLE
        and payload.get("product_version") == EXPECTED_PRODUCT_VERSION
        and payload.get("service_build_id") == EXPECTED_BUILD_ID
        and isinstance(capabilities, list)
        and EXPECTED_CAPABILITIES.issubset(set(capabilities))
    )


def _probe_service(
    *,
    opener: Callable[..., Any] = urlopen,
    connector: Callable[..., Any] = socket.create_connection,
) -> ServiceProbe:
    try:
        status, payload = _http_json(
            f"{BASE_URL}/api/health", timeout=2.0, opener=opener
        )
    except Exception as error:
        if _port_open(PORT, connector=connector):
            return ServiceProbe(
                state="occupied_unknown",
                compatible=False,
                detail=f"Le port {PORT} répond sans identité Nexus valide: {error}",
            )
        return ServiceProbe(
            state="absent",
            compatible=False,
            detail="Aucun service n'écoute sur le port Nexus.",
        )

    if _has_expected_identity(payload):
        return ServiceProbe(
            state="compatible",
            compatible=True,
            detail="Service Nexus courant identifié.",
            http_status=status,
            payload=payload,
        )
    return ServiceProbe(
        state="incompatible",
        compatible=False,
        detail="Le port Nexus est occupé par un service ancien ou étranger.",
        http_status=status,
        payload=payload,
    )


def _probe_ollama(
    *,
    opener: Callable[..., Any] = urlopen,
    connector: Callable[..., Any] = socket.create_connection,
) -> OllamaProbe:
    try:
        _status, payload = _http_json(OLLAMA_URL, timeout=1.5, opener=opener)
    except Exception as error:
        if _port_open(11434, connector=connector):
            return OllamaProbe(
                state="unknown",
                conflict=True,
                detail=f"Ollama occupe le port XPU mais son état est illisible: {error}",
            )
        return OllamaProbe(
            state="absent",
            conflict=False,
            detail="Aucun service Ollama actif détecté.",
        )

    models = payload.get("models")
    if not isinstance(models, list):
        return OllamaProbe(
            state="unknown",
            conflict=True,
            detail="Ollama répond sans liste de modèles vérifiable.",
        )
    loaded = tuple(
        str(item.get("name") or item.get("model") or "modèle sans nom")
        for item in models
        if isinstance(item, dict)
    )
    if models:
        return OllamaProbe(
            state="active",
            conflict=True,
            detail="Ollama utilise déjà l'accélérateur local.",
            loaded_models=loaded,
        )
    return OllamaProbe(
        state="idle",
        conflict=False,
        detail="Ollama répond mais aucun modèle n'est chargé.",
    )


def _preflight_issues(paths: RuntimePaths) -> list[str]:
    required_files = {
        "moteur Python de l'application": paths.host_python,
        "moteur Python fenêtré de l'application": (
            paths.host_python.with_name("pythonw.exe")
        ),
        "moteur Python du modèle": paths.model_python,
        "point d'entrée du service": paths.service_entry,
        "point d'entrée du bureau": paths.desktop_entry,
        "manifeste prudent": paths.core_manifest,
        "configuration du modèle": paths.base_model / "config.json",
        "index des poids du modèle": paths.base_model / "model.safetensors.index.json",
        "configuration de l'adaptateur général": (
            paths.general_adapter / "adapter_config.json"
        ),
        "poids de l'adaptateur général": (
            paths.general_adapter / "adapter_model.safetensors"
        ),
        "configuration de l'adaptateur Code": (
            paths.code_adapter / "adapter_config.json"
        ),
        "poids de l'adaptateur Code": (
            paths.code_adapter / "adapter_model.safetensors"
        ),
    }
    issues = [
        f"{label} absent: {path}"
        for label, path in required_files.items()
        if not path.is_file()
    ]
    if len(tuple(paths.base_model.glob("model-*-of-*.safetensors"))) < 2:
        issues.append(f"poids du modèle incomplets: {paths.base_model}")
    return issues


def _native_environment(paths: RuntimePaths) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(ROOT / "src"),
            "MAT_NEXUS_INSTALL_ROOT": str(INSTALL_ROOT),
            "MAT_NEXUS_DATA_ROOT": str(DATA_ROOT),
            "MAT_NEXUS_CONTROL_ROOT": str(INSTALL_ROOT / "config"),
            "MAT_NEXUS_MODEL_ROOT": str(INSTALL_ROOT / "AI"),
            "MAT_NEXUS_INDEX_ROOT": str(INSTALL_ROOT / "indexes"),
            "MAT_NEXUS_BACKUP_ROOT": str(INSTALL_ROOT / "backups"),
            "MAT_NEXUS_MODEL_PYTHON": str(paths.model_python),
            "MAT_NEXUS_MODEL_PATH": str(paths.base_model),
            "MAT_NEXUS_ADAPTER_PATH": str(paths.general_adapter),
            "MAT_NEXUS_CODE_ADAPTER_PATH": str(paths.code_adapter),
            "MAT_NEXUS_PRODUCT_VERSION": EXPECTED_PRODUCT_VERSION,
            "MAT_NEXUS_BUILD_ID": EXPECTED_BUILD_ID,
            "MAT_NEXUS_AI_ENABLED": "1",
        }
    )
    env.pop("MAT_NEXUS_OLLAMA_MODEL", None)
    env.pop("MAT_NEXUS_OLLAMA_URL", None)
    return env


def _service_command(paths: RuntimePaths) -> list[str]:
    return [
        str(paths.host_python),
        str(paths.service_entry),
        "--no-browser",
        "--host",
        "127.0.0.1",
        "--port",
        str(PORT),
        "--service-role",
        EXPECTED_ROLE,
        "--async-injection",
        "--nexus-core-manifest",
        str(paths.core_manifest),
        "--db",
        str(DATA_ROOT / "memory.sqlite3"),
        "--enable-matlm",
        "--matlm-python",
        str(paths.model_python),
        "--matlm-model",
        str(paths.base_model),
        "--matlm-load-mode",
        "bf16",
        "--matlm-max-new-tokens",
        "768",
        "--matlm-timeout-seconds",
        "180",
        "--matlm-adapter",
        str(paths.general_adapter),
        "--matlm-code-adapter",
        str(paths.code_adapter),
    ]


def _start_engine(*, opener: Callable[..., Any] = urlopen) -> dict[str, Any]:
    request = Request(
        f"{BASE_URL}/api/matlm/start",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    _status, payload = _http_json(request, timeout=15.0, opener=opener)
    matlm = payload.get("matlm") if isinstance(payload, dict) else None
    issues = matlm.get("configuration_issues") if isinstance(matlm, dict) else None
    state = matlm.get("state") if isinstance(matlm, dict) else None
    if not (
        payload.get("ok") is True
        and isinstance(matlm, dict)
        and matlm.get("enabled") is True
        and matlm.get("configured") is True
        and state in {"starting", "ready", "busy"}
        and (issues is None or issues == [])
    ):
        raise RuntimeError(
            "Le moteur natif n'a pas confirmé une configuration complète."
        )
    return matlm


def _wait_engine_ready(
    *,
    timeout_seconds: float = 420.0,
    opener: Callable[..., Any] = urlopen,
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    deadline = monotonic() + timeout_seconds
    last_status: dict[str, Any] = {}
    while monotonic() < deadline:
        _http_status, payload = _http_json(
            f"{BASE_URL}/api/matlm/status", timeout=3.0, opener=opener
        )
        status = payload.get("matlm") if isinstance(payload, dict) else None
        if isinstance(status, dict):
            last_status = status
            if (
                status.get("configured") is True
                and status.get("running") is True
                and status.get("model_loaded") is True
                and status.get("state") == "ready"
            ):
                return status
            if status.get("state") == "error":
                raise RuntimeError(
                    "Le moteur natif a signalé une erreur pendant le chargement: "
                    + str(status.get("last_error") or "erreur non détaillée")
                )
        sleeper(1.0)
    raise TimeoutError(
        "Le modèle natif n'est pas devenu prêt dans le délai prévu; "
        f"dernier état: {last_status.get('state', 'inconnu')}."
    )


def _smoke_native_answer(
    *, opener: Callable[..., Any] = urlopen
) -> dict[str, Any]:
    payload = {
        "question": "Allo",
        "request_id": f"native-smoke-{os.getpid()}",
        "language": "fr",
        "mode": "general",
        "interaction_mode": "general",
    }
    request = Request(
        f"{BASE_URL}/api/matlm/ask",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    http_status, answer = _http_json(request, timeout=240.0, opener=opener)
    details = answer.get("details") if isinstance(answer, dict) else None
    runtime = details.get("runtime") if isinstance(details, dict) else None
    reply = answer.get("reply") if isinstance(answer, dict) else None
    structured_answer = answer.get("answer") if isinstance(answer, dict) else None
    abstention = (
        structured_answer.get("abstention")
        if isinstance(structured_answer, dict)
        else None
    )
    if not (
        http_status == 200
        and answer.get("ok") is True
        and answer.get("intent") == "matlm"
        and isinstance(reply, str)
        and bool(reply.strip())
        and isinstance(abstention, dict)
        and abstention.get("abstained") is False
        and isinstance(runtime, dict)
        and runtime.get("provider") == "granite"
        and runtime.get("nexus_applied") is True
    ):
        observed = {
            "http_status": http_status,
            "ok": answer.get("ok"),
            "intent": answer.get("intent"),
            "reply_nonempty": isinstance(reply, str) and bool(reply.strip()),
            "abstained": (
                abstention.get("abstained") if isinstance(abstention, dict) else None
            ),
            "provider": runtime.get("provider") if isinstance(runtime, dict) else None,
            "nexus_applied": (
                runtime.get("nexus_applied") if isinstance(runtime, dict) else None
            ),
            "error": answer.get("error"),
        }
        raise RuntimeError(
            "La réponse smoke n'a pas fourni la preuve du moteur natif Nexus: "
            + json.dumps(observed, ensure_ascii=False, sort_keys=True)
        )
    return answer


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
        # The service process owned below remains the final bounded cleanup.
        # A foreign service is never stopped here.
        pass


def _kernel32() -> Any:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel32.WaitForSingleObject.restype = ctypes.c_uint32
    kernel32.ReleaseMutex.argtypes = [ctypes.c_void_p]
    kernel32.ReleaseMutex.restype = ctypes.c_bool
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_bool
    return kernel32


def _acquire_named_mutex(
    name: str, *, reject_existing_object: bool = False
) -> int | None:
    kernel32 = _kernel32()
    ctypes.set_last_error(0)
    handle = kernel32.CreateMutexW(None, False, name)
    if not handle:
        raise OSError(f"Impossible de créer le verrou Windows: {name}")
    already_exists = ctypes.get_last_error() == ERROR_ALREADY_EXISTS
    if reject_existing_object and already_exists:
        kernel32.CloseHandle(ctypes.c_void_p(handle))
        return None
    outcome = kernel32.WaitForSingleObject(ctypes.c_void_p(handle), 0)
    if outcome in {WAIT_OBJECT_0, WAIT_ABANDONED}:
        return int(handle)
    kernel32.CloseHandle(ctypes.c_void_p(handle))
    return None


def _release_named_mutex(handle: int) -> None:
    kernel32 = _kernel32()
    native_handle = ctypes.c_void_p(handle)
    kernel32.ReleaseMutex(native_handle)
    kernel32.CloseHandle(native_handle)


def _acquire_runtime_mutexes() -> tuple[list[int], str | None]:
    handles: list[int] = []
    for index, name in enumerate((GLOBAL_MUTEX_NAME, *LEGACY_MUTEX_NAMES)):
        handle = _acquire_named_mutex(
            name,
            reject_existing_object=index > 0,
        )
        if handle is None:
            for acquired in reversed(handles):
                _release_named_mutex(acquired)
            return [], name
        handles.append(handle)
    return handles, None


def _preflight_report(paths: RuntimePaths) -> tuple[dict[str, Any], bool]:
    issues = _preflight_issues(paths)
    service = _probe_service()
    ollama = _probe_ollama()
    report = {
        "schema_version": "nexus-native-supervisor-preflight-v1",
        "timestamp_utc": _utc_now(),
        "paths": {key: str(value) for key, value in asdict(paths).items()},
        "issues": issues,
        "service": asdict(service),
        "ollama": asdict(ollama),
        "safe_to_start": (
            not issues
            and not ollama.conflict
            and service.state in {"absent", "compatible"}
        ),
    }
    return report, bool(report["safe_to_start"])


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Superviseur natif Nexus")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--preflight-only",
        action="store_true",
        help="Vérifie les chemins, le port et les conflits sans lancer Nexus.",
    )
    actions.add_argument(
        "--smoke-native",
        action="store_true",
        help="Charge le moteur natif, vérifie une réponse, puis l'arrête.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    paths = RuntimePaths.current()

    def notify_failure(text: str) -> None:
        if args.smoke_native:
            print(text, file=sys.stderr, flush=True)
        else:
            _message(text)

    if args.preflight_only:
        report, safe = _preflight_report(paths)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if safe else 10

    handles, blocked_mutex = _acquire_runtime_mutexes()
    if blocked_mutex is not None:
        notify_failure(
            "Une autre instance Nexus ou un ancien lanceur utilise déjà le moteur local.\n"
            "Fermez cette instance, puis relancez Nexus."
        )
        return 9

    owned_service = False
    service: subprocess.Popen[bytes] | None = None
    log = None
    desktop_log = None
    try:
        LOG_ROOT.mkdir(parents=True, exist_ok=True)
        _append_event("supervisor_start", pid=os.getpid())

        issues = _preflight_issues(paths)
        if issues:
            _append_event("preflight_failed", issues=issues)
            notify_failure("Nexus est incomplet :\n\n" + "\n".join(issues))
            return 2

        ollama = _probe_ollama()
        _append_event("ollama_probe", **asdict(ollama))
        if ollama.conflict:
            loaded = ", ".join(ollama.loaded_models) or "état inconnu"
            notify_failure(
                "Nexus n'a rien arrêté. Ollama utilise déjà le moteur local.\n\n"
                f"Modèles détectés : {loaded}\n"
                "Fermez Ollama volontairement, puis relancez Nexus."
            )
            return 7

        probe = _probe_service()
        _append_event("service_probe", **asdict(probe))
        if probe.state not in {"absent", "compatible"}:
            notify_failure(
                "Nexus n'a rien arrêté. Le port 8765 appartient à un ancien "
                "service ou à un autre programme.\n\n"
                "Fermez-le volontairement, puis relancez Nexus."
            )
            return 8

        env = _native_environment(paths)
        log = (LOG_ROOT / "nexus-current-service.log").open("ab", buffering=0)
        desktop_log = (LOG_ROOT / "nexus-current-desktop.log").open(
            "ab", buffering=0
        )
        if probe.state == "absent":
            service = subprocess.Popen(
                _service_command(paths),
                cwd=ROOT,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=CREATE_NO_WINDOW,
            )
            owned_service = True
            _append_event("service_spawned", pid=service.pid)
            deadline = time.monotonic() + 120.0
            while time.monotonic() < deadline:
                if service.poll() is not None:
                    _append_event("service_early_exit", exit_code=service.returncode)
                    notify_failure(
                        "Le service Nexus s'est arrêté. Consultez "
                        "nexus-current-service.log."
                    )
                    return 3
                current = _probe_service()
                if current.compatible:
                    break
                # A newly spawned Python service can bind the port before its
                # HTTP handler is ready. Only a decoded, wrong identity is a
                # conclusive collision; an unreadable port remains transient
                # until the bounded startup deadline.
                if current.state == "incompatible":
                    _append_event("service_identity_rejected", **asdict(current))
                    notify_failure(
                        "Le service démarré n'a pas l'identité Nexus attendue."
                    )
                    return 8
                time.sleep(0.5)
            else:
                _append_event("service_start_timeout", timeout_seconds=120)
                notify_failure("Le service Nexus n'a pas démarré dans le délai prévu.")
                return 4

        matlm = _start_engine()
        _append_event(
            "engine_start_accepted",
            state=matlm.get("state"),
            worker_pid=matlm.get("worker_pid"),
        )

        if args.smoke_native:
            ready = _wait_engine_ready()
            _append_event(
                "engine_ready",
                state=ready.get("state"),
                worker_pid=ready.get("worker_pid"),
            )
            answer = _smoke_native_answer()
            details = answer.get("details", {})
            runtime = details.get("runtime", {}) if isinstance(details, dict) else {}
            _append_event(
                "native_smoke_passed",
                reply_characters=len(str(answer.get("reply", ""))),
                provider=runtime.get("provider"),
                model=runtime.get("model"),
                nexus_applied=runtime.get("nexus_applied"),
            )
            return 0

        desktop = subprocess.Popen(
            [
                str(paths.host_python.with_name("pythonw.exe")),
                str(paths.desktop_entry),
                "--host",
                "127.0.0.1",
                "--port",
                str(PORT),
                "--no-auto-server",
            ],
            cwd=ROOT,
            env=env,
            stdout=desktop_log,
            stderr=subprocess.STDOUT,
            creationflags=CREATE_NO_WINDOW,
        )
        _append_event("desktop_spawned", pid=desktop.pid)
        exit_code = desktop.wait()
        desktop_log.write(f"desktop_exit_code={exit_code}\n".encode("utf-8"))
        _append_event("desktop_exit", exit_code=exit_code)
        return exit_code
    except Exception as error:
        try:
            _append_event(
                "supervisor_error",
                error_type=type(error).__name__,
                error=str(error),
            )
        except Exception:
            pass
        notify_failure(f"Nexus n'a pas pu démarrer : {error}")
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
        if log is not None:
            log.close()
        if desktop_log is not None:
            desktop_log.close()
        for handle in reversed(handles):
            _release_named_mutex(handle)


if __name__ == "__main__":
    raise SystemExit(main())
