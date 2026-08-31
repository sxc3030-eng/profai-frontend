#!/usr/bin/env python3
"""Harnais de test de stabilité Nexus (MATMEM + MoE + LLM Granite).

Lance le serveur complet (memory_agent.server) avec les trois couches
actives, puis envoie en continu des requêtes HTTP représentatives et
collecte des métriques fiables de stabilité (latence, erreurs, validité).

Usage:
  python scripts/stability_test_nexus_v1.py --duration 14400 --port 8765
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
SERVER_MODULE = "memory_agent.server"

QUESTIONS = [
    "Quelle est la stratégie de cache pour une API ?",
    "Analyse le risque de sécurité d'une clé API exposée dans l'URL.",
    "Comment optimiser une requête SQL lente avec jointure ?",
    "Évalue la complétude et la fraîcheur d'un pipeline de données.",
    "Quelle est la politique de rétention des données ?",
    "Comment gérer l'escalade d'un incident critique ?",
    "Quelle est la meilleure pratique pour le versioning d'une API ?",
    "Analyse la qualité des données d'un entrepôt.",
    "Comment planifier la capacité d'un cluster Kubernetes ?",
    "Quelle est la stratégie de sauvegarde et de restauration ?",
]


# Preuves à injecter dans MATMEM pour que le pipeline MATMEM→MoE→LLM
# s'exécute réellement (sans évidence, mode grounded → abstention, Granite
# n'est jamais appelé). Chaque preuve est un souvenir user_confirmed dont les
# termes recoupent une question du test.
SEED_EVIDENCE = [
    "La stratégie de cache pour une API repose sur le contrôle de la fraîcheur, "
    "l'invalidation par clé et la mise en cache des réponses idempotentes.",
    "Une clé API exposée dans l'URL présente un risque de sécurité élevé car elle "
    "peut être interceptée et réutilisée sans autorisation.",
    "Une requête SQL lente avec jointure s'optimise par l'indexation des colonnes "
    "de jointure et la réduction du nombre de lignes parcourues.",
    "La complétude et la fraîcheur d'un pipeline de données s'évaluent par la "
    "couverture des sources et la latence de mise à jour des agrégats.",
    "La politique de rétention des données définit la durée de conservation et la "
    "procédure de suppression sécurisée des informations.",
    "L'escalade d'un incident critique suit une procédure de priorisation, de "
    "notification et de remontée vers les responsables disponibles.",
    "Le versioning d'une API suit la compatibilité sémantique et la gestion des "
    "versions majeures et mineures sans rupture.",
    "La qualité des données d'un entrepôt s'analyse par l'exactitude, la "
    "complétude, la cohérence et l'actualité des enregistrements.",
    "La planification de la capacité d'un cluster Kubernetes évalue la charge, "
    "l'autoscaling et la réservation des ressources par nœud.",
    "La stratégie de sauvegarde et de restauration définit la fréquence des "
    "sauvegardes, la rétention et les tests de restauration.",
]


def seed_memory(db_path: Path, python: Path) -> None:
    """Injecte des preuves user_confirmed dans la base MATMEM avant le test.

    Utilise le même venv ML et le même PYTHONPATH=src que le serveur pour
    garantir un schéma identique. Idempotent : observe() avec une clé
    idempotente ne crée pas de doublon.
    """
    import os
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    code = (
        "import sys\n"
        "from pathlib import Path\n"
        "from memory_agent.memory import MemoryEngine\n"
        "db = Path(sys.argv[1])\n"
        "engine = MemoryEngine(db)\n"
        "for i, text in enumerate(sys.argv[2:]):\n"
        "    engine.observe(\n"
        "        text,\n"
        "        episode_id=f'seed-{i}',\n"
        "        source='user_confirmed',\n"
        "        idempotency_key=f'stability-seed-{i}',\n"
        "    )\n"
        "engine.close()\n"
        "print('SEED_OK')\n"
    )
    args = [str(python), "-c", code, str(db_path), *SEED_EVIDENCE]
    result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        print("[stability] AVERTISSEMENT: échec de l'injection de preuves:", flush=True)
        print(result.stdout[-2000:], flush=True)
        print(result.stderr[-2000:], flush=True)
    else:
        print("[stability] preuves injectées dans MATMEM:", flush=True)


def http_json(method: str, url: str, payload: dict | None = None, timeout: float = 300.0):
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            latency = time.monotonic() - start
            try:
                parsed = json.loads(body)
            except Exception:
                parsed = {"_raw": body[:200].decode("utf-8", "replace")}
            return {"status": resp.status, "latency": latency, "body": parsed}
    except urllib.error.HTTPError as e:
        latency = time.monotonic() - start
        try:
            parsed = json.loads(e.read())
        except Exception:
            parsed = {}
        return {"status": e.code, "latency": latency, "body": parsed, "http_error": True}
    except Exception as e:
        latency = time.monotonic() - start
        return {"status": 0, "latency": latency, "body": {}, "error": str(e)[:200]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--duration", type=int, default=14400, help="durée en secondes (défaut 4h)")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--db", type=Path, default=ROOT / "data" / "stability-test.sqlite3")
    p.add_argument("--matlm-model", type=Path, default=Path(r"D:\LLM Mat\AI\models\granite-3.3-2b-instruct"))
    p.add_argument("--matlm-python", type=Path, default=Path(r"D:\LLM Mat\AI\.venv\Scripts\python.exe"))
    p.add_argument("--interval", type=float, default=2.0, help="intervalle entre requêtes (s)")
    p.add_argument("--out", type=Path, default=ROOT / "reports" / "stability-nexus-v1.jsonl")
    args = p.parse_args()

    args.db.parent.mkdir(parents=True, exist_ok=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    # 0) Pré-injecter des preuves dans MATMEM pour que le pipeline complet
    #    (MATMEM → MoE → LLM Granite) s'exécute réellement pendant le test.
    seed_memory(args.db, args.matlm_python)

    # 1) Lancer le serveur complet (3 couches) avec le venv ML + PYTHONPATH=src
    server_python = str(args.matlm_python)  # venv ML (torch/XPU)
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    cmd = [
        server_python, "-u", "-m", SERVER_MODULE,
        "--port", str(args.port),
        "--db", str(args.db),
        "--enable-matlm",
        "--matlm-model", str(args.matlm_model),
        "--matlm-python", str(args.matlm_python),
        "--matlm-timeout-seconds", "300",
        "--matlm-max-new-tokens", "256",
    ]
    print("[stability] lancement serveur:", " ".join(cmd), flush=True)
    # IMPORTANT: rediriger stdout/stderr du serveur vers un fichier plutôt
    # qu'un pipe. Si on utilise un pipe non lu, le buffer du pipe se remplit
    # (les logs de chargement du modèle + requêtes) et le serveur se bloque,
    # provoquant des timeouts sur toutes les requêtes. Un fichier évite ce
    # blocage et permet aussi un diagnostic a posteriori.
    server_log = args.out.with_suffix(".server.log")
    server_logfh = open(server_log, "w", encoding="utf-8", errors="replace")
    print(f"[stability] log serveur: {server_log}", flush=True)
    server = subprocess.Popen(
        cmd, cwd=ROOT, env=env, stdout=server_logfh, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )

    base = f"http://127.0.0.1:{args.port}"
    # 2) Attendre que le serveur soit prêt
    ready = False
    for _ in range(120):
        if server.poll() is not None:
            print("[stability] SERVEUR SORTI AVANT READY", flush=True)
            break
        r = http_json("GET", base + "/api/health", timeout=5)
        if r["status"] == 200:
            ready = True
            break
        time.sleep(1)
    if not ready:
        print("[stability] serveur non prêt, abandon", flush=True)
        server.kill()
        return 1
    print("[stability] serveur prêt", flush=True)

    # 3) Démarrer le worker MAT-LM (LLM) - body JSON vide {} (aucun paramètre accepté)
    start_resp = http_json("POST", base + "/api/matlm/start", {}, timeout=30)
    print("[stability] matlm/start:", start_resp["status"], start_resp["body"], flush=True)

    # 3b) Attendre que le modèle soit chargé (jusqu'à 900s)
    #     Le chargement de Granite 2B sur XPU peut prendre plusieurs minutes.
    model_ready = False
    for _ in range(450):
        st = http_json("GET", base + "/api/matlm/status", timeout=10)
        body = st.get("body", {})
        m = body.get("matlm", body)
        if isinstance(m, dict) and m.get("model_loaded") is True:
            model_ready = True
            break
        if st["status"] != 200:
            time.sleep(2)
            continue
        time.sleep(2)
    print("[stability] modèle chargé:", model_ready, flush=True)
    if not model_ready:
        print("[stability] AVERTISSEMENT: modèle Granite non chargé, inférences possiblement abstention", flush=True)

    # 4) Boucle de test
    out = open(args.out, "w", encoding="utf-8")
    start_time = time.monotonic()
    deadline = start_time + args.duration
    seq = 0
    stats = Counter()
    latencies = []
    errors = []

    while time.monotonic() < deadline:
        seq += 1
        q = QUESTIONS[seq % len(QUESTIONS)]
        request_id = f"stability-{seq}"
        # Requête intégrée : MATMEM + MoE + LLM
        r = http_json(
            "POST", base + "/api/matlm/ask",
            {"question": q, "request_id": request_id, "mode": "grounded", "interaction_mode": "general"},
            timeout=300,
        )
        ok = r["status"] == 200 and bool(r["body"].get("answer"))
        answer_len = 0
        abstained = None
        if r["status"] == 200 and isinstance(r["body"], dict):
            # La réponse du serveur place l'objet réponse native complet dans
            # body["answer"] et la chaîne de texte dans body["answer"]["answer"].
            answer_obj = r["body"].get("answer")
            ans = answer_obj.get("answer") if isinstance(answer_obj, dict) else None
            answer_len = len(ans) if isinstance(ans, str) else 0
            abst = answer_obj.get("abstention") if isinstance(answer_obj, dict) else None
            abstained = bool(abst and abst.get("abstained")) if isinstance(abst, dict) else None
        stats["matlm_ok" if ok else "matlm_fail"] += 1
        latencies.append(r["latency"])
        if not ok or answer_len < 20:
            errors.append({"seq": seq, "route": "matlm/ask", "status": r["status"],
                           "err": r.get("error", ""), "answer_len": answer_len,
                           "abstained": abstained})
        record = {
            "seq": seq, "t": round(time.monotonic() - start_time, 2),
            "route": "matlm/ask", "status": r["status"], "latency": round(r["latency"], 3),
            "ok": ok, "request_id": request_id, "answer_len": answer_len,
            "abstained": abstained,
        }
        out.write(json.dumps(record, ensure_ascii=False) + "\n")
        out.flush()

        # Requête mémoire+MoE (chat)
        r2 = http_json("POST", base + "/api/chat", {"message": q, "request_id": request_id + "-c"}, timeout=60)
        ok2 = r2["status"] == 200
        stats["chat_ok" if ok2 else "chat_fail"] += 1
        record2 = {
            "seq": seq, "t": round(time.monotonic() - start_time, 2),
            "route": "chat", "status": r2["status"], "latency": round(r2["latency"], 3),
            "ok": ok2, "request_id": request_id + "-c",
        }
        out.write(json.dumps(record2, ensure_ascii=False) + "\n")
        out.flush()

        # Health + stats (surveillance)
        h = http_json("GET", base + "/api/health", timeout=10)
        s = http_json("GET", base + "/api/stats", timeout=10)
        stats["health_ok" if h["status"] == 200 else "health_fail"] += 1
        stats["stats_ok" if s["status"] == 200 else "stats_fail"] += 1

        if seq % 10 == 0:
            elapsed = time.monotonic() - start_time
            n = len(latencies)
            avg = sum(latencies) / n if n else 0
            print(f"[stability] seq={seq} elapsed={elapsed:.0f}s "
                  f"matlm_ok={stats['matlm_ok']} matlm_fail={stats['matlm_fail']} "
                  f"avg_latency={avg:.2f}s", flush=True)

        time.sleep(args.interval)

    out.close()

    # 5) Rapport final
    n = len(latencies)
    lat_sorted = sorted(latencies)
    p95 = lat_sorted[int(n * 0.95)] if n else 0
    p99 = lat_sorted[int(n * 0.99)] if n else 0
    report = {
        "schema_version": "mat9f-stability-test-v1",
        "duration_seconds": args.duration,
        "elapsed_seconds": round(time.monotonic() - start_time, 2),
        "requests": seq,
        "stats": dict(stats),
        "latency": {
            "count": n,
            "mean": round(sum(latencies) / n, 3) if n else 0,
            "p50": round(lat_sorted[int(n * 0.5)], 3) if n else 0,
            "p95": round(p95, 3),
            "p99": round(p99, 3),
            "max": round(lat_sorted[-1], 3) if n else 0,
        },
        "errors": errors[:50],
        "error_count": len(errors),
    }
    report_path = args.out.with_suffix(".report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[stability] RAPPORT:", report_path, flush=True)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)

    server.terminate()
    try:
        server.wait(timeout=10)
    except Exception:
        server.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())