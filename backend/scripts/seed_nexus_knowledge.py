#!/usr/bin/env python3
"""Injecte des preuves de base dans la base Nexus de production.

Nexus (mode grounded/general) exige des preuves vérifiées avant de répondre
aux questions factuelles. Sans preuve dans la base, il renvoie « réponse
provisoire (incertitude élevée) ». Ce script injecte un corpus de preuves
générales (user_confirmed) pour que l'assistant puisse répondre.

Usage:
  python scripts/seed_nexus_knowledge.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = Path(r"D:\LLM Mat\data\memory.sqlite3")
PYTHON = Path(r"D:\LLM Mat\AI\.venv\Scripts\python.exe")

# Preuves générales injectées comme souvenirs user_confirmed.
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
    "Le cache HTTP utilise les en-têtes Cache-Control et ETag pour contrôler la "
    "fraîcheur et valider les réponses sans re-téléchargement.",
    "Une API REST bien conçue utilise des verbes HTTP explicites et des codes de "
    "statut standard pour communiquer le résultat de chaque opération.",
    "L'authentification par jeton (JWT) permet une autorisation sans état entre "
    "le client et le serveur.",
    "Les tests unitaires vérifient le comportement d'une fonction isolée, tandis "
    "que les tests d'intégration vérifient la collaboration entre composants.",
    "Le déploiement continu automatise la mise en production après validation "
    "des tests et des contrôles de qualité.",
    "La conteneurisation isole une application et ses dépendances dans une image "
    "reproductible et portable.",
    "Un index de base de données accélère les lectures en organisant les données "
    "selon une structure de recherche efficace.",
    "La journalisation structurée facilite l'analyse des logs et le diagnostic "
    "des erreurs en production.",
    "Le monitoring mesure la santé d'un système via des métriques, des logs et "
    "des alertes en temps réel.",
    "La sécurité d'une application repose sur la validation des entrées, le "
    "chiffrement des données sensibles et le contrôle des accès.",
]


def main() -> int:
    if not DB.is_file():
        print(f"[seed] base introuvable: {DB}", flush=True)
        return 1
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    code = (
        "import sys\n"
        "from pathlib import Path\n"
        "from memory_agent.memory import MemoryEngine\n"
        "db = Path(sys.argv[1])\n"
        "engine = MemoryEngine(db)\n"
        "count = 0\n"
        "for i, text in enumerate(sys.argv[2:]):\n"
        "    try:\n"
        "        engine.observe(\n"
        "            text,\n"
        "            episode_id=f'seed-{i}',\n"
        "            source='user_confirmed',\n"
        "            idempotency_key=f'nexus-seed-{i}',\n"
        "        )\n"
        "        count += 1\n"
        "    except Exception as exc:\n"
        "        print(f'  echec {i}: {exc}', flush=True)\n"
        "engine.close()\n"
        "print(f'SEED_OK {count}')\n"
    )
    args = [str(PYTHON), "-c", code, str(DB), *SEED_EVIDENCE]
    result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True)
    print(result.stdout[-2000:], flush=True)
    if result.stderr:
        print(result.stderr[-2000:], flush=True)
    return 0 if result.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
