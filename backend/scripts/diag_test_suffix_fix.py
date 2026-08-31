#!/usr/bin/env python3
"""Test unitaire du fix de suffixe dans extract_json_object.

Reproduit le cas de l'itération 9 (Kubernetes) où Granite ajoute du texte
après l'objet JSON, et vérifie que la validation passe maintenant.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from memory_agent.matlm_inference import extract_json_object, MATLMInferenceError, validate_generated_answer
from memory_agent.native_llm_contract import build_capsule


def main() -> int:
    # Reproduit la sortie brute réelle de l'itération 9 : l'objet réponse est
    # scindé en deux fragments JSON qui doivent être fusionnés par
    # extract_json_object (abstention+answer, puis calculations+confidence+
    # evidence_ids+request_id+schema_version).
    raw = (
        'OUTPUT_TEMPLATE_JSON={"abstention":{"abstained":false,'
        '"missing_information":[],"reason":"none"},'
        '"answer":"Planifier la capacité d\'un cluster Kubernetes implique '
        'd\'évaluer la charge, d\'autoscaling et de réserver les ressources par '
        'nœud. \\n\\nEvidence ID: e8\\nText: La planification de la capacité '
        'd\'un cluster Kubernetes évalue la charge, l\'autoscaling et la '
        'réservation des ressources par nœud.\\nConfidence: 0.9\\nSpace: '
        'reference\\nStatus: verified\\nTags: test\\nTemporal Context: null\\n"}\n\n'
        '{"calculations":[], "confidence":0.9, "evidence_ids":["e8"], '
        '"request_id":"diag-brute-q8", '
        '"schema_version":"memory-native-answer-v1"}'
    )
    capsule = build_capsule(
        question="Comment planifier la capacité d'un cluster Kubernetes ?",
        request_id="diag-brute-q8",
        evidence=[{
            "evidence_id": "e8",
            "text": "La planification de la capacité d'un cluster Kubernetes "
                    "évalue la charge, l'autoscaling et la réservation des "
                    "ressources par nœud.",
            "status": "verified",
            "confidence": 0.9,
            "space": "reference",
            "tags": ["test"],
            "temporal_context": None,
        }],
    )
    print("[test] extraction de l'objet JSON...")
    try:
        extracted = extract_json_object(raw)
        print("[test] JSON extrait:", extracted[:200])
    except MATLMInferenceError as e:
        print("[test] ÉCHEC extraction:", e)
        return 1
    print("[test] validation complète...")
    try:
        valid = validate_generated_answer(raw, capsule)
        print("[test] OK - answer_len", len(valid["answer"]),
              "| calculations:", valid["calculations"])
        return 0
    except MATLMInferenceError as e:
        print("[test] ÉCHEC validation:", e)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
