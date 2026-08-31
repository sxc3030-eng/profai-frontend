#!/usr/bin/env python3
"""Watchdog Nexus v1 — surveille le serveur MAT-9F et le relance en cas de panne.

Le watchdog vérifie périodiquement la santé du serveur Nexus (MATMEM + MoE +
LLM Granite) via l'endpoint /api/health. Si le serveur ne répond plus ou si le
processus est sorti, il le relance automatiquement avec la même configuration
et attend qu'il soit de nouveau prêt.

Usage:
  python scripts/nexus_watchdog_v1.py --port 8765
  python scripts/nexus_watchdog_v1.py --port 8765 --check-interval 15 --max-miss 3
  python scripts/nexus_watchdog_v1.py --port 8765 --log reports/watchdog.log

Le watchdog est conçu pour tourner en arrière-plan (fenêtre cachée) et peut
être lancé au démarrage de Windows via le fichier d'installation.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER_MODULE = "memory_agent.server"
DEFAULT_MATLM_PYTHON = Path(r"D:\LLM Mat\AI\.venv\Scripts\python.exe")
DEFAULT_MATLM_MODEL = Path(r"D:\LLM Mat\AI\models\granite-3.3-2b-instruct")
DEFAULT_DB = Path(r"D:\LLM Mat\data\memory.sqlite3")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _log(message: str, log_path: Path | None = None) -> None:
    line = f"[{_now()}] {message}"
    print(line, flush=True)
    if log_path is not None:
        try:
            with open(log_path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            pass


def _health_ok(base_url: str, timeout: float = 5.0) -> bool:
    """Vérifie que le serveur répond correctement sur /api/health."""
    try:
        req = urllib.request.Request(base_url + "/api/health", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return False
            body = resp.read()
            try:
                parsed = json.loads(body)
            except Exception:
                return False
            # Le serveur MAT-9F expose un champ "ok" ou "engine" selon la version.
            return bool(parsed.get("ok", True)) or parsed.get("engine") == "memory"
    except Exception:
        return False


def _server_process_alive(server: subprocess.Popen | None) -> bool:
    if server is None:
        return False
    return server.poll() is None


def _port_in_use(port: int) -> bool:
    """Détecte si le port est déjà occupé par un processus local.

    Évite l'erreur "ressource déjà utilisée" (address already in use) quand
    un serveur tourne déjà sur le même port. On tente une connexion TCP
    simple : si elle aboutit, le port est occupé.
    """
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(1.0)
        result = sock.connect_ex(("127.0.0.1", port))
        return result == 0
    except Exception:
        return False
    finally:
        sock.close()


def _launch_server(
    args: argparse.Namespace,
    log_path: Path,
) -> subprocess.Popen:
    """Lance le serveur complet (MATMEM + MoE + LLM) avec le venv ML."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    cmd = [
        str(args.matlm_python), "-u", "-m", SERVER_MODULE,
        "--port", str(args.port),
        "--db", str(args.db),
        "--enable-matlm",
        "--matlm-model", str(args.matlm_model),
        "--matlm-python", str(args.matlm_python),
        "--matlm-timeout-seconds", str(args.matlm_timeout_seconds),
        "--matlm-max-new-tokens", str(args.matlm_max_new_tokens),
        "--matlm-load-mode", "bf16",
        "--matlm-adapter",
        str(Path(r"D:\LLM Mat\AI\adapters\nexus-bridge")),
        "--matlm-code-adapter",
        str(Path(r"D:\LLM Mat\AI\adapter_code_planner")),
        "--service-role", "desktop",
        "--async-injection",
        "--nexus-core-manifest",
        str(ROOT / "src" / "memory_agent" / "manifests" /
            "mat9f-public-prudent-core-manifest-v1.json"),
    ]
    _log("lancement serveur: " + " ".join(cmd), log_path)
    # Rediriger stdout/stderr vers un fichier (jamais un pipe non lu, sinon le
    # buffer se remplit et le serveur se bloque).
    server_log = log_path.with_suffix(".server.log")
    server_logfh = open(server_log, "a", encoding="utf-8", errors="replace")
    return subprocess.Popen(
        cmd, cwd=ROOT, env=env, stdout=server_logfh, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )


