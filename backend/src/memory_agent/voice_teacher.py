# -*- coding: utf-8 -*-
"""Professeur vocal — AI Formateur MAT-9F.

Le formateur PARLE (TTS edge-tts) et ÉCOUTE (STT faster-whisper).
Bilingue FR/EN. Réutilise les patterns de voice.py de Luce.

Usage:
    from memory_agent.voice_teacher import VoiceTeacher
    vt = VoiceTeacher(lang="fr")
    await vt.speak("Bonjour, aujourd'hui nous allons étudier l'algèbre.")
    question = await vt.listen()
"""

from __future__ import annotations

import asyncio
import io
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator


# ── Voix disponibles ────────────────────────────────────────────────────────

VOICES = {
    "fr": {
        "female": "fr-CA-SylvieNeural",  # Québec
        "female_fr": "fr-FR-DeniseNeural",  # France
        "male": "fr-CA-AntoineNeural",
        "male_fr": "fr-FR-HenriNeural",
    },
    "en": {
        "female": "en-US-JennyNeural",
        "female_uk": "en-GB-SoniaNeural",
        "male": "en-US-GuyNeural",
        "male_uk": "en-GB-RyanNeural",
    },
}

# Vitesse de parole par niveau
SPEED_BY_GRADE = {
    "secondary_3": "-10%",  # Plus lent pour les plus jeunes
    "secondary_4": "-5%",
    "secondary_5": "+0%",
    "cegep": "+5%",
    "university": "+10%",
}


@dataclass
class VoiceConfig:
    """Configuration de la voix du formateur."""

    lang: str = "fr"
    voice: str = "fr-CA-SylvieNeural"
    rate: str = "+0%"
    pitch: str = "+0Hz"
    volume: str = "+0%"


