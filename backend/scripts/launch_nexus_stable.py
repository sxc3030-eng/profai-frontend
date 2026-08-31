#!/usr/bin/env python3
"""Lanceur Nexus stable — sépare le service du desktop.

Avantage sur le superviseur précédent : le service Nexus (MATMEM + MoE + LLM)
reste actif après la fermeture de l'interface. Ainsi, au prochain clic,
l'interface s'ouvre immédiatement (le modèle reste chargé) au lieu de
redémarrer tout le service (attente de plusieurs centaines de secondes).

Flux :
  1. Vérifie que le service répond sur /api/health ; sinon le lance.
  2. Démarre le moteur MAT-LM si nécessaire.
  3. Lance la fenêtre desktop (client seul).
  4. Attend la fermeture du desktop SANS arrêter le service (géré par le
     watchdog en arrière-plan).

Usage:
  pythonw scripts/launch_nexus_stable.py [--host H] [--port P]
"""
from __future__ import annotations

import argparse
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PORT = 8765
BASE_URL = f"http://127.0.0.1:{PORT}"


def _nexus_window_visible() -> bool:
    """Vrai si une fenêtre Nexus est déjà ouverte.

    Évite de lancer un second desktop si l'interface est déjà affichée
    (double-clic ou clics répétés sur le raccourci).
    """
    try:
        return bool(ctypes.windll.user32.FindWindowW(None, "Nexus"))
    except (AttributeError, OSError):
        return False


def _health() -> bool:
    try:
        with urlopen(f"{BASE_URL}/api/health", timeout=2.0) as response:
            payload = json.loads(response.read(65_536).decode("utf-8"))
        return payload.get("ok") is True
    except Exception:
        return False


