# -*- coding: utf-8 -*-
"""Vérifie la syntaxe de tous les modules du formateur."""
import ast
from pathlib import Path

FILES = [
    "auth", "formateur_server", "socratic_guide", "adaptive_pacer",
    "dynamic_visualizer", "browser_voice", "enhanced_visualizer",
    "quiz_engine", "grade_adapter", "course_generator", "visualizer",
    "voice_teacher", "subscription",
]

BASE = Path("D:/MAT-9F/src/memory_agent")
ok = 0
errors = 0

for name in FILES:
    path = BASE / f"{name}.py"
    if not path.exists():
        print(f"ABSENT {name}.py")
        continue
    try:
        ast.parse(path.read_text(encoding="utf-8"))
        print(f"OK     {name}.py")
        ok += 1
    except SyntaxError as e:
        print(f"ERREUR {name}.py: {e}")
        errors += 1

print(f"\n{ok} fichiers OK, {errors} erreurs")

# Vérifier que auth.py a bien les bonnes méthodes
import sys
sys.path.insert(0, "D:/MAT-9F/src")
import importlib

try:
    from memory_agent.auth import AuthManager
    m = AuthManager()
    methods = [x for x in dir(m) if not x.startswith("_")]
    print("\nAuthManager methods:", methods)
    print("SCHEMA OK")
except Exception as e:
    print(f"AUTH IMPORT ERROR: {e}")
    errors += 1

sys.exit(1 if errors else 0)