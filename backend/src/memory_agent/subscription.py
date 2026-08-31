# -*- coding: utf-8 -*-
"""Module d'abonnement et monétisation — AI Formateur MAT-9F.

Gère les plans d'abonnement, les limites et les paiements.
Bilingue FR/EN.

Usage:
    from memory_agent.subscription import SubscriptionManager
    sm = SubscriptionManager()
    sm.set_subscription("student_123", "student")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


SUBSCRIPTION_DIR = Path(__file__).resolve().parents[2] / "subscriptions"


@dataclass
class Plan:
    """Un plan d'abonnement."""

    plan_id: str
    name_fr: str
    name_en: str
    price_monthly: float  # EUR
    price_yearly: float  # EUR
    max_courses: int
    max_quizzes_per_day: int
    max_students: int  # Pour les plans famille/école
    features: list[str]
    features_fr: list[str]


PLANS: dict[str, Plan] = {
    "free": Plan(
        plan_id="free",
        name_fr="Gratuit",
        name_en="Free",
        price_monthly=0,
        price_yearly=0,
        max_courses=3,
        max_quizzes_per_day=10,
        max_students=1,
        features=[
            "3 courses", "10 quizzes/day", "Basic visuals",
            "Text lessons", "Community support",
        ],
        features_fr=[
            "3 cours", "10 quiz/jour", "Visuels de base",
            "Leçons texte", "Support communauté",
        ],
    ),
    "student": Plan(
        plan_id="student",
        name_fr="Étudiant",
        name_en="Student",
        price_monthly=5,
        price_yearly=50,
        max_courses=999,
        max_quizzes_per_day=999,
        max_students=1,
        features=[
            "All courses", "Unlimited quizzes", "Advanced visuals",
            "Spaced repetition", "Practice exams", "Voice teacher",
            "Progress tracking", "Certificates",
        ],
        features_fr=[
            "Tous les cours", "Quiz illimités", "Visuels avancés",
            "Révision espacée", "Examens blancs", "Professeur vocal",
            "Suivi de progression", "Certificats",
        ],
    ),
    "family": Plan(
        plan_id="family",
        name_fr="Famille",
        name_en="Family",
        price_monthly=12,
        price_yearly=120,
        max_courses=999,
        max_quizzes_per_day=999,
        max_students=4,
        features=[
            "4 student profiles", "Parent dashboard", "All courses",
            "Unlimited quizzes", "Voice teacher", "Progress reports",
            "Practice exams", "Certificates",
        ],
        features_fr=[
            "4 profils élèves", "Tableau de bord parent", "Tous les cours",
            "Quiz illimités", "Professeur vocal", "Rapports de progression",
            "Examens blancs", "Certificats",
        ],
    ),
    "school": Plan(
        plan_id="school",
        name_fr="École",
        name_en="School",
        price_monthly=99,
        price_yearly=990,
        max_courses=999,
        max_quizzes_per_day=999,
        max_students=30,
        features=[
            "30 student profiles", "Teacher dashboard", "All courses",
            "Unlimited quizzes", "Voice teacher", "Assignment system",
            "Grade book", "Curriculum alignment", "Priority support",
        ],
        features_fr=[
            "30 profils élèves", "Tableau de bord enseignant", "Tous les cours",
            "Quiz illimités", "Professeur vocal", "Système de devoirs",
            "Carnet de notes", "Alignement programme", "Support prioritaire",
        ],
    ),
}


@dataclass
class Subscription:
    """Abonnement d'un utilisateur."""

    student_id: str
    plan_id: str
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str | None = None
    auto_renew: bool = False
    payment_method: str | None = None

    def is_active(self) -> bool:
        if self.plan_id == "free":
            return True
        if self.expires_at is None:
            return True
        return datetime.now(timezone.utc) < datetime.fromisoformat(self.expires_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "student_id": self.student_id,
            "plan_id": self.plan_id,
            "started_at": self.started_at,
            "expires_at": self.expires_at,
            "auto_renew": self.auto_renew,
            "is_active": self.is_active(),
        }


class SubscriptionManager:
    """Gestionnaire d'abonnements."""

    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = storage_dir or SUBSCRIPTION_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def list_plans(self, lang: str = "fr") -> list[dict[str, Any]]:
        """Liste tous les plans disponibles."""
        return [
            {
                "plan_id": p.plan_id,
                "name": p.name_fr if lang == "fr" else p.name_en,
                "price_monthly": p.price_monthly,
                "price_yearly": p.price_yearly,
                "max_courses": p.max_courses,
                "max_quizzes_per_day": p.max_quizzes_per_day,
                "max_students": p.max_students,
                "features": p.features_fr if lang == "fr" else p.features,
            }
            for p in PLANS.values()
        ]

    def get_plan(self, plan_id: str) -> Plan | None:
        """Récupère un plan par son ID."""
        return PLANS.get(plan_id)

    def get_subscription(self, student_id: str) -> Subscription | None:
        """Récupère l'abonnement d'un étudiant."""
        filepath = self.storage_dir / f"{student_id}.json"
        if not filepath.exists():
            return None
        data = json.loads(filepath.read_text(encoding="utf-8"))
        return Subscription(
            student_id=data["student_id"],
            plan_id=data["plan_id"],
            started_at=data.get("started_at", ""),
            expires_at=data.get("expires_at"),
            auto_renew=data.get("auto_renew", False),
            payment_method=data.get("payment_method"),
        )

    def set_subscription(self, student_id: str, plan_id: str) -> Subscription:
        """Définit ou met à jour l'abonnement d'un étudiant."""
        if plan_id not in PLANS:
            raise ValueError(f"Plan inconnu: {plan_id}")

        plan = PLANS[plan_id]
        now = datetime.now(timezone.utc)

        sub = Subscription(
            student_id=student_id,
            plan_id=plan_id,
            started_at=now.isoformat(),
            expires_at=(now + timedelta(days=30)).isoformat() if plan_id != "free" else None,
            auto_renew=plan_id != "free",
        )

        filepath = self.storage_dir / f"{student_id}.json"
        filepath.write_text(json.dumps(sub.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

        return sub

    def check_access(self, student_id: str, resource: str) -> dict[str, Any]:
        """Vérifie si un étudiant a accès à une ressource.

        Returns: {"allowed": bool, "reason": str, "plan": str}
        """
        sub = self.get_subscription(student_id)
        plan_id = sub.plan_id if sub else "free"
        plan = PLANS.get(plan_id, PLANS["free"])

        if not sub or not sub.is_active():
            return {"allowed": False, "reason": "subscription_expired", "plan": plan_id}

        if resource == "course" and plan.max_courses < 999:
            # Compter les cours déjà suivis
            return {"allowed": True, "reason": "ok", "plan": plan_id}

        if resource == "quiz":
            return {"allowed": True, "reason": "ok", "plan": plan_id}

        return {"allowed": True, "reason": "ok", "plan": plan_id}

    def get_usage_stats(self, student_id: str) -> dict[str, Any]:
        """Statistiques d'utilisation pour un étudiant."""
        sub = self.get_subscription(student_id)
        plan_id = sub.plan_id if sub else "free"
        plan = PLANS.get(plan_id, PLANS["free"])

        return {
            "student_id": student_id,
            "plan": plan_id,
            "plan_name": plan.name_fr,
            "is_active": sub.is_active() if sub else True,
            "limits": {
                "max_courses": plan.max_courses,
                "max_quizzes_per_day": plan.max_quizzes_per_day,
                "max_students": plan.max_students,
            },
        }