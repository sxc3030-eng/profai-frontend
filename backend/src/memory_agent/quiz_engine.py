# -*- coding: utf-8 -*-
"""Moteur de quiz et d'examens — AI Formateur MAT-9F.

Génère des quiz QCM, exercices, examens blancs avec correction expliquée.
Bilingue FR/EN, adaptatif par niveau.

Usage:
    from memory_agent.quiz_engine import QuizEngine
    qe = QuizEngine(lang="fr", grade="secondary_5")
    quiz = qe.generate_quiz(domain="formal_science.mathematics.algebra", lesson_title="Algèbre")
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .grade_adapter import GradeAdapter, GradeLevel


SCHEMA_VERSION = "ai-formateur-quiz-v1"


@dataclass
class Question:
    """Une question de quiz."""

    question_id: str
    question_type: str  # "multiple_choice" | "true_false" | "fill_blank" | "short_answer"
    question: str
    choices: list[str] | None = None  # Pour QCM
    correct_answer: str = ""
    explanation: str = ""
    difficulty: str = "medium"  # "easy" | "medium" | "hard"
    points: int = 1
    domain: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class Quiz:
    """Un quiz complet."""

    quiz_id: str
    title: str
    description: str
    lang: str
    grade: str
    domain: str
    questions: list[Question] = field(default_factory=list)
    total_points: int = 0
    passing_score: float = 0.6
    time_limit_minutes: int = 0
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "quiz_id": self.quiz_id,
            "title": self.title,
            "description": self.description,
            "lang": self.lang,
            "grade": self.grade,
            "domain": self.domain,
            "total_points": self.total_points,
            "passing_score": self.passing_score,
            "time_limit_minutes": self.time_limit_minutes,
            "generated_at": self.generated_at,
            "questions": [
                {
                    "question_id": q.question_id,
                    "question_type": q.question_type,
                    "question": q.question,
                    "choices": q.choices,
                    "correct_answer": q.correct_answer,
                    "explanation": q.explanation,
                    "difficulty": q.difficulty,
                    "points": q.points,
                    "domain": q.domain,
                    "tags": q.tags,
                }
                for q in self.questions
            ],
        }


@dataclass
class QuizResult:
    """Résultat d'un quiz passé."""

    quiz_id: str
    student_id: str
    answers: dict[str, str] = field(default_factory=dict)  # question_id -> student_answer
    score: int = 0
    total: int = 0
    percentage: float = 0.0
    passed: bool = False
    question_results: list[dict[str, Any]] = field(default_factory=list)
    completed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "quiz_id": self.quiz_id,
            "student_id": self.student_id,
            "score": self.score,
            "total": self.total,
            "percentage": round(self.percentage, 1),
            "passed": self.passed,
            "completed_at": self.completed_at,
            "question_results": self.question_results,
        }


# ── Banques de questions par domaine ────────────────────────────────────────

_ALGEBRA_QUESTIONS_FR = [
    {
        "type": "multiple_choice",
        "question": "Si 2x + 3 = 11, quelle est la valeur de x ?",
        "choices": ["x = 3", "x = 4", "x = 5", "x = 7"],
        "correct": "x = 4",
        "explanation": "2x + 3 = 11 → 2x = 8 → x = 4. On soustrait 3 des deux côtés, puis on divise par 2.",
        "difficulty": "easy",
    },
    {
        "type": "multiple_choice",
        "question": "Quelle est la forme factorisée de x² - 9 ?",
        "choices": ["(x - 9)(x + 1)", "(x - 3)(x + 3)", "(x - 3)²", "(x + 9)(x - 1)"],
        "correct": "(x - 3)(x + 3)",
        "explanation": "x² - 9 est une différence de carrés : a² - b² = (a-b)(a+b) avec a=x et b=3.",
        "difficulty": "medium",
    },
    {
        "type": "true_false",
        "question": "L'équation x² = -4 a une solution réelle.",
        "choices": ["Vrai", "Faux"],
        "correct": "Faux",
        "explanation": "Un carré ne peut jamais être négatif dans les nombres réels. x² = -4 n'a pas de solution réelle (mais a des solutions complexes : x = ±2i).",
        "difficulty": "medium",
    },
    {
        "type": "multiple_choice",
        "question": "Quel est le coefficient directeur de la droite y = 3x - 7 ?",
        "choices": ["-7", "3", "7", "1/3"],
        "correct": "3",
        "explanation": "Dans y = mx + b, m est le coefficient directeur (pente). Ici m = 3.",
        "difficulty": "easy",
    },
    {
        "type": "fill_blank",
        "question": "Complète : (a + b)² = a² + ____ + b²",
        "choices": None,
        "correct": "2ab",
        "explanation": "L'identité remarquable : (a + b)² = a² + 2ab + b².",
        "difficulty": "easy",
    },
]

