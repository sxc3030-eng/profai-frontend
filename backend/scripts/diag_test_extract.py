#!/usr/bin/env python3
"""Test unitaire : extraction JSON simple ET multi-objets (fusion).

Vérifie que extract_json_object gère correctement :
1) un objet JSON unique (cas normal)
2) un objet scindé en deux fragments (fusion)
3) un objet avec préambule naturel
4) un objet avec texte parasite après (suffixe naturel)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from memory_agent.matlm_inference import extract_json_object, MATLMInferenceError
import json


def check(name: str, raw: str, expect_ok: bool) -> bool:
    try:
        out = extract_json_object(raw)
        parsed = json.loads(out)
        if not isinstance(parsed, dict):
            print(f"[{'OK' if expect_ok else 'ÉCHEC'}] {name}: objet non dict")
            return not expect_ok
        print(f"[{'OK' if expect_ok else 'ÉCHEC'}] {name}: extrait {len(parsed)} clés")
        return expect_ok
    except MATLMInferenceError as e:
        print(f"[{'OK' if not expect_ok else 'ÉCHEC'}] {name}: {e}")
        return not expect_ok


def main() -> int:
    ok = True

    # 1) Objet unique (cas normal)
    ok &= check(
        "objet unique",
        '{"a":1,"b":2}',
        True,
    )
    # 2) Préambule naturel
    ok &= check(
        "préambule naturel",
        'Voici la réponse: {"a":1,"b":2}',
        True,
    )
    # 3) Préambule OUTPUT_TEMPLATE_JSON + objet unique
    ok &= check(
        "template + objet unique",
        'OUTPUT_TEMPLATE_JSON={"a":1,"b":2}',
        True,
    )
    # 4) Deux fragments à fusionner
    ok &= check(
        "deux fragments fusionnés",
        'OUTPUT_TEMPLATE_JSON={"abstention":{"abstained":false},'
        '"answer":"Test"}\n\n'
        '{"calculations":[],"confidence":0.9,"evidence_ids":["e1"],'
        '"request_id":"r1","schema_version":"v1"}',
        True,
    )
    # 5) Suffixe texte naturel après objet unique (sans accolades)
    ok &= check(
        "suffixe texte naturel",
        '{"a":1,"b":2}\n\nEvidence ID: e1\nText: exemple\nTags: test\n',
        True,
    )
    # 6) Second objet réel après (ne doit PAS être accepté comme suffixe, mais
    #    la fusion le traite comme fragment). Ici on a 2 objets qui fusionnent.
    ok &= check(
        "deux objets fusionnés (clés disjointes)",
        '{"a":1}\n\n{"b":2}',
        True,
    )

    print("\n[test] RÉSULTAT GLOBAL:", "OK" if ok else "ÉCHEC")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
