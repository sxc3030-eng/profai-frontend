# -*- coding: utf-8 -*-
"""Adaptateur de niveau scolaire — AI Formateur MAT-9F.

Adapte le contenu pédagogique au niveau de l'élève :
Secondaire 3 → Université. Bilingue FR/EN.

Usage:
    from memory_agent.grade_adapter import GradeAdapter
    ga = GradeAdapter(lang="fr")
    adapted = ga.adapt("Le texte original", grade="secondary_3")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GradeLevel:
    """Définition d'un niveau scolaire."""

    key: str
    label_fr: str
    label_en: str
    age_range: str
    complexity: int  # 1 (simple) à 5 (expert)
    max_sentence_length: int
    max_paragraph_length: int
    vocabulary_level: str  # "basic" | "intermediate" | "advanced" | "expert"
    allows_abstract: bool
    allows_jargon: bool
    allows_math_symbols: bool
    exam_style: str  # "none" | "ministere" | "epreuve_uniforme" | "universitaire"


# ── Définition des niveaux ──────────────────────────────────────────────────

GRADE_LEVELS: dict[str, GradeLevel] = {
    "secondary_3": GradeLevel(
        key="secondary_3",
        label_fr="Secondaire 3",
        label_en="Grade 9",
        age_range="14-15 ans",
        complexity=1,
        max_sentence_length=80,
        max_paragraph_length=300,
        vocabulary_level="basic",
        allows_abstract=False,
        allows_jargon=False,
        allows_math_symbols=True,
        exam_style="none",
    ),
    "secondary_4": GradeLevel(
        key="secondary_4",
        label_fr="Secondaire 4",
        label_en="Grade 10",
        age_range="15-16 ans",
        complexity=2,
        max_sentence_length=100,
        max_paragraph_length=400,
        vocabulary_level="basic",
        allows_abstract=True,
        allows_jargon=False,
        allows_math_symbols=True,
        exam_style="ministere",
    ),
    "secondary_5": GradeLevel(
        key="secondary_5",
        label_fr="Secondaire 5",
        label_en="Grade 11",
        age_range="16-17 ans",
        complexity=3,
        max_sentence_length=120,
        max_paragraph_length=500,
        vocabulary_level="intermediate",
        allows_abstract=True,
        allows_jargon=True,
        allows_math_symbols=True,
        exam_style="ministere",
    ),
    "cegep": GradeLevel(
        key="cegep",
        label_fr="Cégep",
        label_en="College / CEGEP",
        age_range="17-20 ans",
        complexity=4,
        max_sentence_length=150,
        max_paragraph_length=600,
        vocabulary_level="advanced",
        allows_abstract=True,
        allows_jargon=True,
        allows_math_symbols=True,
        exam_style="epreuve_uniforme",
    ),
    "university": GradeLevel(
        key="university",
        label_fr="Université",
        label_en="University",
        age_range="20+ ans",
        complexity=5,
        max_sentence_length=200,
        max_paragraph_length=800,
        vocabulary_level="expert",
        allows_abstract=True,
        allows_jargon=True,
        allows_math_symbols=True,
        exam_style="universitaire",
    ),
}

# Ordre de progression
GRADE_ORDER = ["secondary_3", "secondary_4", "secondary_5", "cegep", "university"]


# ── Règles d'adaptation par niveau ──────────────────────────────────────────