_ALGEBRA_QUESTIONS_EN = [
    {
        "type": "multiple_choice",
        "question": "If 2x + 3 = 11, what is the value of x?",
        "choices": ["x = 3", "x = 4", "x = 5", "x = 7"],
        "correct": "x = 4",
        "explanation": "2x + 3 = 11 → 2x = 8 → x = 4. Subtract 3 from both sides, then divide by 2.",
        "difficulty": "easy",
    },
    {
        "type": "multiple_choice",
        "question": "What is the factored form of x² - 9?",
        "choices": ["(x - 9)(x + 1)", "(x - 3)(x + 3)", "(x - 3)²", "(x + 9)(x - 1)"],
        "correct": "(x - 3)(x + 3)",
        "explanation": "x² - 9 is a difference of squares: a² - b² = (a-b)(a+b) with a=x and b=3.",
        "difficulty": "medium",
    },
    {
        "type": "true_false",
        "question": "The equation x² = -4 has a real solution.",
        "choices": ["True", "False"],
        "correct": "False",
        "explanation": "A square can never be negative in real numbers. x² = -4 has no real solution (but has complex solutions: x = ±2i).",
        "difficulty": "medium",
    },
    {
        "type": "multiple_choice",
        "question": "What is the slope of the line y = 3x - 7?",
        "choices": ["-7", "3", "7", "1/3"],
        "correct": "3",
        "explanation": "In y = mx + b, m is the slope. Here m = 3.",
        "difficulty": "easy",
    },
    {
        "type": "fill_blank",
        "question": "Complete: (a + b)² = a² + ____ + b²",
        "choices": None,
        "correct": "2ab",
        "explanation": "The binomial expansion: (a + b)² = a² + 2ab + b².",
        "difficulty": "easy",
    },
]

_ALGORITHMS_QUESTIONS_FR = [
    {
        "type": "multiple_choice",
        "question": "Quelle est la complexité temporelle d'une recherche dichotomique (binary search) ?",
        "choices": ["O(1)", "O(n)", "O(log n)", "O(n²)"],
        "correct": "O(log n)",
        "explanation": "La recherche dichotomique divise l'espace de recherche par 2 à chaque étape, d'où une complexité logarithmique O(log n).",
        "difficulty": "medium",
    },
    {
        "type": "multiple_choice",
        "question": "Quel algorithme de tri a la meilleure complexité dans le pire des cas ?",
        "choices": ["Tri à bulles (Bubble sort)", "Tri fusion (Merge sort)", "Tri rapide (Quick sort)", "Tri par insertion"],
        "correct": "Tri fusion (Merge sort)",
        "explanation": "Merge sort garantit O(n log n) dans tous les cas. Quick sort est O(n²) dans le pire cas, bubble sort et insertion sort sont O(n²).",
        "difficulty": "hard",
    },
    {
        "type": "true_false",
        "question": "Un algorithme récursif s'appelle toujours lui-même au moins une fois.",
        "choices": ["Vrai", "Faux"],
        "correct": "Faux",
        "explanation": "Un algorithme récursif a un cas de base où il ne s'appelle pas. Sans cas de base, la récursion serait infinie.",
        "difficulty": "easy",
    },
]