class VoiceTeacher:
    """Professeur vocal — parle et écoute."""

    def __init__(self, config: VoiceConfig | None = None, grade: str = "secondary_5") -> None:
        self.config = config or VoiceConfig()
        self.grade = grade
        self._whisper_model = None
        self._tts_available = False
        self._stt_available = False

    # ── TTS : Le formateur PARLE ─────────────────────────────────────────

    async def speak(self, text: str, output_path: str | None = None) -> bytes | None:
        """Lit un texte à voix haute avec edge-tts.

        Returns: audio bytes (MP3) ou None si TTS non disponible.
        """
        try:
            import edge_tts  # type: ignore
        except ImportError:
            print("[VoiceTeacher] edge-tts non installé. pip install edge-tts")
            return None

        self._tts_available = True
        rate = SPEED_BY_GRADE.get(self.grade, "+0%")

        communicate = edge_tts.Communicate(
            text=text,
            voice=self.config.voice,
            rate=rate,
            pitch=self.config.pitch,
            volume=self.config.volume,
        )

        audio_chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        if not audio_chunks:
            return None

        audio_data = b"".join(audio_chunks)

        if output_path:
            Path(output_path).write_bytes(audio_data)

        return audio_data

    async def speak_lesson(self, sections: list[dict[str, str]], pause_between: float = 1.5) -> list[bytes]:
        """Lit une leçon complète section par section.

        Returns: liste des chunks audio pour chaque section.
        """
        chunks = []
        for i, section in enumerate(sections):
            content = section.get("content", "")
            if not content.strip():
                continue

            # Nettoyer le markdown pour la lecture
            clean = self._clean_for_speech(content)
            audio = await self.speak(clean)
            if audio:
                chunks.append(audio)

            # Pause entre les sections
            if i < len(sections) - 1:
                await asyncio.sleep(pause_between)

        return chunks

    async def speak_stream(self, text: str) -> AsyncIterator[bytes]:
        """Stream audio pour lecture en continu."""
        try:
            import edge_tts
        except ImportError:
            return

        rate = SPEED_BY_GRADE.get(self.grade, "+0%")
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.config.voice,
            rate=rate,
        )
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]

    # ── STT : Le formateur ÉCOUTE ────────────────────────────────────────

    async def listen(self, audio_bytes: bytes | None = None, timeout: float = 30.0) -> str:
        """Écoute et transcrit la parole de l'élève.

        Args:
            audio_bytes: Audio WAV/MP3 bytes. Si None, écoute le micro.
            timeout: Temps max d'écoute en secondes.

        Returns: texte transcrit.
        """
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except ImportError:
            print("[VoiceTeacher] faster-whisper non installé. pip install faster-whisper")
            return ""

        if self._whisper_model is None:
            # Modèle tiny pour rapidité, ou small pour précision
            self._whisper_model = WhisperModel(
                "tiny",
                device="cpu",
                compute_type="int8",
            )
            self._stt_available = True

        if audio_bytes is None:
            # Mode micro — à implémenter avec pyaudio/sounddevice
            return await self._listen_microphone(timeout)

        # Transcrire depuis bytes
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name

        try:
            segments, _ = self._whisper_model.transcribe(temp_path, language=self.config.lang)
            text = " ".join(segment.text for segment in segments)
            return text.strip()
        finally:
            os.unlink(temp_path)

    async def _listen_microphone(self, timeout: float) -> str:
        """Écoute le microphone."""
        try:
            import sounddevice as sd
            import numpy as np
        except ImportError:
            print("[VoiceTeacher] sounddevice/numpy non installés. pip install sounddevice numpy")
            return ""

        sample_rate = 16000
        duration = min(timeout, 30.0)

        print(f"[VoiceTeacher] 🎤 Écoute... ({duration}s max)" if self.config.lang == "fr" else f"[VoiceTeacher] 🎤 Listening... ({duration}s max)")

        recording = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
        )
        sd.wait()

        # Sauvegarder en WAV
        import struct
        import wave

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            # Convertir float32 -> int16
            audio_int16 = (recording.flatten() * 32767).astype(np.int16)
            wf.writeframes(audio_int16.tobytes())

        return await self.listen(buffer.getvalue())

    # ── Mode podcast / audiobook ─────────────────────────────────────────

    async def narrate_course(self, course_data: dict, output_dir: str | None = None) -> list[str]:
        """Narre un cours complet en mode podcast/audiobook.

        Returns: liste des chemins des fichiers audio générés.
        """
        audio_files = []
        lessons = course_data.get("lessons", [])

        for lesson in lessons:
            title = lesson.get("title", "Leçon")
            sections = lesson.get("sections", [])

            # Annoncer la leçon
            if self.config.lang == "fr":
                intro = f"Leçon : {title}."
            else:
                intro = f"Lesson: {title}."

            full_text = intro + "\n\n"
            for section in sections:
                content = section.get("content", "")
                full_text += self._clean_for_speech(content) + "\n\n"

            audio = await self.speak(full_text)
            if audio and output_dir:
                dest = Path(output_dir)
                dest.mkdir(parents=True, exist_ok=True)
                filepath = dest / f"{lesson.get('lesson_id', 'lesson')}.mp3"
                filepath.write_bytes(audio)
                audio_files.append(str(filepath))

        return audio_files

    # ── Utilitaires ──────────────────────────────────────────────────────

    def _clean_for_speech(self, text: str) -> str:
        """Nettoie le markdown pour la synthèse vocale."""
        import re

        # Enlever les marqueurs markdown
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # bold
        text = re.sub(r"\*(.+?)\*", r"\1", text)  # italic
        text = re.sub(r"`(.+?)`", r"\1", text)  # code
        text = re.sub(r"#{1,6}\s*", "", text)  # headers
        text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)  # links
        text = re.sub(r"!\[.*?\]\(.+?\)", "", text)  # images
        text = re.sub(r"[-*+]\s", "", text)  # list markers
        text = re.sub(r"\n{3,}", "\n\n", text)  # multiple newlines
        text = text.replace("---", "").replace("___", "")

        return text.strip()

    def set_voice(self, voice_key: str) -> None:
        """Change la voix du formateur.

        Args:
            voice_key: "female", "male", "female_fr", "male_fr", "female_uk", "male_uk"
        """
        voices = VOICES.get(self.config.lang, VOICES["en"])
        if voice_key in voices:
            self.config.voice = voices[voice_key]

    def set_grade(self, grade: str) -> None:
        """Change le niveau (affecte la vitesse de parole)."""
        self.grade = grade

    @property
    def is_tts_available(self) -> bool:
        return self._tts_available

    @property
    def is_stt_available(self) -> bool:
        return self._stt_available

    @staticmethod
    def list_voices(lang: str = "fr") -> dict[str, str]:
        """Liste les voix disponibles pour une langue."""
        return dict(VOICES.get(lang, VOICES["en"]))