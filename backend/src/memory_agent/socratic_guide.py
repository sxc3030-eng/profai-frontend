# -*- coding: utf-8 -*-
"""Guide socratique — AI Formateur MAT-9F.

Le formateur ne donne JAMAIS la réponse. Il fait cheminer l'élève par
questions, indices, reformulations et validation d'étapes.

Principe fondamental : l'élève doit DÉCOUVRIR, pas COPIER.

Usage:
    from memory_agent.socratic_guide import SocraticGuide
    sg = SocraticGuide(lang="fr", grade="secondary_5")
    response = sg.respond("C'est quoi la réponse de 2x+3=11?")
    # → "Je ne te donnerai pas la réponse. Réfléchissons ensemble.
    #    Si tu as 2x + 3 = 11, que peux-tu faire pour isoler x ?"
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class GuideMode(Enum):
    """Mode de réponse du guide socratique."""

    QUESTION = "question"           # Pose une question pour faire réfléchir
    HINT = "hint"                   # Donne un indice sans la réponse
    REFORMULATE = "reformulate"     # Reformule le problème autrement
    VALIDATE_STEP = "validate_step" # Valide une étape du raisonnement
    ENCOURAGE = "encourage"         # Encourage sans donner la réponse
    SCAFFOLD = "scaffold"           # Décompose en sous-étapes
    COUNTER_EXAMPLE = "counter"     # Propose un contre-exemple
    CONNECT = "connect"             # Fait le lien avec un concept connu


@dataclass
class SocraticResponse:
    """Réponse du guide socratique."""

    mode: GuideMode
    message: str
    hints_remaining: int = 3
    steps_completed: list[str] = field(default_factory=list)
    next_step: str = ""
    should_generate_visual: bool = False
    visual_type: str = ""  # "diagram", "equation", "table", "graph"


# ── Banques de réponses socratiques ──────────────────────────────────────────

_SOCRATIC_QUESTION_STARTERS = {
    "fr": [
        "Qu'est-ce que tu comprends déjà de ce problème ?",
        "Si tu devais expliquer ça à un ami, par où commencerais-tu ?",
        "Quelle information importante vois-tu dans l'énoncé ?",
        "Qu'est-ce qui te bloque exactement ?",
        "As-tu déjà vu un problème similaire ? Lequel ?",
        "Quelle serait ta première intuition, même si tu n'es pas sûr·e ?",
        "Peux-tu reformuler le problème dans tes propres mots ?",
        "Qu'est-ce qu'on cherche exactement ?",
        "Quelles sont les données qu'on connaît ?",
        "Si on enlevait les nombres, quel est le vrai problème ?",
    ],
    "en": [
        "What do you already understand about this problem?",
        "If you had to explain this to a friend, where would you start?",
        "What important information do you see in the problem statement?",
        "What exactly is blocking you?",
        "Have you seen a similar problem before? Which one?",
        "What would be your first intuition, even if you're not sure?",
        "Can you rephrase the problem in your own words?",
        "What exactly are we looking for?",
        "What information do we already know?",
        "If we removed the numbers, what's the real problem here?",
    ],
}

_SOCRATIC_HINTS = {
    "fr": [
        "Pense à ce qu'on a vu dans la leçon précédente...",
        "Et si tu essayais avec un nombre plus simple d'abord ?",
        "Regarde le mot clé dans l'énoncé. Qu'est-ce qu'il t'indique ?",
        "Quelle opération pourrait t'aider à isoler ce que tu cherches ?",
        "Fais un dessin ou un schéma de la situation.",
        "Y a-t-il une formule ou une règle qui s'applique ici ?",
        "Essaie de deviner la réponse, puis vérifie si elle fonctionne.",
        "Décompose le problème en plus petites parties.",
        "Qu'est-ce qui changerait si on modifiait cette valeur ?",
        "Compare avec l'exemple qu'on a vu ensemble.",
    ],
    "en": [
        "Think about what we covered in the previous lesson...",
        "What if you tried with a simpler number first?",
        "Look at the keyword in the problem. What does it tell you?",
        "What operation could help you isolate what you're looking for?",
        "Draw a picture or diagram of the situation.",
        "Is there a formula or rule that applies here?",
        "Try guessing the answer, then check if it works.",
        "Break the problem down into smaller parts.",
        "What would change if we modified this value?",
        "Compare with the example we did together.",
    ],
}

_SOCRATIC_ENCOURAGEMENT = {
    "fr": [
        "C'est une excellente question ! Ça montre que tu réfléchis.",
        "Tu es sur la bonne piste. Continue !",
        "C'est normal de bloquer. Même les experts bloquent. L'important c'est de persévérer.",
        "J'aime ta façon de penser. Approfondis cette idée.",
        "Tu progresses ! Chaque erreur t'apprend quelque chose.",
        "Prends ton temps. La vitesse n'est pas importante, la compréhension oui.",
        "Tu as déjà fait le plus dur : identifier ce qui te bloque.",
        "Excellent raisonnement jusqu'ici. Quelle est la prochaine étape ?",
    ],
    "en": [
        "That's an excellent question! It shows you're thinking.",
        "You're on the right track. Keep going!",
        "It's normal to get stuck. Even experts do. What matters is persevering.",
        "I like your thinking. Explore that idea further.",
        "You're making progress! Every mistake teaches you something.",
        "Take your time. Speed isn't important — understanding is.",
        "You've already done the hardest part: identifying what's blocking you.",
        "Excellent reasoning so far. What's the next step?",
    ],
}

_SOCRATIC_REFUSAL = {
    "fr": [
        "Je ne te donnerai pas la réponse, mais je vais t'aider à la trouver. {question}",
        "Si je te donne la réponse, tu n'apprendras rien. Alors dis-moi : {question}",
        "Mon rôle n'est pas de te donner des réponses, mais de t'apprendre à les trouver. {question}",
        "La réponse, c'est toi qui vas la découvrir. Pour t'aider : {question}",
        "Copier une réponse, c'est tricher contre toi-même. Réfléchissons : {question}",
    ],
    "en": [
        "I won't give you the answer, but I'll help you find it. {question}",
        "If I give you the answer, you won't learn anything. So tell me: {question}",
        "My role isn't to give you answers, but to teach you how to find them. {question}",
        "You're going to discover the answer yourself. To help you: {question}",
        "Copying an answer is cheating yourself. Let's think: {question}",
    ],
}

# Patterns qui déclenchent un refus socratique
_GIVE_ME_ANSWER_PATTERNS = {
    "fr": [
        "donne", "réponse", "c'est quoi", "combien", "quel est", "quelle est",
        "dis-moi", "dit moi", "la solution", "le résultat", "corrige", "correction",
        "fais-le", "fais le", "écris", "calcule pour moi",
    ],
    "en": [
        "give me", "answer", "what is", "what's", "tell me", "solution",
        "result", "correct", "do it", "solve", "write", "calculate for me",
    ],
}

# Patterns qui indiquent un choix de sujet (pas une demande de réponse)
_TOPIC_CHOICE_PATTERNS = {
    "fr": [
        "je veux", "j'aimerais", "je voudrais", "apprendre", "apprends",
        "étudier", "travailler", "coder", "programmer", "python", "java",
        "aide aux devoirs", "devoir", "exercice", "pratiquer", "réviser",
        "explique", "montre", "comment", "les maths", "le français",
        "les sciences", "l'histoire", "la géo", "la physique", "la chimie",
    ],
    "en": [
        "i want", "i'd like", "learn", "study", "practice", "code",
        "python", "java", "homework", "help", "explain", "show me how",
        "math", "science", "french", "history",
    ],
}

# Réponses naturelles aux choix de sujet
_TOPIC_RESPONSES = {
    "fr": [
        "D'accord ! {topic}. Par où veux-tu commencer ? As-tu un exercice précis ou une notion que tu veux comprendre ?",
        "Super, {topic} ! Dis-moi ce que tu sais déjà et ce sur quoi tu veux qu'on travaille.",
        "Très bien, on va travailler {topic}. Quel est le premier point que tu veux aborder ?",
        "Parfait ! {topic}. Est-ce que tu as un devoir ou un exercice en particulier, ou tu veux qu'on commence par les bases ?",
    ],
    "en": [
        "Great! {topic}. Where do you want to start? Do you have a specific exercise or concept you want to understand?",
        "Awesome, {topic}! Tell me what you already know and what you'd like us to work on.",
        "Perfect, let's work on {topic}. What's the first thing you want to tackle?",
        "Sounds good! {topic}. Do you have a specific homework or should we start with the basics?",
    ],
}


class SocraticGuide:
    """Guide socratique — ne donne jamais la réponse, fait cheminer."""

    def __init__(self, lang: str = "fr", grade: str = "secondary_5") -> None:
        if lang not in ("fr", "en"):
            raise ValueError(f"Langue non supportée: {lang}")
        self.lang = lang
        self.grade = grade
        self._hints_given: dict[str, int] = {}  # session_id → hints count
        self._conversation_history: dict[str, list[dict[str, str]]] = {}

    # ── API principale ───────────────────────────────────────────────────

    def respond(
        self,
        student_message: str,
        session_id: str = "default",
        context: dict[str, Any] | None = None,
    ) -> SocraticResponse:
        """Répond à un message d'élève de façon socratique.

        Ne donne JAMAIS la réponse directement. Guide par questions,
        indices, reformulations.

        Args:
            student_message: Le message de l'élève
            session_id: Identifiant de session (pour suivre les indices)
            context: Contexte optionnel {domain, lesson_title, current_step, ...}

        Returns:
            SocraticResponse avec le mode et le message
        """
        # Initialiser le suivi de session
        if session_id not in self._hints_given:
            self._hints_given[session_id] = 0
        if session_id not in self._conversation_history:
            self._conversation_history[session_id] = []

        # Stocker dans l'historique
        self._conversation_history[session_id].append({
            "role": "student",
            "content": student_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        msg_lower = student_message.lower().strip()

        # ── Détection : l'élève choisit un sujet (PAS une demande de réponse) ──
        if self._is_topic_choice(msg_lower):
            return self._respond_to_topic(student_message, session_id)

        # ── Détection : l'élève demande la réponse directement ──────────
        if self._is_demanding_answer(msg_lower):
            return self._refuse_and_guide(session_id, context)

        # ── Détection : l'élève propose une réponse ─────────────────────
        if self._is_proposing_answer(msg_lower):
            return self._validate_or_redirect(student_message, session_id, context)

        # ── Détection : l'élève est bloqué/frustré ──────────────────────
        if self._is_stuck(msg_lower):
            return self._give_hint(session_id, context)

        # ── Détection : l'élève pose une vraie question ─────────────────
        if self._is_genuine_question(msg_lower):
            return self._guide_question(student_message, session_id, context)

        # ── Par défaut : encourager et questionner ──────────────────────
        return self._encourage_and_probe(session_id, context)

    def get_visual_for_step(
        self, domain: str, step_description: str, session_id: str = "default"
    ) -> dict[str, Any]:
        """Décide quel visuel générer pour aider l'élève à comprendre une étape.

        Ne montre JAMAIS la réponse dans le visuel — seulement la structure.
        """
        # Déterminer le type de visuel le plus utile
        visual_type = self._best_visual_type(domain, step_description)

        return {
            "should_generate": True,
            "visual_type": visual_type,
            "domain": domain,
            "step": step_description,
            "instruction": self._visual_instruction(visual_type),
        }

    # ── Détection d'intention ────────────────────────────────────────────

    def _is_demanding_answer(self, msg: str) -> bool:
        patterns = _GIVE_ME_ANSWER_PATTERNS[self.lang]
        return any(p in msg for p in patterns)

    def _is_topic_choice(self, msg: str) -> bool:
        """Détecte si l'élève choisit un sujet (pas une demande de réponse)."""
        patterns = _TOPIC_CHOICE_PATTERNS[self.lang]
        return any(p in msg for p in patterns)

    def _respond_to_topic(self, student_message: str, session_id: str) -> SocraticResponse:
        """Répond naturellement à un choix de sujet."""
        template = random.choice(_TOPIC_RESPONSES[self.lang])
        # Extraire le sujet (tout après "je veux", "apprendre", etc.)
        topic = student_message.strip()
        message = template.format(topic=topic.lower())

        response = SocraticResponse(
            mode=GuideMode.ENCOURAGE,
            message=message,
            hints_remaining=3,
        )
        self._record_response(session_id, response)
        return response

    def _is_proposing_answer(self, msg: str) -> bool:
        indicators_fr = ["je pense", "je crois", "peut-être", "la réponse est", "x =", "c'est", "=", "alors"]
        indicators_en = ["i think", "i believe", "maybe", "the answer is", "x =", "it's", "=", "so"]
        indicators = indicators_fr if self.lang == "fr" else indicators_en
        return any(ind in msg for ind in indicators)

    def _is_stuck(self, msg: str) -> bool:
        stuck_fr = ["bloqué", "bloque", "comprends pas", "comprend pas", "je sais pas", "j'sais pas",
                     "aide", "help", "difficile", "trop dur", "impossible", "peux pas", "arrive pas"]
        stuck_en = ["stuck", "don't understand", "dont understand", "i don't know", "i dont know",
                     "help", "difficult", "too hard", "impossible", "can't", "cant"]
        stuck = stuck_fr if self.lang == "fr" else stuck_en
        return any(s in msg for s in stuck)

    def _is_genuine_question(self, msg: str) -> bool:
        return "?" in msg or any(
            msg.startswith(q) for q in ["comment", "pourquoi", "quand", "où", "how", "why", "when", "where"]
        )

    # ── Stratégies de réponse ────────────────────────────────────────────

    def _refuse_and_guide(
        self, session_id: str, context: dict[str, Any] | None
    ) -> SocraticResponse:
        """Refuse de donner la réponse et guide vers la découverte."""
        question = random.choice(_SOCRATIC_QUESTION_STARTERS[self.lang])
        template = random.choice(_SOCRATIC_REFUSAL[self.lang])
        message = template.format(question=question)

        response = SocraticResponse(
            mode=GuideMode.QUESTION,
            message=message,
            hints_remaining=max(0, 3 - self._hints_given.get(session_id, 0)),
        )

        self._record_response(session_id, response)
        return response

    def _validate_or_redirect(
        self, student_message: str, session_id: str, context: dict[str, Any] | None
    ) -> SocraticResponse:
        """Valide une proposition d'élève sans donner la réponse finale."""
        # On ne dit jamais "c'est correct" ou "c'est faux" directement.
        # On pose une question qui fait réfléchir sur la validité.

        if self.lang == "fr":
            responses = [
                "Intéressant ! Comment peux-tu VÉRIFIER si c'est la bonne réponse ?",
                "Et si tu testais cette hypothèse avec un exemple concret ?",
                "Qu'est-ce qui te fait penser ça ? Explique-moi ton raisonnement.",
                "Peux-tu me montrer les étapes qui t'ont mené à cette conclusion ?",
                "Cette piste est intéressante. Que se passerait-il si on changeait une valeur ?",
            ]
        else:
            responses = [
                "Interesting! How can you VERIFY if that's the right answer?",
                "What if you tested that hypothesis with a concrete example?",
                "What makes you think that? Walk me through your reasoning.",
                "Can you show me the steps that led you to that conclusion?",
                "That's an interesting lead. What would happen if we changed one value?",
            ]

        return SocraticResponse(
            mode=GuideMode.VALIDATE_STEP,
            message=random.choice(responses),
            hints_remaining=max(0, 3 - self._hints_given.get(session_id, 0)),
        )

    def _give_hint(
        self, session_id: str, context: dict[str, Any] | None
    ) -> SocraticResponse:
        """Donne un indice progressif."""
        hints_count = self._hints_given.get(session_id, 0)

        if hints_count >= 3:
            # Trop d'indices → décomposer le problème (scaffolding)
            if self.lang == "fr":
                msg = (
                    "Je vois que c'est difficile. Décomposons le problème ensemble.\n\n"
                    "Étape 1 : Qu'est-ce qu'on cherche exactement ?\n"
                    "Étape 2 : Quelles informations a-t-on ?\n"
                    "Étape 3 : Quelle est la PREMIÈRE chose qu'on pourrait faire ?\n\n"
                    "Dis-moi ce que tu trouves pour l'étape 1."
                )
            else:
                msg = (
                    "I can see this is challenging. Let's break it down together.\n\n"
                    "Step 1: What exactly are we looking for?\n"
                    "Step 2: What information do we have?\n"
                    "Step 3: What's the FIRST thing we could do?\n\n"
                    "Tell me what you find for step 1."
                )
            mode = GuideMode.SCAFFOLD
        else:
            hint = _SOCRATIC_HINTS[self.lang][hints_count % len(_SOCRATIC_HINTS[self.lang])]
            if self.lang == "fr":
                msg = f"Voici un indice (indice {hints_count + 1}/3) : {hint}"
            else:
                msg = f"Here's a hint (hint {hints_count + 1}/3): {hint}"
            mode = GuideMode.HINT

        self._hints_given[session_id] = hints_count + 1

        response = SocraticResponse(
            mode=mode,
            message=msg,
            hints_remaining=max(0, 3 - self._hints_given[session_id]),
            should_generate_visual=(hints_count >= 2),  # Visuel au 3e indice
            visual_type="diagram" if hints_count >= 2 else "",
        )

        self._record_response(session_id, response)
        return response

    def _guide_question(
        self, student_message: str, session_id: str, context: dict[str, Any] | None
    ) -> SocraticResponse:
        """Répond à une vraie question par une autre question qui guide."""
        if self.lang == "fr":
            msg = (
                f"Bonne question ! Avant d'y répondre, j'aimerais que tu réfléchisses :\n"
                f"Qu'est-ce que tu sais DÉJÀ qui pourrait t'aider à répondre à cette question ?"
            )
        else:
            msg = (
                f"Good question! Before I answer, I'd like you to think:\n"
                f"What do you ALREADY know that could help you answer this question?"
            )

        response = SocraticResponse(
            mode=GuideMode.QUESTION,
            message=msg,
            hints_remaining=max(0, 3 - self._hints_given.get(session_id, 0)),
        )
        self._record_response(session_id, response)
        return response

    def _encourage_and_probe(
        self, session_id: str, context: dict[str, Any] | None
    ) -> SocraticResponse:
        """Encourage et relance la réflexion."""
        encouragement = random.choice(_SOCRATIC_ENCOURAGEMENT[self.lang])
        question = random.choice(_SOCRATIC_QUESTION_STARTERS[self.lang])

        msg = f"{encouragement}\n\n{question}"

        response = SocraticResponse(
            mode=GuideMode.ENCOURAGE,
            message=msg,
            hints_remaining=max(0, 3 - self._hints_given.get(session_id, 0)),
        )
        self._record_response(session_id, response)
        return response

    # ── Visuels ──────────────────────────────────────────────────────────

    def _best_visual_type(self, domain: str, step: str) -> str:
        """Détermine le meilleur type de visuel pour une étape."""
        if any(k in domain for k in ["math", "algebra", "calculus", "geometry"]):
            return "equation"
        if any(k in domain for k in ["physics", "chemistry", "biology"]):
            return "diagram"
        if any(k in domain for k in ["statistics", "economics", "data"]):
            return "graph"
        if any(k in domain for k in ["history", "chronology"]):
            return "timeline"
        if any(k in domain for k in ["computer_science", "algorithms"]):
            return "flowchart"
        return "diagram"

    def _visual_instruction(self, visual_type: str) -> str:
        """Instruction pour le générateur de visuel — ne montre jamais la réponse."""
        instructions = {
            "equation": "show_structure_only",
            "diagram": "show_relationships_only",
            "graph": "show_axes_and_labels_only",
            "timeline": "show_periods_only",
            "flowchart": "show_steps_without_values",
            "table": "show_headers_only",
        }
        return instructions.get(visual_type, "show_structure_only")

    # ── Utilitaires ──────────────────────────────────────────────────────

    def _record_response(self, session_id: str, response: SocraticResponse) -> None:
        self._conversation_history[session_id].append({
            "role": "guide",
            "mode": response.mode.value,
            "content": response.message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def reset_session(self, session_id: str) -> None:
        """Réinitialise une session (nouvel exercice)."""
        self._hints_given[session_id] = 0
        self._conversation_history[session_id] = []

    def get_session_summary(self, session_id: str) -> dict[str, Any]:
        """Résumé de la session."""
        history = self._conversation_history.get(session_id, [])
        return {
            "session_id": session_id,
            "messages": len(history),
            "hints_given": self._hints_given.get(session_id, 0),
            "student_messages": sum(1 for h in history if h["role"] == "student"),
            "guide_messages": sum(1 for h in history if h["role"] == "guide"),
        }