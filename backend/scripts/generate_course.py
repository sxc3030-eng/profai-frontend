# -*- coding: utf-8 -*-
"""Script CLI pour générer des cours — AI Formateur MAT-9F.

Usage:
    cd D:\MAT-9F
    $env:PYTHONPATH="src"
    python scripts/generate_course.py --domain formal_science.mathematics.algebra --lang fr --grade secondary_5
    python scripts/generate_course.py --list-domains
    python scripts/generate_course.py --list-domains --lang en
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from memory_agent.course_generator import CourseGenerator
from memory_agent.quiz_engine import QuizEngine
from memory_agent.grade_adapter import GradeAdapter


def cmd_list_domains(args: argparse.Namespace) -> int:
    """Liste tous les domaines disponibles."""
    gen = CourseGenerator(lang=args.lang)
    if args.by_family:
        families = gen.list_domains_by_family()
        for family, domains in families.items():
            print(f"\n{'='*60}")
            print(f"  {family.upper()}")
            print(f"{'='*60}")
            for d in domains:
                print(f"  {d['domain']}")
                print(f"    → {d['title']}")
                if d.get('description'):
                    print(f"    {d['description']}")
    else:
        domains = gen.list_domains()
        print(f"\n{len(domains)} domaines disponibles ({args.lang}):\n")
        for d in domains:
            print(f"  {d['domain']:<60} {d['title']}")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    """Génère un cours complet."""
    print(f"\n🎓 Génération du cours...")
    print(f"   Domaine : {args.domain}")
    print(f"   Langue  : {args.lang}")
    print(f"   Niveau  : {args.grade}")
    print(f"   Leçons  : {args.lessons}")

    gen = CourseGenerator(
        lang=args.lang,
        grade=args.grade,
        include_visuals=not args.no_visuals,
        include_audio=args.audio,
    )

    course = gen.generate(args.domain, args.lessons)
    filepath = course.save()

    print(f"\n✅ Cours généré : {course.title}")
    print(f"   ID       : {course.course_id}")
    print(f"   Leçons   : {course.total_lessons}")
    print(f"   Durée    : {course.total_duration_minutes} min")
    print(f"   Fichier  : {filepath}")

    if args.verbose:
        print(f"\n{'='*60}")
        for i, lesson in enumerate(course.lessons):
            print(f"\n📖 Leçon {i+1}: {lesson.title}")
            print(f"   Objectif : {lesson.objective}")
            print(f"   Durée    : {lesson.duration_minutes} min")
            print(f"   Sections : {len(lesson.sections)}")
            print(f"   Visuels  : {len(lesson.visuals)}")
            for v in lesson.visuals:
                print(f"     - {v['type']}: {v.get('caption', '')}")

    if args.quiz:
        qe = QuizEngine(lang=args.lang, grade=args.grade)
        quiz = qe.generate_quiz(args.domain, course.title, 10)
        print(f"\n📝 Quiz final : {len(quiz.questions)} questions, {quiz.total_points} points")

    return 0


def cmd_grades(args: argparse.Namespace) -> int:
    """Affiche les niveaux disponibles."""
    ga = GradeAdapter(lang=args.lang)
    grades = ga.list_grades()
    print(f"\nNiveaux disponibles ({args.lang}):\n")
    for g in grades:
        print(f"  {g['key']:<20} {g['label']:<25} {g['age_range']:<15} {g['exam_style']}")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Affiche les infos d'un domaine."""
    gen = CourseGenerator(lang=args.lang)
    domains = gen.list_domains()
    found = [d for d in domains if d['domain'] == args.domain]
    if not found:
        print(f"Domaine inconnu : {args.domain}")
        return 1
    d = found[0]
    print(f"\n📚 {d['title']}")
    print(f"   Domaine  : {d['domain']}")
    print(f"   Famille  : {d['family']}")
    print(f"   Roue     : {d['wheel']}")
    print(f"   Description : {d.get('description', 'N/A')}")

    ga = GradeAdapter(lang=args.lang)
    for grade_key in ["secondary_3", "secondary_4", "secondary_5", "cegep", "university"]:
        info = ga.get_grade_info(grade_key)
        prompt = ga.get_system_prompt(grade_key)
        print(f"\n   ── {info['label']} ({info['age_range']}) ──")
        print(f"   {prompt[:120]}...")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="🎓 AI Formateur — Générateur de cours",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--lang", default="fr", choices=["fr", "en"], help="Langue (défaut: fr)")

    sub = parser.add_subparsers(dest="command", help="Commandes")

    # list-domains
    p_list = sub.add_parser("list-domains", help="Lister les domaines")
    p_list.add_argument("--by-family", action="store_true", help="Regrouper par famille")

    # generate
    p_gen = sub.add_parser("generate", help="Générer un cours")
    p_gen.add_argument("--domain", required=True, help="Domaine (ex: formal_science.mathematics.algebra)")
    p_gen.add_argument("--grade", default="secondary_5", help="Niveau (défaut: secondary_5)")
    p_gen.add_argument("--lessons", type=int, default=5, help="Nombre de leçons (défaut: 5)")
    p_gen.add_argument("--no-visuals", action="store_true", help="Désactiver les visuels")
    p_gen.add_argument("--audio", action="store_true", help="Mode audio/podcast")
    p_gen.add_argument("--quiz", action="store_true", help="Générer aussi le quiz final")
    p_gen.add_argument("--verbose", "-v", action="store_true", help="Affichage détaillé")

    # grades
    sub.add_parser("grades", help="Afficher les niveaux")

    # info
    p_info = sub.add_parser("info", help="Infos sur un domaine")
    p_info.add_argument("--domain", required=True, help="Domaine")

    args = parser.parse_args()

    if args.command == "list-domains":
        return cmd_list_domains(args)
    elif args.command == "generate":
        return cmd_generate(args)
    elif args.command == "grades":
        return cmd_grades(args)
    elif args.command == "info":
        return cmd_info(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())