_ALGORITHMS_QUESTIONS_EN = [
    {
        "type": "multiple_choice",
        "question": "What is the time complexity of binary search?",
        "choices": ["O(1)", "O(n)", "O(log n)", "O(n²)"],
        "correct": "O(log n)",
        "explanation": "Binary search divides the search space by 2 at each step, giving logarithmic complexity O(log n).",
        "difficulty": "medium",
    },
    {
        "type": "multiple_choice",
        "question": "Which sorting algorithm has the best worst-case complexity?",
        "choices": ["Bubble sort", "Merge sort", "Quick sort", "Insertion sort"],
        "correct": "Merge sort",
        "explanation": "Merge sort guarantees O(n log n) in all cases. Quick sort is O(n²) worst-case, bubble and insertion sort are O(n²).",
        "difficulty": "hard",
    },
    {
        "type": "true_false",
        "question": "A recursive algorithm always calls itself at least once.",
        "choices": ["True", "False"],
        "correct": "False",
        "explanation": "A recursive algorithm has a base case where it doesn't call itself. Without a base case, recursion would be infinite.",
        "difficulty": "easy",
    },
]

# Registre des questions par domaine
_QUESTION_BANK = {
    "fr": {
        "formal_science.mathematics.algebra": _ALGEBRA_QUESTIONS_FR,
        "formal_science.computer_science.algorithms": _ALGORITHMS_QUESTIONS_FR,
    },
    "en": {
        "formal_science.mathematics.algebra": _ALGEBRA_QUESTIONS_EN,
        "formal_science.computer_science.algorithms": _ALGORITHMS_QUESTIONS_EN,
    },
}