_ADAPTATION_RULES = {
    "fr": {
        "secondary_3": {
            "tone": "Explique comme si tu parlais à un·e élève de 14 ans. Utilise des mots simples, des comparaisons concrètes, et évite le jargon.",
            "max_words_per_sentence": 20,
            "forbidden_words": ["néanmoins", "subséquemment", "ipso facto", "a fortiori", "mutatis mutandis"],
            "preferred_words": {"cependant": "mais", "toutefois": "mais", "également": "aussi", "effectuer": "faire"},
        },
        "secondary_4": {
            "tone": "Explique pour un·e élève de secondaire 4. Tu peux introduire du vocabulaire technique mais en le définissant.",
            "max_words_per_sentence": 25,
            "forbidden_words": ["ipso facto", "a fortiori", "mutatis mutandis"],
            "preferred_words": {"effectuer": "faire"},
        },
        "secondary_5": {
            "tone": "Explique pour un·e élève de secondaire 5 qui se prépare pour le cégep. Vocabulaire précis, raisonnements structurés.",
            "max_words_per_sentence": 30,
            "forbidden_words": [],
            "preferred_words": {},
        },
        "cegep": {
            "tone": "Niveau collégial. Méthodologie rigoureuse, pensée critique, préparation aux épreuves uniformes.",
            "max_words_per_sentence": 35,
            "forbidden_words": [],
            "preferred_words": {},
        },
        "university": {
            "tone": "Niveau universitaire. Analyse approfondie, sources, débats académiques, rigueur scientifique.",
            "max_words_per_sentence": 40,
            "forbidden_words": [],
            "preferred_words": {},
        },
    },
    "en": {
        "secondary_3": {
            "tone": "Explain like you're talking to a 14-year-old. Use simple words, concrete comparisons, and avoid jargon.",
            "max_words_per_sentence": 20,
            "forbidden_words": ["nevertheless", "consequently", "ipso facto", "a fortiori", "mutatis mutandis"],
            "preferred_words": {"however": "but", "therefore": "so", "additionally": "also", "utilize": "use"},
        },
        "secondary_4": {
            "tone": "Explain for a 10th grader. You can introduce technical vocabulary but define it.",
            "max_words_per_sentence": 25,
            "forbidden_words": ["ipso facto", "a fortiori", "mutatis mutandis"],
            "preferred_words": {"utilize": "use"},
        },
        "secondary_5": {
            "tone": "Explain for an 11th grader preparing for college. Precise vocabulary, structured reasoning.",
            "max_words_per_sentence": 30,
            "forbidden_words": [],
            "preferred_words": {},
        },
        "cegep": {
            "tone": "College level. Rigorous methodology, critical thinking, preparation for standardized tests.",
            "max_words_per_sentence": 35,
            "forbidden_words": [],
            "preferred_words": {},
        },
        "university": {
            "tone": "University level. In-depth analysis, sources, academic debates, scientific rigor.",
            "max_words_per_sentence": 40,
            "forbidden_words": [],
            "preferred_words": {},
        },
    },
}


