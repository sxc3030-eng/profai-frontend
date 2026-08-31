#!/usr/bin/env python3
"""Lance l'entraînement LoRA de Luce sur le curriculum conversationnel.

Ce script est un wrapper mince autour de ``train_matlm.py``. Il prépare les
chemins, génère le curriculum si nécessaire, puis délègue l'entraînement.

Usage::

    # Étape 1 — générer le curriculum
    python scripts/build_luce_core_curriculum.py --output training-data/luce-core-train.jsonl

    # Étape 2 — entraîner
    python scripts/train_luce_core.py --train-jsonl training-data/luce-core-train.jsonl --output-dir training-runs/luce-core-v1

    # Ou tout d'un coup (génère + entraîne)
    python scripts/train_luce_core.py --auto-build --output-dir training-runs/luce-core-v1
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
TRAINING_DATA_DIR = PROJECT_ROOT / "training-data"
DEFAULT_TRAIN_JSONL = TRAINING_DATA_DIR / "luce-core-train.jsonl"
DEFAULT_EVAL_JSONL = TRAINING_DATA_DIR / "luce-core-eval.jsonl"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "training-runs" / "luce-core-v1"
DEFAULT_BASE_MODEL = str(PROJECT_ROOT.parent / "MAT-LM" / "models" / "granite-3.3-2b-instruct")
DEFAULT_CACHE_DIR = str(PROJECT_ROOT.parent / "MAT-LM" / "hf-cache")


def _run(cmd: list[str], description: str) -> int:
    sys.stdout.write(f"\n=== {description} ===\n")
    sys.stdout.write(f"  {' '.join(cmd)}\n\n")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--train-jsonl", type=Path, default=DEFAULT_TRAIN_JSONL,
        help=f"JSONL d'entraînement (défaut: {DEFAULT_TRAIN_JSONL}).",
    )
    parser.add_argument(
        "--eval-jsonl", type=Path, default=DEFAULT_EVAL_JSONL,
        help=f"JSONL d'évaluation (défaut: {DEFAULT_EVAL_JSONL}).",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
        help=f"Répertoire de sortie (défaut: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--auto-build", action="store_true",
        help="Génère automatiquement le curriculum avant l'entraînement.",
    )
    parser.add_argument(
        "--base-model", default=DEFAULT_BASE_MODEL,
        help="Chemin ou identifiant HuggingFace du modèle de base.",
    )
    parser.add_argument(
        "--cache-dir", default=DEFAULT_CACHE_DIR,
        help="Cache HuggingFace local.",
    )
    parser.add_argument(
        "--mode", choices=("qlora-nf4", "bf16-lora"), default="bf16-lora",
        help="Mode d'entraînement (défaut: bf16-lora pour Intel Arc).",
    )
    parser.add_argument(
        "--fallback", choices=("bf16-attention", "none"), default="bf16-attention",
    )
    parser.add_argument(
        "--max-steps", type=int, default=600,
        help="Nombre maximum de pas d'entraînement (défaut: 600).",
    )
    parser.add_argument(
        "--sequence-length", type=int, default=1024,
        help="Longueur maximale des séquences (défaut: 1024).",
    )
    parser.add_argument(
        "--learning-rate", type=float, default=1e-4,
        help="Taux d'apprentissage (défaut: 1e-4).",
    )
    parser.add_argument(
        "--lora-rank", type=int, default=8,
    )
    parser.add_argument(
        "--lora-alpha", type=int, default=16,
    )
    parser.add_argument(
        "--seed", type=int, default=20260818,
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Valide le curriculum sans lancer l'entraînement.",
    )
    parser.add_argument(
        "--conversation-count", type=int, default=1200,
        help="Nombre d'exemples conversationnels pour --auto-build.",
    )
    parser.add_argument(
        "--factual-count", type=int, default=300,
        help="Nombre d'exemples factuels pour --auto-build.",
    )
    args = parser.parse_args(argv)

    # --- Étape 1 : générer le curriculum si demandé ---
    if args.auto_build:
        build_cmd = [
            sys.executable,
            str(SCRIPTS_DIR / "build_luce_core_curriculum.py"),
            "--output", str(args.train_jsonl),
            "--seed", str(args.seed),
            "--conversation-count", str(args.conversation_count),
            "--factual-count", str(args.factual_count),
        ]
        rc = _run(build_cmd, "Génération du curriculum Luce")
        if rc != 0:
            sys.stderr.write("Échec de la génération du curriculum.\n")
            return rc

    # --- Vérifier que le JSONL existe ---
    if not args.train_jsonl.exists():
        sys.stderr.write(
            f"Fichier d'entraînement introuvable: {args.train_jsonl}\n"
            f"Lancez d'abord: python scripts/build_luce_core_curriculum.py --output {args.train_jsonl}\n"
            f"Ou utilisez --auto-build.\n"
        )
        return 2

    # --- Étape 2 : entraînement ---
    train_cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "train_matlm.py"),
        "--train-jsonl", str(args.train_jsonl),
        "--output-dir", str(args.output_dir),
        "--base-model", args.base_model,
        "--cache-dir", args.cache_dir,
        "--mode", args.mode,
        "--fallback", args.fallback,
        "--max-steps", str(args.max_steps),
        "--sequence-length", str(args.sequence_length),
        "--learning-rate", str(args.learning_rate),
        "--lora-rank", str(args.lora_rank),
        "--lora-alpha", str(args.lora_alpha),
        "--seed", str(args.seed),
        "--gradient-accumulation-steps", "1",
        "--save-steps", "100",
        "--logging-steps", "10",
    ]

    if args.eval_jsonl.exists():
        train_cmd.extend(["--eval-jsonl", str(args.eval_jsonl)])

    if args.dry_run:
        train_cmd.append("--dry-run")

    rc = _run(train_cmd, "Entraînement LoRA Luce")
    if rc != 0:
        sys.stderr.write("Échec de l'entraînement.\n")
        return rc

    sys.stdout.write(f"\nEntraînement terminé. Adaptateur dans: {args.output_dir / 'adapter'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())