def _launch_service() -> subprocess.Popen[bytes]:
    """Lance le service Nexus détaché et retourne le processus."""
    # Utilise python.exe (avec console) plutôt que pythonw.exe : le service
    # est plus stable et les erreurs de démarrage sont visibles dans le log.
    python = _python_exe()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    log_root = Path(r"D:\LLM Mat\data\logs")
    log_root.mkdir(parents=True, exist_ok=True)
    log = (log_root / "nexus-stable-service.log").open("ab", buffering=0)
    command = [
        str(python), str(ROOT / "start_agent.py"), "--no-browser",
        "--host", "127.0.0.1", "--port", str(PORT),
        "--service-role", "desktop", "--async-injection",
        "--nexus-core-manifest",
        str(ROOT / "src" / "memory_agent" / "manifests"
             / "mat9f-public-prudent-core-manifest-v1.json"),
        "--db", str(r"D:\LLM Mat\data\memory.sqlite3"),
        "--enable-matlm",
        "--matlm-python", str(r"D:\LLM Mat\AI\.venv\Scripts\python.exe"),
        "--matlm-model",
        str(r"D:\LLM Mat\AI\models\granite-3.3-2b-instruct"),
        "--matlm-load-mode", "bf16",
        "--matlm-max-new-tokens", "384",
        "--matlm-timeout-seconds", "300",
        "--matlm-adapter", str(r"D:\LLM Mat\AI\adapters\nexus-bridge"),
        "--matlm-code-adapter", str(r"D:\LLM Mat\AI\adapter_code_planner"),
    ]
    return subprocess.Popen(
        command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
        stdout=log, stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _warm_wait_service(timeout: float = 15.0) -> None:
    """Attend brièvement que le service ouvre son port (préchauffage).

    N'attend PAS le chargement GPU complet. Le desktop est lancé juste après ;
    il affiche « connexion… » puis « prêt » quand le moteur est disponible.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _health():
            return
        time.sleep(0.25)


def _python_exe() -> Path:
    """Trouve un python.exe valide (celui qui exécute ce script si possible)."""
    exec_path = Path(sys.executable).resolve()
    candidate = exec_path.with_name("python.exe")
    if candidate.is_file():
        return candidate
    # Fallback : chercher dans packaging-python puis venv ML.
    for base in (ROOT / "tools" / "packaging-python", Path(r"D:\LLM Mat\AI\.venv")):
        executable = base / "Scripts" / "python.exe"
        if executable.is_file():
            return str(executable)
    return "python.exe"


def _pythonw() -> Path:
    """Trouve un python.exe valide pour lancer le desktop.

    On utilise python.exe (avec console) plutôt que pythonw.exe : sous pythonw,
    un crash Tkinter natif est silencieux et la fenêtre n'apparaît jamais.
    Avec python.exe, les erreurs sont visibles et le desktop est plus stable.
    """
    return _python_exe()


def main() -> int:
    parser = argparse.ArgumentParser(description="Lanceur Nexus stable")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    pythonw = _pythonw()
    # PYTHONPATH=src est ESSENTIEL pour le desktop : start_desktop.py fait
    # "from memory_agent.desktop_app import main". Sans lui, l'import échoue
    # silencieusement sous pythonw (sans console) et la fenêtre n'apparaît
    # jamais — bug "ça n'ouvre pas de fenêtre".
    desktop_env = os.environ.copy()
    desktop_env["PYTHONPATH"] = str(ROOT / "src")
    # Le desktop lit aussi le profil d'installation via les variables MAT_NEXUS_*.
    # Sans elles, load_install_profile() retombe sur des valeurs par défaut
    # vides et le desktop peut crasher à la recherche du modèle/adaptateur.
    desktop_env.update(
        {
            "MAT_NEXUS_INSTALL_ROOT": r"D:\LLM Mat",
            "MAT_NEXUS_DATA_ROOT": r"D:\LLM Mat\data",
            "MAT_NEXUS_CONTROL_ROOT": r"D:\LLM Mat\config",
            "MAT_NEXUS_MODEL_ROOT": r"D:\LLM Mat\AI",
            "MAT_NEXUS_INDEX_ROOT": r"D:\LLM Mat\indexes",
            "MAT_NEXUS_BACKUP_ROOT": r"D:\LLM Mat\backups",
            "MAT_NEXUS_MODEL_PYTHON": r"D:\LLM Mat\AI\.venv\Scripts\python.exe",
            "MAT_NEXUS_MODEL_PATH": r"D:\LLM Mat\AI\models\granite-3.3-2b-instruct",
            "MAT_NEXUS_ADAPTER_PATH": r"D:\LLM Mat\AI\adapters\nexus-bridge",
            "MAT_NEXUS_CODE_ADAPTER_PATH": r"D:\LLM Mat\AI\adapter_code_planner",
            "MAT_NEXUS_PRODUCT_VERSION": "0.9.2-dev",
            "MAT_NEXUS_BUILD_ID": "nexus-moe-native-0.9.2-dev",
            "MAT_NEXUS_AI_ENABLED": "1",
        }
    )
    desktop_env.pop("MAT_NEXUS_OLLAMA_MODEL", None)
    desktop_env.pop("MAT_NEXUS_OLLAMA_URL", None)

    # Garde anti-double-lancement : si la fenêtre Nexus est déjà ouverte, on
    # la ramène au premier plan au lieu d'en créer une seconde.
    if _nexus_window_visible():
        try:
            ctypes.windll.user32.ShowWindow(
                ctypes.windll.user32.FindWindowW(None, "Nexus"), 9  # SW_RESTORE
            )
        except (AttributeError, OSError):
            pass
        print("[launch] Nexus déjà ouvert — fenêtre ramenée au premier plan", flush=True)
        return 0

    # Lance le service en arrière-plan SANS bloquer la fenêtre. S'il est déjà
    # actif, on le réutilise. La fenêtre s'ouvre immédiatement ; l'interface
    # affiche "connexion…" puis "prêt" quand le service répond.
    if not _health():
        print("[launch] service absent, lancement en cours…", flush=True)
        service = _launch_service()
        # Préchauffage court pour ouvrir le port du service (pas le modèle GPU).
        _warm_wait_service(15.0)
    else:
        service = None

    desktop_log = (Path(r"D:\LLM Mat\data\logs")
                   / "nexus-stable-desktop.log").open("ab", buffering=0)
    # --no-auto-server : le desktop se connecte au service déjà lancé par ce
    # lanceur et ne démarre PAS son propre service. Évite le double chargement
    # du modèle XPU (2 workers qui se bloquent mutuellement).
    desktop = subprocess.Popen(
        [
            pythonw, str(ROOT / "start_desktop.py"), "--host", args.host,
            "--port", str(args.port), "--no-auto-server",
        ],
        cwd=ROOT,
        env=desktop_env,
        stdout=desktop_log, stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    # On attend la fermeture de la fenêtre. Le service n'est PAS arrêté :
    # il reste actif pour un redémarrage rapide, géré par le watchdog.
    exit_code = desktop.wait()
    desktop_log.write(f"desktop_exit_code={exit_code}\n".encode("utf-8"))
    desktop_log.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())