class QuizEngine:
    """Moteur de quiz et d'examens."""

    def __init__(self, lang: str = "fr", grade: str = "secondary_5") -> None:
        if lang not in ("fr", "en"):
            raise ValueError(f"Langue non supportée: {lang}")
        self.lang = lang
        self.grade = grade
        self.grade_adapter = GradeAdapter(lang=lang)

    # ── Génération de quiz ───────────────────────────────────────────────

    def generate_quiz(
        self,
        domain: str,
        lesson_title: str,
        question_count: int = 5,
        difficulty_mix: tuple[float, float, float] = (0.3, 0.5, 0.2),
    ) -> Quiz:
        """Génère un quiz pour une leçon.

        difficulty_mix: (easy_ratio, medium_ratio, hard_ratio)
        """
        questions = self._select_questions(domain, question_count, difficulty_mix)
        total_points = sum(q.points for q in questions)
        grade_info = self.grade_adapter.get_grade_info(self.grade)

        quiz_id = hashlib.sha256(
            f"{domain}-{lesson_title}-{self.lang}-{self.grade}".encode()
        ).hexdigest()[:12]

        title_fr = f"Quiz : {lesson_title}"
        title_en = f"Quiz: {lesson_title}"
        desc_fr = f"Évalue ta compréhension de {lesson_title}. Niveau {grade_info['label']}."
        desc_en = f"Test your understanding of {lesson_title}. {grade_info['label']} level."

        return Quiz(
            quiz_id=quiz_id,
            title=title_fr if self.lang == "fr" else title_en,
            description=desc_fr if self.lang == "fr" else desc_en,
            lang=self.lang,
            grade=self.grade,
            domain=domain,
            questions=questions,
            total_points=total_points,
            passing_score=0.6,
            time_limit_minutes=max(5, question_count * 2),
        )

    def generate_final_quiz(
        self, domain: str, course_title: str, lessons: list[Any]
    ) -> dict[str, Any]:
        """Génère un quiz final pour tout le cours."""
        question_count = min(20, len(lessons) * 3)
        quiz = self.generate_quiz(domain, course_title, question_count, (0.2, 0.5, 0.3))
        quiz.time_limit_minutes = max(15, question_count * 2)
        return quiz.to_dict()

    def generate_exam(
        self,
        domain: str,
        course_title: str,
        question_count: int = 30,
        time_limit_minutes: int = 60,
    ) -> Quiz:
        """Génère un examen blanc (format examen ministère/CEGEP)."""
        quiz = self.generate_quiz(domain, course_title, question_count, (0.15, 0.55, 0.30))
        quiz.time_limit_minutes = time_limit_minutes
        quiz.passing_score = 0.5  # Plus indulgent pour un examen

        if self.lang == "fr":
            quiz.title = f"Examen blanc : {course_title}"
            quiz.description = f"Simulation d'examen. {question_count} questions, {time_limit_minutes} minutes. Bonne chance !"
        else:
            quiz.title = f"Practice Exam: {course_title}"
            quiz.description = f"Exam simulation. {question_count} questions, {time_limit_minutes} minutes. Good luck!"

        return quiz

    # ── Correction ───────────────────────────────────────────────────────

    def grade_quiz(self, quiz: Quiz, answers: dict[str, str], student_id: str = "anonymous") -> QuizResult:
        """Corrige un quiz et retourne le résultat détaillé."""
        question_results = []
        score = 0
        total = 0

        for q in quiz.questions:
            total += q.points
            student_answer = answers.get(q.question_id, "").strip()
            is_correct = self._check_answer(q, student_answer)

            if is_correct:
                score += q.points

            question_results.append({
                "question_id": q.question_id,
                "question": q.question,
                "student_answer": student_answer,
                "correct_answer": q.correct_answer,
                "is_correct": is_correct,
                "explanation": q.explanation,
                "points_earned": q.points if is_correct else 0,
                "points_possible": q.points,
            })

        percentage = (score / total * 100) if total > 0 else 0

        return QuizResult(
            quiz_id=quiz.quiz_id,
            student_id=student_id,
            answers=answers,
            score=score,
            total=total,
            percentage=round(percentage, 1),
            passed=percentage >= quiz.passing_score * 100,
            question_results=question_results,
        )

    def get_feedback(self, result: QuizResult) -> dict[str, Any]:
        """Génère un feedback personnalisé basé sur les résultats."""
        if self.lang == "fr":
            if result.percentage >= 90:
                message = "Excellent travail ! Tu maîtrises parfaitement cette matière. 🎉"
                suggestion = "Tu es prêt·e pour le niveau suivant !"
            elif result.percentage >= 75:
                message = "Très bien ! Tu as une bonne compréhension de la matière. 👍"
                suggestion = "Révise les questions où tu as fait des erreurs pour consolider."
            elif result.percentage >= 60:
                message = "Pas mal ! Tu as les bases, mais il y a encore des points à travailler."
                suggestion = "Revois les leçons sur les concepts que tu as manqués."
            elif result.percentage >= 40:
                message = "Continue tes efforts ! Cette matière demande encore du travail. 💪"
                suggestion = "Reprends les leçons depuis le début et refais les exercices."
            else:
                message = "Ne te décourage pas ! C'est en faisant des erreurs qu'on apprend. 🌱"
                suggestion = "Recommence le cours à ton rythme, et n'hésite pas à poser des questions."
        else:
            if result.percentage >= 90:
                message = "Excellent work! You've mastered this material. 🎉"
                suggestion = "You're ready for the next level!"
            elif result.percentage >= 75:
                message = "Very good! You have a solid understanding. 👍"
                suggestion = "Review the questions you missed to consolidate."
            elif result.percentage >= 60:
                message = "Not bad! You have the basics, but there's room for improvement."
                suggestion = "Review the lessons on the concepts you missed."
            elif result.percentage >= 40:
                message = "Keep going! This material needs more work. 💪"
                suggestion = "Go through the lessons again from the start and redo the exercises."
            else:
                message = "Don't give up! We learn from our mistakes. 🌱"
                suggestion = "Restart the course at your own pace, and don't hesitate to ask questions."

        # Identifier les domaines faibles
        weak_areas = [
            r["question"] for r in result.question_results if not r["is_correct"]
        ]

        return {
            "message": message,
            "suggestion": suggestion,
            "score": f"{result.score}/{result.total}",
            "percentage": result.percentage,
            "passed": result.passed,
            "weak_areas": weak_areas,
            "strong_areas": [
                r["question"] for r in result.question_results if r["is_correct"]
            ],
        }

    # ── Interne ──────────────────────────────────────────────────────────

    def _select_questions(
        self,
        domain: str,
        count: int,
        difficulty_mix: tuple[float, float, float],
    ) -> list[Question]:
        """Sélectionne des questions selon le mix de difficulté."""
        bank = _QUESTION_BANK.get(self.lang, {}).get(domain, [])
        if not bank:
            bank = self._generate_generic_questions(domain, count)

        easy_count = max(1, int(count * difficulty_mix[0]))
        medium_count = max(1, int(count * difficulty_mix[1]))
        hard_count = count - easy_count - medium_count

        easy = [q for q in bank if q.get("difficulty") == "easy"]
        medium = [q for q in bank if q.get("difficulty") == "medium"]
        hard = [q for q in bank if q.get("difficulty") == "hard"]

        selected = []
        selected.extend(random.sample(easy, min(easy_count, len(easy))) if easy else [])
        selected.extend(random.sample(medium, min(medium_count, len(medium))) if medium else [])
        selected.extend(random.sample(hard, min(hard_count, len(hard))) if hard else [])

        # Compléter si pas assez
        remaining = [q for q in bank if q not in selected]
        while len(selected) < count and remaining:
            selected.append(remaining.pop(0))

        random.shuffle(selected)

        return [
            Question(
                question_id=hashlib.sha256(
                    f"{domain}-{i}-{q['question']}".encode()
                ).hexdigest()[:10],
                question_type=q["type"],
                question=q["question"],
                choices=q.get("choices"),
                correct_answer=q["correct"],
                explanation=q["explanation"],
                difficulty=q.get("difficulty", "medium"),
                points=1 if q.get("difficulty") == "easy" else 2 if q.get("difficulty") == "hard" else 1,
                domain=domain,
                tags=[q.get("difficulty", "medium")],
            )
            for i, q in enumerate(selected)
        ]

    def _generate_generic_questions(self, domain: str, count: int) -> list[dict[str, Any]]:
        """Génère des questions génériques si pas de banque spécifique."""
        if self.lang == "fr":
            return [
                {
                    "type": "multiple_choice",
                    "question": f"Quel est le concept le plus important dans ce domaine ?",
                    "choices": ["Option A", "Option B", "Option C", "Option D"],
                    "correct": "Option A",
                    "explanation": "Explication à venir.",
                    "difficulty": "easy",
                },
                {
                    "type": "true_false",
                    "question": "Ce domaine a des applications dans la vie quotidienne.",
                    "choices": ["Vrai", "Faux"],
                    "correct": "Vrai",
                    "explanation": "La plupart des domaines académiques ont des applications pratiques.",
                    "difficulty": "easy",
                },
            ]
        return [
            {
                "type": "multiple_choice",
                "question": "What is the most important concept in this field?",
                "choices": ["Option A", "Option B", "Option C", "Option D"],
                "correct": "Option A",
                "explanation": "Explanation to come.",
                "difficulty": "easy",
            },
            {
                "type": "true_false",
                "question": "This field has applications in everyday life.",
                "choices": ["True", "False"],
                "correct": "True",
                "explanation": "Most academic fields have practical applications.",
                "difficulty": "easy",
            },
        ]

    def _check_answer(self, question: Question, student_answer: str) -> bool:
        """Vérifie si la réponse de l'étudiant est correcte."""
        correct = question.correct_answer.strip().lower()
        answer = student_answer.strip().lower()

        if question.question_type == "fill_blank":
            # Tolérance pour les espaces et la casse
            return answer == correct
        elif question.question_type == "multiple_choice":
            # Accepter la lettre ou le texte complet
            if question.choices:
                for i, choice in enumerate(question.choices):
                    letter = chr(ord("a") + i)
                    if answer in (letter, choice.strip().lower()):
                        return choice.strip().lower() == correct.lower()
            return answer == correct
        elif question.question_type == "true_false":
            return answer in (correct, correct[0])  # "vrai" ou "v", "true" ou "t"
        else:
            # short_answer : comparaison souple
            return answer == correct or correct in answer