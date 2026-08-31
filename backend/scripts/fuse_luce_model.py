#!/usr/bin/env python3
"""Fusionne l'adaptateur LoRA Luce dans les poids du modèle de base.

Produit un dossier standalone ``luce-model/`` contenant le LLM Luce complet
(architecture Granite, poids uniques à Luce). Ce modèle fusionné n'a plus
besoin du LoRA ni du modèle de base original pour fonctionner.

Usage::

    python scripts/fuse_luce_model.py --adapter training-runs/luce-core-v2/adapter --output D:\LLM-Mat\luce-model
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def fuse_model(
    adapter_path: Path,
    base_model: str,
    output_dir: Path,
) -> dict[str, str]:
    """Fusionne l'adaptateur LoRA dans le modèle de base.

    Returns:
        Un dict avec ``output``, ``size_mb``, ``adapter``, ``base``.
    """
    if output_dir.exists():
        shutil.rmtree(output_dir)

    # Étape 1 : Copier le modèle de base
    base_path = Path(base_model).expanduser().resolve()
    if not base_path.is_dir():
        # Essayer le cache HuggingFace
        from pathlib import Path as P
        cache = P.home() / ".cache" / "huggingface" / "hub"
        candidate = None
        for d in cache.glob("models--*granite*3.3*2b*"):
            snaps = d / "snapshots"
            if snaps.is_dir():
                candidates = sorted(snaps.iterdir())
                if candidates:
                    candidate = candidates[-1]
                    break
        if candidate is None:
            raise FileNotFoundError(
                f"Modèle de base introuvable: {base_model}\n"
                f"Cherché dans: {base_path} et {cache}"
            )
        base_path = candidate

    print(f"📋 Copie du modèle de base depuis {base_path}...")
    shutil.copytree(base_path, output_dir, symlinks=False,
                    ignore=lambda d, f: [x for x in f if x.endswith('.bin')])
    print(f"   ✅ Modèle de base copié ({len(list(output_dir.glob('*')))} fichiers)")

    # Étape 2 : Fusionner le LoRA
    print(f"🔗 Fusion du LoRA depuis {adapter_path}...")

    # Charger le modèle avec PEFT puis le sauvegarder fusionné
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    # Détecter device
    xpu = getattr(torch, "xpu", None)
    device = "cpu"
    if xpu is not None and xpu.is_available():
        device = "xpu:0"
        xpu.set_device(0)
    elif torch.cuda.is_available():
        device = "cuda:0"

    print(f"   Périphérique: {device}")
    print(f"   Chargement du modèle de base...")
    base = AutoModelForCausalLM.from_pretrained(
        str(output_dir),
        torch_dtype=torch.bfloat16 if device != "cpu" else torch.float32,
        local_files_only=True,
        trust_remote_code=False,
    )

    print(f"   Chargement du LoRA...")
    model = PeftModel.from_pretrained(base, str(adapter_path))

    print(f"   Fusion...")
    merged = model.merge_and_unload()

    print(f"   Sauvegarde du modèle fusionné...")
    merged.save_pretrained(str(output_dir), safe_serialization=True,
                           max_shard_size="5GB")

    # Sauvegarder aussi le tokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        str(base_path), use_fast=True, local_files_only=True
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.save_pretrained(str(output_dir))

    # Étape 3 : Ajouter le manifeste Luce
    adapter_config = json.loads((adapter_path / "adapter_config.json").read_text())
    manifest = {
        "model_name": "Luce",
        "version": "2.0",
        "base_architecture": "granite-3.3-2b",
        "training_steps": 2000,
        "training_examples": 2700,
        "conversation_tasks": 30,
        "lora_rank": adapter_config.get("r", 8),
        "lora_alpha": adapter_config.get("lora_alpha", 16),
        "merged": True,
        "language": "fr",
        "description": "Compagne conversationnelle francophone pour aînés",
    }
    (output_dir / "luce_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Calculer la taille
    total_size = sum(f.stat().st_size for f in output_dir.rglob("*") if f.is_file())
    size_mb = total_size / (1024 * 1024)

    return {
        "output": str(output_dir),
        "size_mb": f"{size_mb:.1f}",
        "adapter": str(adapter_path),
        "base": str(base_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--adapter", type=Path, required=True,
        help="Chemin de l'adaptateur LoRA Luce.",
    )
    parser.add_argument(
        "--base-model", default="D:/MAT-LM/models/granite-3.3-2b-instruct",
        help="Chemin du modèle de base.",
    )
    parser.add_argument(
        "--output", type=Path, default="D:/MAT-LM/models/luce-model",
        help="Dossier de sortie du modèle fusionné.",
    )
    args = parser.parse_args(argv)

    if not args.adapter.is_dir():
        sys.stderr.write(f"❌ Adaptateur introuvable: {args.adapter}\n")
        return 2

    print("🌸 Fusion Luce — création du modèle standalone\n")
    try:
        result = fuse_model(args.adapter, args.base_model, args.output)
        print(f"\n✅ Modèle Luce fusionné !")
        print(f"   📂 {result['output']}")
        print(f"   📦 {result['size_mb']} Mo")
        return 0
    except Exception as error:
        sys.stderr.write(f"❌ Échec de la fusion: {error}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())