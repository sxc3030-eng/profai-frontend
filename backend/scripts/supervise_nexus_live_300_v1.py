#!/usr/bin/env python3
"""Persistently recover Nexus/Granite and resume the live-300 qualification."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"D:\MAT-9F")
OUT = ROOT / "nexus-live-300-v1"
PYTHON = Path(r"D:\LLM Mat\AI\.venv\Scripts\python.exe")
SERVICE = Path(r"D:\LLM Mat\MATNexusService\MATNexusService.exe")
SERVICE_ARGS = [
    "--no-browser", "--host", "127.0.0.1", "--port", "8765",
    "--service-role", "desktop", "--async-injection", "--enable-matlm",
    "--matlm-load-mode", "bf16", "--matlm-max-new-tokens", "384",
    "--matlm-timeout-seconds", "180",
    "--matlm-python", r"D:\LLM Mat\AI\.venv\Scripts\python.exe",
    "--matlm-model", r"D:\LLM Mat\AI\models\granite-3.3-2b-instruct",
    "--matlm-adapter", r"D:\LLM Mat\AI\adapters\nexus-bridge",
]


def write(state: str, **extra: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": "mat9f-nexus-live-300-supervisor-v1", "state": state,
               "updated_at": datetime.now(timezone.utc).isoformat(), **extra}
    path = OUT / "supervisor-status.json"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def matlm() -> dict[str, object] | None:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/api/matlm/status", timeout=5) as response:
            value = json.load(response)
        candidate = value.get("matlm") if isinstance(value, dict) else None
        return candidate if isinstance(candidate, dict) else None
    except Exception:
        return None


def service_port_open() -> bool:
    """Avoid spawning a second service during a transient HTTP failure."""
    try:
        with socket.create_connection(("127.0.0.1", 8765), timeout=1):
            return True
    except OSError:
        return False


def process_alive(pid: object) -> bool:
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def acquire_lock(path: Path):
    """Acquire the supervisor lock, recovering only a proven stale owner."""
    try:
        return path.open("x", encoding="utf-8")
    except FileExistsError:
        try:
            owner = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise SystemExit("live-300 supervisor lock is unreadable")
        if process_alive(owner.get("pid") if isinstance(owner, dict) else None):
            raise SystemExit("live-300 supervisor already registered")
        path.unlink(missing_ok=True)
        try:
            return path.open("x", encoding="utf-8")
        except FileExistsError:
            raise SystemExit("live-300 supervisor lock was reacquired concurrently")


def post(path: str) -> None:
    request = urllib.request.Request("http://127.0.0.1:8765" + path, data=b"{}",
                                     headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=30):
        pass


def valid_count() -> int:
    path = OUT / "results.jsonl"
    if not path.exists():
        return 0
    count = 0
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            break
        case_id = row.get("case_id") if isinstance(row, dict) else None
        expected_prefix = f"live300-{count + 1:03d}-"
        if (
            not isinstance(row, dict)
            or row.get("passed") is not True
            or not isinstance(case_id, str)
            or not case_id.startswith(expected_prefix)
            or case_id in seen
        ):
            break
        seen.add(case_id)
        count += 1
    return min(count, 300)


def start_service(attempt: int) -> subprocess.Popen[bytes]:
    stdout = (OUT / f"supervisor-service-{attempt:03d}-stdout.log").open("ab")
    stderr = (OUT / f"supervisor-service-{attempt:03d}-stderr.log").open("ab")
    try:
        return subprocess.Popen([str(SERVICE), *SERVICE_ARGS], cwd=ROOT, stdin=subprocess.DEVNULL,
                                stdout=stdout, stderr=stderr, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    finally:
        stdout.close()
        stderr.close()


def ensure_ready(attempt: int, deadline: float) -> bool:
    process: subprocess.Popen[bytes] | None = None
    last_load_request = 0.0
    while time.monotonic() < deadline:
        state = matlm()
        if state is None:
            if service_port_open():
                # A process owns the port but its status route is temporarily
                # unavailable. Starting another executable could duplicate Granite.
                time.sleep(5)
                continue
            if process is None or process.poll() is not None:
                process = start_service(attempt)
                write("STARTING_SERVICE", attempt=attempt, service_pid=process.pid, valid=valid_count())
            time.sleep(5)
            continue
        if state.get("state") == "ready" and state.get("model_loaded") is True:
            stable = time.monotonic()
            while time.monotonic() - stable < 20:
                check = matlm()
                if not isinstance(check, dict) or check.get("state") != "ready":
                    break
                time.sleep(5)
            else:
                return True
        if state.get("state") in {"error", "stopped"} or not state.get("running"):
            if time.monotonic() - last_load_request >= 30:
                try:
                    post("/api/matlm/start")
                    last_load_request = time.monotonic()
                    write("LOADING_GRANITE", attempt=attempt, valid=valid_count())
                except Exception:
                    pass
        time.sleep(5)
    return False


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    lock = OUT / "supervisor-running.lock"
    handle = acquire_lock(lock)
    handle.write(json.dumps({"pid": __import__("os").getpid(), "started_at": datetime.now(timezone.utc).isoformat()}) + "\n")
    handle.flush()
    overall_deadline = time.monotonic() + 72 * 3600
    attempt = 0
    try:
        while time.monotonic() < overall_deadline and valid_count() < 300:
            attempt += 1
            ready = ensure_ready(attempt, min(overall_deadline, time.monotonic() + 900))
            state = matlm()
            if (
                not ready
                or not isinstance(state, dict)
                or state.get("state") != "ready"
                or state.get("model_loaded") is not True
            ):
                write("RECOVERING_SERVICE", attempt=attempt, valid=valid_count())
                time.sleep(10)
                continue
            write("RUNNING_300", attempt=attempt, valid=valid_count())
            result = subprocess.run([str(PYTHON), str(ROOT / "scripts" / "run_nexus_directed_300_v1.py"), "--resume"],
                                    cwd=ROOT, check=False)
            write("RECOVERING" if result.returncode else "VERIFYING", attempt=attempt,
                  valid=valid_count(), runner_returncode=result.returncode)
            if valid_count() < 300:
                time.sleep(15)
        count = valid_count()
        state = "COMPLETED_300_PASS" if count == 300 else "BLOCKED_TIMEOUT"
        write(state, valid=count, attempts=attempt,
              next_gate="BENCHMARK_AND_CERTIFICATION" if count == 300 else None,
              hugging_face_published=False)
        if count == 300:
            marker = OUT / "READY_FOR_BENCHMARK"
            temporary = marker.with_name(marker.name + ".tmp")
            temporary.write_text("300/300 live transport checks passed\n", encoding="utf-8")
            temporary.replace(marker)
        return 0 if count == 300 else 2
    finally:
        handle.close()
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
