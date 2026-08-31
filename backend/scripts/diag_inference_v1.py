#!/usr/bin/env python3
"""Test d'une vraie inférence Granite via /api/matlm/ask.

Vérifie que le pipeline MATMEM + MoE + LLM produit une réponse valide.
Usage:
  python scripts/diag_inference_v1.py --port 8765
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
import urllib.error


def http_json(method: str, url: str, payload: dict | None = None, timeout: float = 400.0):
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
            return {"status": resp.status, "latency": latency, "body": json.loads(body)}
    except urllib.error.HTTPError as e:
        latency = time.monotonic() - start
        try:
            parsed = json.loads(e.read())
        except Exception:
            parsed = {}
        return {"status": e.code, "latency": latency, "body": parsed}
    except Exception as e:
        latency = time.monotonic() - start
        return {"status": 0, "latency": latency, "body": {}, "error": str(e)[:300]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args()
    base = f"http://127.0.0.1:{args.port}"

    print("[diag] vérifie la santé...")
    h = http_json("GET", base + "/api/health", timeout=10)
    print("[diag] health:", h["status"], h["latency"], "s")

    print("[diag] démarre le worker MAT-LM...")
    s = http_json("POST", base + "/api/matlm/start", {}, timeout=30)
    print("[diag] matlm/start:", s["status"], json.dumps(s["body"], ensure_ascii=False)[:200])

    print("[diag] attend le chargement du modèle (max 900s)...")
    loaded = False
    for i in range(450):
        st = http_json("GET", base + "/api/matlm/status", timeout=10)
        m = st.get("body", {}).get("matlm", st.get("body", {}))
        if isinstance(m, dict) and m.get("model_loaded") is True:
            loaded = True
            print(f"[diag] modèle chargé après ~{i*2}s")
            break
        if i % 15 == 0:
            print(f"[diag] ... chargement (it={i}, state={m.get('state') if isinstance(m,dict) else '?'})")
        time.sleep(2)
    if not loaded:
        print("[diag] ÉCHEC: modèle non chargé après 900s")
        return 1

    question = "Quelle est la strategie de cache pour une API ?"
    payload = {
        "question": question,
        "request_id": "diag-real-1",
        "mode": "grounded",
        "interaction_mode": "general",
    }
    print("[diag] envoie une requête réelle...")
    r = http_json("POST", base + "/api/matlm/ask", payload, timeout=400)
    body = r.get("body", {})
    # La réponse du serveur place l'objet réponse native complet dans
    # body["answer"], et la chaîne de réponse dans body["answer"]["answer"].
    answer_obj = body.get("answer") if isinstance(body, dict) else None
    answer = answer_obj.get("answer") if isinstance(answer_obj, dict) else None
    abst = answer_obj.get("abstention") if isinstance(answer_obj, dict) else None
    answer_len = len(answer) if isinstance(answer, str) else 0
    abstained = bool(abst and abst.get("abstained")) if isinstance(abst, dict) else None
    print("[diag] statut:", r["status"], "| latence:", round(r["latency"], 2), "s")
    print("[diag] answer_len:", answer_len, "| abstained:", abstained)
    print("[diag] réponse:", json.dumps(body, ensure_ascii=False)[:800])
    ok = r["status"] == 200 and answer_len >= 20 and not abstained
    print("[diag] RÉSULTAT:", "OK" if ok else "ÉCHEC")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
