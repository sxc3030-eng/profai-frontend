#!/usr/bin/env python3
"""Diagnostic : capture N sorties brutes de Granite pour analyser la variabilité.

Identifie les valeurs de ``calculations`` non conformes produites par Granite
afin de valider le fix de normalisation.
Usage:
  python scripts/diag_granite_raw_n.py --n 8
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from memory_agent.matlm_inference import (
    InferenceConfig,
    MATLMInferenceSession,
    _generate_text,
    validate_generated_answer,
)
from memory_agent.native_llm_contract import build_capsule
from memory_agent.matlm_inference import MATLMInferenceError


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=10)
    args = p.parse_args()

    # Les 10 questions du test de stabilité, pour reproduire les cas réels.
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
    EVIDENCE = {
        "Quelle est la stratégie de cache pour une API ?": "La stratégie de cache pour une API repose sur la fraîcheur, l'invalidation par clé et la mise en cache des réponses idempotentes.",
        "Analyse le risque de sécurité d'une clé API exposée dans l'URL.": "Une clé API exposée dans l'URL présente un risque de sécurité élevé car elle peut être interceptée et réutilisée sans autorisation.",
        "Comment optimiser une requête SQL lente avec jointure ?": "Une requête SQL lente avec jointure s'optimise par l'indexation des colonnes de jointure et la réduction du nombre de lignes parcourues.",
        "Évalue la complétude et la fraîcheur d'un pipeline de données.": "La complétude et la fraîcheur d'un pipeline de données s'évaluent par la couverture des sources et la latence de mise à jour des agrégats.",
        "Quelle est la politique de rétention des données ?": "La politique de rétention des données définit la durée de conservation et la procédure de suppression sécurisée des informations.",
        "Comment gérer l'escalade d'un incident critique ?": "L'escalade d'un incident critique suit une procédure de priorisation, de notification et de remontée vers les responsables disponibles.",
        "Quelle est la meilleure pratique pour le versioning d'une API ?": "Le versioning d'une API suit la compatibilité sémantique et la gestion des versions majeures et mineures sans rupture.",
        "Analyse la qualité des données d'un entrepôt.": "La qualité des données d'un entrepôt s'analyse par l'exactitude, la complétude, la cohérence et l'actualité des enregistrements.",
        "Comment planifier la capacité d'un cluster Kubernetes ?": "La planification de la capacité d'un cluster Kubernetes évalue la charge, l'autoscaling et la réservation des ressources par nœud.",
        "Quelle est la stratégie de sauvegarde et de restauration ?": "La stratégie de sauvegarde et de restauration définit la fréquence des sauvegardes, la rétention et les tests de restauration.",
    }

    config = InferenceConfig(
        adapter_path=None,
        code_adapter_path=None,
        base_model=r"D:\LLM Mat\AI\models\granite-3.3-2b-instruct",
        load_mode="auto",
        device_index=0,
        max_input_tokens=4096,
        max_new_tokens=768,
        allow_model_download=False,
    )

    ok = 0
    fail = 0
    with MATLMInferenceSession(config) as session:
        for i in range(args.n):
            q = QUESTIONS[i % len(QUESTIONS)]
            capsule = build_capsule(
                question=q,
                request_id=f"diag-brute-q{i}",
                evidence=[{
                    "evidence_id": f"e{i}",
                    "text": EVIDENCE[q],
                    "status": "verified",
                    "confidence": 0.9,
                    "space": "reference",
                    "tags": ["test"],
                    "temporal_context": None,
                }],
            )
            raw = _generate_text(session._assets, capsule, config)
            print(f"\n[diag] === itération {i+1}/{args.n} | Q={q[:40]} ===")
            print("[diag] SORTIE BRUTE:", raw[:600])
            try:
                valid = validate_generated_answer(raw, capsule)
                print("[diag] VALIDATION: OK - answer_len",
                      len(valid["answer"]), "| calculations:", valid["calculations"])
                ok += 1
            except MATLMInferenceError as e:
                print("[diag] VALIDATION: ÉCHEC -", e)
                out = Path(__file__).resolve().parents[1] / "reports"
                out.mkdir(parents=True, exist_ok=True)
                fpath = out / f"raw-fail-q{i}.txt"
                fpath.write_text(repr(raw), encoding="utf-8")
                print(f"[diag] sortie brute complète → {fpath}")
                fail += 1
    print(f"\n[diag] RÉSUMÉ: {ok} OK / {fail} ÉCHEC sur {args.n}")
    return 0 if fail == 0 else 2
    config = InferenceConfig(
        adapter_path=None,
        code_adapter_path=None,
        base_model=r"D:\LLM Mat\AI\models\granite-3.3-2b-instruct",
        load_mode="auto",
        device_index=0,
        max_input_tokens=1024,
        max_new_tokens=256,
        allow_model_download=False,
    )
    ok = 0
    fail = 0
    with MATLMInferenceSession(config) as session:
        for i in range(args.n):
            raw = _generate_text(session._assets, capsule, config)
            print(f"\n[diag] === itération {i+1}/{args.n} ===")
            print("[diag] SORTIE BRUTE:", raw[:600])
            try:
                valid = validate_generated_answer(raw, capsule)
                print("[diag] VALIDATION: OK - answer_len",
                      len(valid["answer"]), "| calculations:", valid["calculations"])
                ok += 1
            except MATLMInferenceError as e:
                print("[diag] VALIDATION: ÉCHEC -", e)
                fail += 1
    print(f"\n[diag] RÉSUMÉ: {ok} OK / {fail} ÉCHEC sur {args.n}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