def _wait_ready(
    args: argparse.Namespace,
    server: subprocess.Popen,
    log_path: Path,
    timeout: float = 900.0,
) -> bool:
    """Attend que le serveur réponde sur /api/health (jusqu'à timeout s)."""
    base = f"http://127.0.0.1:{args.port}"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _server_process_alive(server):
            _log("serveur sorti avant d'être prêt", log_path)
            return False
        if _health_ok(base):
            return True
        time.sleep(2)
    _log("serveur non prêt après le délai", log_path)
    return False


def _start_matlm(args: argparse.Namespace, log_path: Path) -> bool:
    """Démarre le worker MAT-LM (LLM) et attend le chargement du modèle."""
    base = f"http://127.0.0.1:{args.port}"
    try:
        req = urllib.request.Request(
            base + "/api/matlm/start",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
    except Exception as error:
        _log(f"matlm/start échec: {error}", log_path)
        return False

    # Attendre le chargement du modèle (jusqu'à 900s).
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(base + "/api/matlm/status", method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read())
            m = body.get("matlm", body)
            if isinstance(m, dict) and m.get("model_loaded") is True:
                _log("modèle Granite chargé", log_path)
                return True
        except Exception:
            pass
        time.sleep(2)
    _log("AVERTISSEMENT: modèle non chargé après 900s", log_path)
    return False


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--matlm-python", type=Path, default=DEFAULT_MATLM_PYTHON)
    p.add_argument("--matlm-model", type=Path, default=DEFAULT_MATLM_MODEL)
    p.add_argument("--matlm-timeout-seconds", type=int, default=300)
    p.add_argument("--matlm-max-new-tokens", type=int, default=256)
    p.add_argument("--check-interval", type=float, default=10.0,
                   help="intervalle entre vérifications de santé (s)")
    p.add_argument("--max-missed", type=int, default=3,
                   help="nombre d'échecs consécutifs avant redémarrage")
    p.add_argument("--log", type=Path, default=ROOT / "reports" / "watchdog.log")
    p.add_argument("--no-matlm", action="store_true",
                   help="ne pas redémarrer le worker MAT-LM après un crash")
    args = p.parse_args()

    args.db.parent.mkdir(parents=True, exist_ok=True)
    args.log.parent.mkdir(parents=True, exist_ok=True)

    base = f"http://127.0.0.1:{args.port}"
    server: subprocess.Popen | None = None
    missed = 0
    restarts = 0

    _log(f"watchdog Nexus démarré (port {args.port}, intervalle {args.check_interval}s)", args.log)

    while True:
        if server is None or not _server_process_alive(server):
            # Le serveur est absent ou est sorti. Avant de relancer, vérifions
            # si un serveur sain tourne déjà sur le port (évite l'erreur
            # "ressource déjà utilisée" quand une autre instance est active).
            if _port_in_use(args.port) and _health_ok(base):
                _log("un serveur sain tourne déjà sur le port — adoption", args.log)
                server = None
                missed = 0
                time.sleep(args.check_interval)
                continue
            if server is not None:
                restarts += 1
                _log(f"SERVEUR SORTI — redémarrage #{restarts}", args.log)
            server = _launch_server(args, args.log)
            if not _wait_ready(args, server, args.log):
                _log("serveur non prêt, nouvel essai dans 30s", args.log)
                time.sleep(30)
                continue
            _log("serveur prêt", args.log)
            if not args.no_matlm:
                _ensure_model(args, args.log)
            missed = 0
            continue

        # Le serveur tourne : vérifions sa santé.
        if _health_ok(base):
            missed = 0
        else:
            missed += 1
            _log(f"santé KO ({missed}/{args.max_missed})", args.log)
            if missed >= args.max_missed:
                restarts += 1
                _log(f"redémarrage forcé #{restarts} (santé KO)", args.log)
                server.terminate()
                try:
                    server.wait(timeout=10)
                except Exception:
                    server.kill()
                server = None
                missed = 0
                continue

        time.sleep(args.check_interval)


if __name__ == "__main__":
    raise SystemExit(main())