class GradeAdapter:
    """Adapte le contenu au niveau scolaire."""

    def __init__(self, lang: str = "fr") -> None:
        if lang not in ("fr", "en"):
            raise ValueError(f"Langue non supportée: {lang}")
        self.lang = lang

    # ── API publique ─────────────────────────────────────────────────────

    def get_grade_info(self, grade: str) -> dict[str, Any]:
        """Retourne les informations d'un niveau."""
        level = GRADE_LEVELS.get(grade)
        if level is None:
            raise ValueError(f"Niveau inconnu: {grade}. Options: {list(GRADE_LEVELS)}")
        return {
            "key": level.key,
            "label": level.label_fr if self.lang == "fr" else level.label_en,
            "age_range": level.age_range,
            "complexity": level.complexity,
            "exam_style": level.exam_style,
        }

    def list_grades(self) -> list[dict[str, Any]]:
        """Liste tous les niveaux disponibles."""
        return [self.get_grade_info(g) for g in GRADE_ORDER]

    def get_adaptation_rules(self, grade: str) -> dict[str, Any]:
        """Retourne les règles d'adaptation pour un niveau."""
        rules = _ADAPTATION_RULES.get(self.lang, {}).get(grade)
        if rules is None:
            raise ValueError(f"Niveau inconnu: {grade}")
        return dict(rules)

    def get_system_prompt(self, grade: str) -> str:
        """Génère un prompt système pour le niveau donné."""
        level = GRADE_LEVELS.get(grade)
        if level is None:
            raise ValueError(f"Niveau inconnu: {grade}")

        rules = _ADAPTATION_RULES[self.lang][grade]

        if self.lang == "fr":
            return (
                f"Tu es un professeur bienveillant qui enseigne à des élèves de {level.label_fr} "
                f"({level.age_range}).\n\n"
                f"Règles :\n"
                f"- {rules['tone']}\n"
                f"- Phrases de maximum {rules['max_words_per_sentence']} mots\n"
                f"- Paragraphes de maximum {level.max_paragraph_length} caractères\n"
                f"- {'Peux utiliser des concepts abstraits' if level.allows_abstract else 'Utilise uniquement des exemples concrets'}\n"
                f"- {'Peux utiliser du vocabulaire technique' if level.allows_jargon else 'Définis tout nouveau terme'}\n"
                f"- Encourage l'élève, sois patient, valorise les efforts"
            )
        return (
            f"You are a supportive teacher for {level.label_en} students "
            f"({level.age_range}).\n\n"
            f"Rules:\n"
            f"- {rules['tone']}\n"
            f"- Maximum {rules['max_words_per_sentence']} words per sentence\n"
            f"- Maximum {level.max_paragraph_length} characters per paragraph\n"
            f"- {'Can use abstract concepts' if level.allows_abstract else 'Use only concrete examples'}\n"
            f"- {'Can use technical vocabulary' if level.allows_jargon else 'Define every new term'}\n"
            f"- Encourage the student, be patient, celebrate effort"
        )

    def adapt_text(self, text: str, grade: str) -> str:
        """Adapte un texte au niveau scolaire (version simple, règles déterministes)."""
        rules = _ADAPTATION_RULES[self.lang].get(grade)
        if rules is None:
            return text

        # Remplacer les mots interdits
        for forbidden in rules["forbidden_words"]:
            if forbidden.lower() in text.lower():
                # On laisse le texte tel quel — l'adaptation fine est faite par le LLM
                pass

        # Tronquer les phrases trop longues (heuristique simple)
        sentences = text.replace("!", ".").replace("?", ".").split(".")
        max_words = rules["max_words_per_sentence"]
        adapted = []
        for sentence in sentences:
            words = sentence.split()
            if len(words) > max_words:
                # Couper en deux
                mid = len(words) // 2
                adapted.append(" ".join(words[:mid]) + ".")
                adapted.append(" ".join(words[mid:]) + ".")
            else:
                if sentence.strip():
                    adapted.append(sentence.strip() + ".")
        return " ".join(adapted)

    def get_exam_format(self, grade: str) -> dict[str, Any]:
        """Retourne le format d'examen approprié pour le niveau."""
        level = GRADE_LEVELS.get(grade)
        if level is None:
            raise ValueError(f"Niveau inconnu: {grade}")

        formats = {
            "none": {
                "fr": {"name": "Quiz simple", "duration": 15, "question_count": 10},
                "en": {"name": "Simple Quiz", "duration": 15, "question_count": 10},
            },
            "ministere": {
                "fr": {"name": "Examen du ministère", "duration": 60, "question_count": 25},
                "en": {"name": "Ministry Exam", "duration": 60, "question_count": 25},
            },
            "epreuve_uniforme": {
                "fr": {"name": "Épreuve uniforme", "duration": 90, "question_count": 35},
                "en": {"name": "Standardized Test", "duration": 90, "question_count": 35},
            },
            "universitaire": {
                "fr": {"name": "Examen universitaire", "duration": 120, "question_count": 50},
                "en": {"name": "University Exam", "duration": 120, "question_count": 50},
            },
        }

        return formats[level.exam_style][self.lang]

    def get_next_grade(self, grade: str) -> str | None:
        """Retourne le niveau suivant, ou None si c'est le dernier."""
        try:
            idx = GRADE_ORDER.index(grade)
            return GRADE_ORDER[idx + 1] if idx + 1 < len(GRADE_ORDER) else None
        except ValueError:
            return None

    def get_previous_grade(self, grade: str) -> str | None:
        """Retourne le niveau précédent, ou None si c'est le premier."""
        try:
            idx = GRADE_ORDER.index(grade)
            return GRADE_ORDER[idx - 1] if idx > 0 else None
        except ValueError:
            return None