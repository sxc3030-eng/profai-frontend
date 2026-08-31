# -*- coding: utf-8 -*-
"""Adaptateur de rythme — AI Formateur MAT-9F.

Adapte la vitesse d'apprentissage à chaque élève. Détecte si l'élève
est en difficulté ou s'ennuie, et ajuste le rythme en conséquence.

Ne pousse jamais l'élève. Ne le retient jamais. S'adapte.

Usage:
    from memory_agent.adaptive_pacer import AdaptivePacer
    ap = AdaptivePacer()
    pace = ap.assess(student_id="alice", time_taken_seconds=45, is_correct=True)
    # → {"speed": "optimal", "adjustment": "maintain", "next_difficulty": "medium"}
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PACER_DIR = Path(__file__).resolve().parents[2] / "pacer_data"


@dataclass
class StudentProfile:
    """Profil d'apprentissage d'un élève."""

    student_id: str
    # Métriques de vitesse
    avg_response_time_seconds: float = 60.0
    response_time_history: list[float] = field(default_factory=list)
    # Métriques de réussite
    accuracy: float = 0.0
    accuracy_history: list[float] = field(default_factory=list)
    # Métriques d'engagement
    hints_requested: int = 0
    questions_asked: int = 0
    sessions_completed: int = 0
    # Niveau actuel
    current_difficulty: str = "medium"  # easy, medium, hard
    current_pace: str = "normal"  # slow, normal, fast
    # Historique
    last_active: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AdaptivePacer:
    """Adapte le rythme d'apprentissage à l'élève."""

    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = storage_dir or PACER_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._profiles: dict[str, StudentProfile] = {}

    # ── API publique ─────────────────────────────────────────────────────

    def assess(
        self,
        student_id: str,
        time_taken_seconds: float,
        is_correct: bool,
        hints_used: int = 0,
        question_difficulty: str = "medium",
    ) -> dict[str, Any]:
        """Évalue la performance sur une question et ajuste le rythme.

        Returns:
            {"speed": str, "adjustment": str, "next_difficulty": str, "message": str}
        """
        profile = self._get_profile(student_id)

        # Mettre à jour l'historique
        profile.response_time_history.append(time_taken_seconds)
        if len(profile.response_time_history) > 50:
            profile.response_time_history = profile.response_time_history[-50:]

        profile.accuracy_history.append(1.0 if is_correct else 0.0)
        if len(profile.accuracy_history) > 50:
            profile.accuracy_history = profile.accuracy_history[-50:]

        profile.hints_requested += hints_used
        profile.last_active = datetime.now(timezone.utc).isoformat()

        # Recalculer les moyennes
        profile.avg_response_time_seconds = (
            sum(profile.response_time_history) / len(profile.response_time_history)
        )
        profile.accuracy = (
            sum(profile.accuracy_history) / len(profile.accuracy_history)
            if profile.accuracy_history else 0.0
        )

        # ── Analyse du rythme ──────────────────────────────────────────
        speed, adjustment, message = self._analyze_pace(profile, time_taken_seconds, is_correct)

        # ── Ajustement de la difficulté ─────────────────────────────────
        next_difficulty = self._adjust_difficulty(profile, is_correct, time_taken_seconds)

        profile.current_difficulty = next_difficulty
        profile.current_pace = speed

        self._save_profile(profile)

        return {
            "speed": speed,
            "adjustment": adjustment,
            "next_difficulty": next_difficulty,
            "message": message,
            "stats": {
                "avg_time": round(profile.avg_response_time_seconds, 1),
                "accuracy": round(profile.accuracy * 100, 1),
                "hints_used": profile.hints_requested,
                "sessions": profile.sessions_completed,
            },
        }

    def get_profile(self, student_id: str) -> dict[str, Any]:
        """Retourne le profil complet d'un élève."""
        profile = self._get_profile(student_id)
        return {
            "student_id": profile.student_id,
            "avg_response_time_seconds": round(profile.avg_response_time_seconds, 1),
            "accuracy": round(profile.accuracy * 100, 1),
            "current_difficulty": profile.current_difficulty,
            "current_pace": profile.current_pace,
            "hints_requested": profile.hints_requested,
            "questions_asked": profile.questions_asked,
            "sessions_completed": profile.sessions_completed,
            "last_active": profile.last_active,
        }

    def get_recommendation(self, student_id: str) -> dict[str, Any]:
        """Recommande la prochaine action pour l'élève."""
        profile = self._get_profile(student_id)

        if profile.sessions_completed == 0:
            return {
                "action": "start_lesson",
                "message_fr": "Commence par une leçon pour découvrir le sujet.",
                "message_en": "Start with a lesson to discover the topic.",
            }

        if profile.accuracy < 0.4:
            return {
                "action": "review",
                "message_fr": "Tu as besoin de revoir les bases. Reprenons la leçon précédente.",
                "message_en": "You need to review the basics. Let's go back to the previous lesson.",
            }

        if profile.accuracy < 0.7:
            return {
                "action": "practice",
                "message_fr": "Continue à pratiquer avec des exercices. Tu progresses !",
                "message_en": "Keep practicing with exercises. You're making progress!",
            }

        if profile.avg_response_time_seconds < 20 and profile.accuracy > 0.85:
            return {
                "action": "accelerate",
                "message_fr": "Tu maîtrises bien ! Passons à des défis plus avancés.",
                "message_en": "You're doing great! Let's move to more advanced challenges.",
            }

        return {
            "action": "continue",
            "message_fr": "Continue à ton rythme, tu es sur la bonne voie.",
            "message_en": "Keep going at your pace, you're on the right track.",
        }

    def record_session_complete(self, student_id: str) -> None:
        """Enregistre la fin d'une session d'apprentissage."""
        profile = self._get_profile(student_id)
        profile.sessions_completed += 1
        profile.last_active = datetime.now(timezone.utc).isoformat()
        self._save_profile(profile)

    # ── Analyse interne ──────────────────────────────────────────────────

    def _analyze_pace(
        self, profile: StudentProfile, time_taken: float, is_correct: bool
    ) -> tuple[str, str, str]:
        """Analyse le rythme de l'élève.

        Returns: (speed, adjustment, message_fr)
        """
        avg = profile.avg_response_time_seconds

        # Trop rapide + erreurs → l'élève se précipite
        if time_taken < 15 and not is_correct and profile.accuracy < 0.5:
            return (
                "too_fast",
                "slow_down",
                "Prends ton temps. Lis bien l'énoncé. La vitesse n'est pas importante, la compréhension oui. 🐢",
            )

        # Trop rapide + juste → l'élève s'ennuie peut-être
        if time_taken < 15 and is_correct and profile.accuracy > 0.85:
            return (
                "fast",
                "challenge",
                "Tu vas vite et tu réussis ! Es-tu prêt·e pour un défi plus corsé ? 🚀",
            )

        # Très lent + erreurs → l'élève est en difficulté
        if time_taken > 120 and not is_correct:
            return (
                "struggling",
                "support",
                "Je vois que c'est difficile. Ce n'est pas grave. Veux-tu qu'on revoie la leçon ensemble ? 💪",
            )

        # Très lent + juste → l'élève est méthodique, c'est OK
        if time_taken > 120 and is_correct:
            return (
                "methodical",
                "maintain",
                "Tu prends ton temps et tu fais juste. C'est une excellente approche. Continue comme ça. ✅",
            )

        # Rythme normal
        if is_correct:
            return (
                "optimal",
                "maintain",
                "Bon rythme ! Tu comprends bien la matière. Continue. 👍",
            )
        else:
            return (
                "normal",
                "encourage",
                "Ce n'est pas grave de se tromper. Chaque erreur est une occasion d'apprendre. 🌱",
            )

    def _adjust_difficulty(
        self, profile: StudentProfile, is_correct: bool, time_taken: float
    ) -> str:
        """Ajuste la difficulté des prochaines questions."""
        levels = ["easy", "medium", "hard"]
        current_idx = levels.index(profile.current_difficulty) if profile.current_difficulty in levels else 1

        # Règle : 3 bonnes réponses rapides d'affilée → monter
        recent = profile.accuracy_history[-3:]
        recent_times = profile.response_time_history[-3:]

        if (
            len(recent) >= 3
            and all(r == 1.0 for r in recent)
            and all(t < 30 for t in recent_times)
            and current_idx < 2
        ):
            return levels[current_idx + 1]

        # Règle : 3 erreurs d'affilée → descendre
        if len(recent) >= 3 and all(r == 0.0 for r in recent) and current_idx > 0:
            return levels[current_idx - 1]

        # Règle : très lent + erreur → descendre
        if time_taken > 180 and not is_correct and current_idx > 0:
            return levels[current_idx - 1]

        return profile.current_difficulty

    # ── Persistance ──────────────────────────────────────────────────────

    def _get_profile(self, student_id: str) -> StudentProfile:
        if student_id in self._profiles:
            return self._profiles[student_id]

        filepath = self.storage_dir / f"{student_id}.json"
        if filepath.exists():
            data = json.loads(filepath.read_text(encoding="utf-8"))
            profile = StudentProfile(
                student_id=data["student_id"],
                avg_response_time_seconds=data.get("avg_response_time_seconds", 60.0),
                response_time_history=data.get("response_time_history", []),
                accuracy=data.get("accuracy", 0.0),
                accuracy_history=data.get("accuracy_history", []),
                hints_requested=data.get("hints_requested", 0),
                questions_asked=data.get("questions_asked", 0),
                sessions_completed=data.get("sessions_completed", 0),
                current_difficulty=data.get("current_difficulty", "medium"),
                current_pace=data.get("current_pace", "normal"),
                last_active=data.get("last_active", ""),
                created_at=data.get("created_at", ""),
            )
            self._profiles[student_id] = profile
            return profile

        profile = StudentProfile(student_id=student_id)
        self._profiles[student_id] = profile
        return profile

    def _save_profile(self, profile: StudentProfile) -> None:
        filepath = self.storage_dir / f"{profile.student_id}.json"
        data = {
            "student_id": profile.student_id,
            "avg_response_time_seconds": profile.avg_response_time_seconds,
            "response_time_history": profile.response_time_history[-50:],
            "accuracy": profile.accuracy,
            "accuracy_history": profile.accuracy_history[-50:],
            "hints_requested": profile.hints_requested,
            "questions_asked": profile.questions_asked,
            "sessions_completed": profile.sessions_completed,
            "current_difficulty": profile.current_difficulty,
            "current_pace": profile.current_pace,
            "last_active": profile.last_active,
            "created_at": profile.created_at,
        }
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")