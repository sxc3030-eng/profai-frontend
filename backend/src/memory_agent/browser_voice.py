# -*- coding: utf-8 -*-
"""Module voix navigateur — AI Formateur MAT-9F.

Délègue la synthèse et reconnaissance vocale au navigateur (Web Speech API).
Zéro dépendance serveur. Fonctionne sur Chromebook, iPad, tous navigateurs.

Le serveur renvoie juste le texte, le navigateur fait TTS/STT gratuitement.

Usage (serveur):
    from memory_agent.browser_voice import BrowserVoice
    bv = BrowserVoice(lang="fr")
    result = bv.get_speech_data("Bonjour, aujourd'hui nous allons étudier l'algèbre.")
    # → {"text": "...", "lang": "fr", "voice": "fr-CA", "rate": 1.0, "chunks": [...]}

Usage (navigateur — intégré dans formateur.html):
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'fr-CA';
    speechSynthesis.speak(utterance);
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Configuration des voix navigateur ────────────────────────────────────────

BROWSER_VOICES = {
    "fr": {
        "female": {"lang": "fr-CA", "name": "Sylvie (Canada)"},
        "female_fr": {"lang": "fr-FR", "name": "Denise (France)"},
        "male": {"lang": "fr-CA", "name": "Antoine (Canada)"},
    },
    "en": {
        "female": {"lang": "en-US", "name": "Jenny (US)"},
        "female_uk": {"lang": "en-GB", "name": "Sonia (UK)"},
        "male": {"lang": "en-US", "name": "Guy (US)"},
    },
}

# Vitesse de parole par niveau (le navigateur gère ça)
BROWSER_RATES = {
    "secondary_3": 0.85,
    "secondary_4": 0.92,
    "secondary_5": 1.0,
    "cegep": 1.08,
    "university": 1.15,
}


@dataclass
class SpeechChunk:
    """Un morceau de texte à lire."""

    text: str
    lang: str = "fr-CA"
    rate: float = 1.0
    pitch: float = 1.0
    pause_after_ms: int = 500


@dataclass
class SpeechData:
    """Données de synthèse vocale pour le navigateur."""

    chunks: list[SpeechChunk] = field(default_factory=list)
    total_duration_estimate_ms: int = 0
    lang: str = "fr-CA"
    voice_preference: str = "female"


class BrowserVoice:
    """Prépare les données vocales pour le navigateur.

    Le serveur ne fait AUCUNE synthèse vocale. Il prépare juste le texte
    en chunks optimisés pour la Web Speech API du navigateur.
    """

    def __init__(self, lang: str = "fr", grade: str = "secondary_5") -> None:
        if lang not in ("fr", "en"):
            raise ValueError(f"Langue non supportée: {lang}")
        self.lang = lang
        self.grade = grade
        self.rate = BROWSER_RATES.get(grade, 1.0)

    # ── API publique ─────────────────────────────────────────────────────

    def prepare_lesson_speech(self, sections: list[dict[str, str]]) -> SpeechData:
        """Prépare une leçon complète pour lecture vocale navigateur.

        Args:
            sections: Liste de sections {type, content} de la leçon

        Returns:
            SpeechData avec chunks optimisés pour le navigateur
        """
        lang_code = "fr-CA" if self.lang == "fr" else "en-US"
        chunks = []

        for section in sections:
            content = section.get("content", "")
            if not content.strip():
                continue

            # Nettoyer le markdown pour la lecture
            clean = self._clean_for_speech(content)

            # Découper en phrases pour des chunks naturels
            sentences = self._split_sentences(clean)
            for sentence in sentences:
                if sentence.strip():
                    pause = 800 if sentence.endswith("?") else 500
                    chunks.append(SpeechChunk(
                        text=sentence.strip(),
                        lang=lang_code,
                        rate=self.rate,
                        pause_after_ms=pause,
                    ))

        # Estimer la durée (approx 150 mots/min)
        total_words = sum(len(c.text.split()) for c in chunks)
        estimated_ms = int(total_words / 150 * 60 * 1000)

        return SpeechData(
            chunks=chunks,
            total_duration_estimate_ms=estimated_ms,
            lang=lang_code,
            voice_preference="female",
        )

    def prepare_quiz_speech(self, question: str, choices: list[str] | None = None) -> SpeechData:
        """Prépare une question de quiz pour lecture vocale."""
        lang_code = "fr-CA" if self.lang == "fr" else "en-US"
        chunks = [SpeechChunk(text=question, lang=lang_code, rate=self.rate, pause_after_ms=1000)]

        if choices:
            for i, choice in enumerate(choices):
                prefix = f"Choix {i+1}. " if self.lang == "fr" else f"Choice {i+1}. "
                chunks.append(SpeechChunk(
                    text=prefix + choice,
                    lang=lang_code,
                    rate=self.rate,
                    pause_after_ms=600,
                ))

        return SpeechData(
            chunks=chunks,
            total_duration_estimate_ms=len(question.split()) * 400,
            lang=lang_code,
        )

    def prepare_feedback_speech(self, is_correct: bool, explanation: str) -> SpeechData:
        """Prépare un feedback vocal pour une réponse."""
        lang_code = "fr-CA" if self.lang == "fr" else "en-US"

        if self.lang == "fr":
            prefix = "✅ Bonne réponse ! " if is_correct else "❌ Pas tout à fait. "
        else:
            prefix = "✅ Correct! " if is_correct else "❌ Not quite. "

        chunks = [
            SpeechChunk(text=prefix + explanation, lang=lang_code, rate=self.rate, pause_after_ms=500),
        ]

        return SpeechData(chunks=chunks, total_duration_estimate_ms=3000, lang=lang_code)

    def to_browser_json(self, speech_data: SpeechData) -> dict[str, Any]:
        """Convertit en JSON pour le navigateur."""
        return {
            "lang": speech_data.lang,
            "voicePreference": speech_data.voice_preference,
            "totalDurationMs": speech_data.total_duration_estimate_ms,
            "chunks": [
                {
                    "text": c.text,
                    "lang": c.lang,
                    "rate": c.rate,
                    "pitch": c.pitch,
                    "pauseAfterMs": c.pause_after_ms,
                }
                for c in speech_data.chunks
            ],
        }

    # ── Utilitaires ──────────────────────────────────────────────────────

    def _clean_for_speech(self, text: str) -> str:
        """Nettoie le markdown pour la synthèse vocale."""
        import re

        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"\*(.+?)\*", r"\1", text)
        text = re.sub(r"`(.+?)`", r"\1", text)
        text = re.sub(r"#{1,6}\s*", "", text)
        text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
        text = re.sub(r"!\[.*?\]\(.+?\)", "", text)
        text = re.sub(r"[-*+]\s", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.replace("---", "").replace("___", "")
        return text.strip()

    def _split_sentences(self, text: str) -> list[str]:
        """Découpe en phrases pour des chunks naturels."""
        import re

        # Découper sur . ! ? mais garder les nombres
        sentences = re.split(r"(?<=[.!?])\s+", text)
        # Fusionner les phrases trop courtes
        merged = []
        buffer = ""
        for s in sentences:
            if len(buffer.split()) + len(s.split()) < 15:
                buffer += " " + s if buffer else s
            else:
                if buffer:
                    merged.append(buffer)
                buffer = s
        if buffer:
            merged.append(buffer)
        return merged or [text]

    @staticmethod
    def get_browser_voices(lang: str = "fr") -> dict[str, dict[str, str]]:
        """Retourne les voix navigateur disponibles pour une langue."""
        return dict(BROWSER_VOICES.get(lang, BROWSER_VOICES["en"]))