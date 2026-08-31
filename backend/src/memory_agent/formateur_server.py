# -*- coding: utf-8 -*-
"""Serveur API AI Formateur — MAT-9F.

Endpoints REST pour le formateur : cours, quiz, voix, progression.
Bilingue FR/EN. Multi-niveaux Secondaire 3 → Université.

Usage:
    cd D:\MAT-9F
    $env:PYTHONPATH="src"
    python src/memory_agent/formateur_server.py --port 8100
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from aiohttp import web  # type: ignore

from memory_agent.course_generator import CourseGenerator, COURSE_DIR
from memory_agent.quiz_engine import QuizEngine
from memory_agent.grade_adapter import GradeAdapter
from memory_agent.visualizer import Visualizer
from memory_agent.voice_teacher import VoiceTeacher, VoiceConfig
from memory_agent.subscription import SubscriptionManager
from memory_agent.socratic_guide import SocraticGuide
from memory_agent.adaptive_pacer import AdaptivePacer
from memory_agent.dynamic_visualizer import DynamicVisualizer
from memory_agent.browser_voice import BrowserVoice
from memory_agent.auth import AuthManager


# ── Initialisation ──────────────────────────────────────────────────────────

routes = web.RouteTableDef()
course_gen: CourseGenerator | None = None
quiz_engine: QuizEngine | None = None
grade_adapter: GradeAdapter | None = None
visualizer: Visualizer | None = None
voice_teacher: VoiceTeacher | None = None
socratic_guide: SocraticGuide | None = None
adaptive_pacer: AdaptivePacer | None = None
dynamic_visualizer: DynamicVisualizer | None = None
browser_voice: BrowserVoice | None = None
sub_manager: SubscriptionManager | None = None
auth_manager: AuthManager | None = None


def get_services(lang: str = "fr", grade: str = "secondary_5") -> dict[str, Any]:
    """Retourne ou initialise les services pour une langue/niveau donnés."""
    global course_gen, quiz_engine, grade_adapter, visualizer, voice_teacher
    global socratic_guide, adaptive_pacer, dynamic_visualizer, browser_voice, sub_manager
    global auth_manager

    if course_gen is None or course_gen.lang != lang:
        course_gen = CourseGenerator(lang=lang, grade=grade, include_visuals=True, include_audio=True)
    if quiz_engine is None or quiz_engine.lang != lang:
        quiz_engine = QuizEngine(lang=lang, grade=grade)
    if grade_adapter is None or grade_adapter.lang != lang:
        grade_adapter = GradeAdapter(lang=lang)
    if visualizer is None or visualizer.lang != lang:
        visualizer = Visualizer(lang=lang)
    if voice_teacher is None:
        voice_teacher = VoiceTeacher(config=VoiceConfig(lang=lang), grade=grade)
    if socratic_guide is None or socratic_guide.lang != lang:
        socratic_guide = SocraticGuide(lang=lang, grade=grade)
    if adaptive_pacer is None:
        adaptive_pacer = AdaptivePacer()
    if dynamic_visualizer is None or dynamic_visualizer.lang != lang:
        dynamic_visualizer = DynamicVisualizer(lang=lang)
    if browser_voice is None or browser_voice.lang != lang:
        browser_voice = BrowserVoice(lang=lang, grade=grade)
    if sub_manager is None:
        sub_manager = SubscriptionManager()
    if auth_manager is None:
        auth_manager = AuthManager()

    return {
        "course_gen": course_gen,
        "quiz_engine": quiz_engine,
        "grade_adapter": grade_adapter,
        "visualizer": visualizer,
        "voice_teacher": voice_teacher,
        "socratic_guide": socratic_guide,
        "adaptive_pacer": adaptive_pacer,
        "dynamic_visualizer": dynamic_visualizer,
        "browser_voice": browser_voice,
        "sub_manager": sub_manager,
        "auth_manager": auth_manager,
    }


# ── Middleware CORS ─────────────────────────────────────────────────────────

@web.middleware
async def cors_middleware(request: web.Request, handler) -> web.StreamResponse:
    if request.method == "OPTIONS":
        response = web.Response(status=204)
    else:
        response = await handler(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


# ── Endpoints ───────────────────────────────────────────────────────────────

@routes.get("/api/health")
async def health(request: web.Request) -> web.Response:
    """Vérifie que le serveur est en ligne."""
    return web.json_response({"status": "ok", "service": "ai-formateur", "version": "1.0.0"})


# ── Authentification SaaS ─────────────────────────────────────────────────────

@routes.post("/api/auth/signup")
async def auth_signup(request: web.Request) -> web.Response:
    """Inscription d'un nouvel utilisateur."""
    svc = get_services()
    data = await request.json()
    email = data.get("email", "")
    password = data.get("password", "")
    name = data.get("name", "")
    plan = data.get("plan", "free")

    result = svc["auth_manager"].signup(email, password, name, plan)
    if "error" in result:
        return web.json_response(result, status=400)
    return web.json_response(result, status=201)


@routes.post("/api/auth/login")
async def auth_login(request: web.Request) -> web.Response:
    """Connexion d'un utilisateur."""
    svc = get_services()
    data = await request.json()
    email = data.get("email", "")
    password = data.get("password", "")

    result = svc["auth_manager"].login(email, password)
    if "error" in result:
        return web.json_response(result, status=401)
    return web.json_response(result)


@routes.post("/api/auth/refresh")
async def auth_refresh(request: web.Request) -> web.Response:
    """Rafraîchit un token expiré."""
    svc = get_services()
    data = await request.json()
    refresh_token = data.get("refresh_token", "")

    result = svc["auth_manager"].refresh_token(refresh_token)
    if result is None:
        return web.json_response({"error": "Refresh token invalide"}, status=401)
    return web.json_response(result)


@routes.get("/api/auth/verify")
async def auth_verify(request: web.Request) -> web.Response:
    """Vérifie un token."""
    svc = get_services()
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return web.json_response({"error": "Token manquant"}, status=401)

    token = header[7:]
    user = svc["auth_manager"].verify_token(token)
    if user is None:
        return web.json_response({"error": "Token invalide ou expiré"}, status=401)

    return web.json_response({"valid": True, "user": user})


@routes.get("/api/auth/user")
async def auth_user(request: web.Request) -> web.Response:
    """Récupère l'utilisateur connecté."""
    svc = get_services()
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return web.json_response({"error": "Token manquant"}, status=401)

    token = header[7:]
    claims = svc["auth_manager"].verify_token(token)
    if claims is None:
        return web.json_response({"error": "Token invalide"}, status=401)

    user = svc["auth_manager"].get_user(claims["user_id"])
    if user is None:
        return web.json_response({"error": "Utilisateur introuvable"}, status=404)

    return web.json_response(user)


@routes.post("/api/auth/update")
async def auth_update(request: web.Request) -> web.Response:
    """Met à jour le profil utilisateur."""
    svc = get_services()
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return web.json_response({"error": "Token manquant"}, status=401)

    token = header[7:]
    claims = svc["auth_manager"].verify_token(token)
    if claims is None:
        return web.json_response({"error": "Token invalide"}, status=401)

    data = await request.json()
    updates = {
        k: v for k, v in data.items()
        if k in ("name", "grade", "lang", "plan")
    }
    if svc["auth_manager"].update_user(claims["user_id"], updates):
        return web.json_response({"status": "ok"})
    return web.json_response({"error": "Rien à mettre à jour"}, status=400)


# ── Domaines ────────────────────────────────────────────────────────────────

@routes.get("/api/domains")
async def list_domains(request: web.Request) -> web.Response:
    """Liste tous les domaines disponibles."""
    lang = request.query.get("lang", "fr")
    svc = get_services(lang)
    domains = svc["course_gen"].list_domains()
    return web.json_response({"domains": domains, "total": len(domains)})


@routes.get("/api/domains/by-family")
async def list_domains_by_family(request: web.Request) -> web.Response:
    """Liste les domaines regroupés par famille."""
    lang = request.query.get("lang", "fr")
    svc = get_services(lang)
    families = svc["course_gen"].list_domains_by_family()
    return web.json_response({"families": families})


# ── Niveaux ─────────────────────────────────────────────────────────────────

@routes.get("/api/grades")
async def list_grades(request: web.Request) -> web.Response:
    """Liste tous les niveaux scolaires."""
    lang = request.query.get("lang", "fr")
    svc = get_services(lang)
    grades = svc["grade_adapter"].list_grades()
    return web.json_response({"grades": grades})


# ── Cours ───────────────────────────────────────────────────────────────────

@routes.post("/api/courses/generate")
async def generate_course(request: web.Request) -> web.Response:
    """Génère un nouveau cours."""
    data = await request.json()
    domain = data.get("domain", "")
    lang = data.get("lang", "fr")
    grade = data.get("grade", "secondary_5")
    lesson_count = int(data.get("lesson_count", 5))

    if not domain:
        return web.json_response({"error": "domain requis"}, status=400)

    svc = get_services(lang, grade)
    course = svc["course_gen"].generate(domain, lesson_count)
    course.save()

    return web.json_response(course.to_dict())


@routes.get("/api/courses/{course_id}")
async def get_course(request: web.Request) -> web.Response:
    """Récupère un cours existant."""
    course_id = request.match_info["course_id"]
    course = CourseGenerator.load(course_id)
    if course is None:
        return web.json_response({"error": "Cours introuvable"}, status=404)
    return web.json_response(course.to_dict())


@routes.get("/api/courses")
async def list_courses(request: web.Request) -> web.Response:
    """Liste tous les cours sauvegardés."""
    COURSE_DIR.mkdir(parents=True, exist_ok=True)
    courses = []
    for f in sorted(COURSE_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            courses.append({
                "course_id": data.get("course_id"),
                "title": data.get("title"),
                "domain": data.get("domain"),
                "lang": data.get("lang"),
                "grade": data.get("grade"),
                "grade_label": data.get("grade_label"),
                "total_lessons": data.get("total_lessons"),
                "total_duration_minutes": data.get("total_duration_minutes"),
                "generated_at": data.get("generated_at"),
            })
        except (json.JSONDecodeError, KeyError):
            continue
    return web.json_response({"courses": courses, "total": len(courses)})


# ── Leçons ──────────────────────────────────────────────────────────────────

@routes.get("/api/courses/{course_id}/lessons/{lesson_index}")
async def get_lesson(request: web.Request) -> web.Response:
    """Récupère une leçon spécifique."""
    course_id = request.match_info["course_id"]
    lesson_index = int(request.match_info["lesson_index"])

    course = CourseGenerator.load(course_id)
    if course is None:
        return web.json_response({"error": "Cours introuvable"}, status=404)
    if lesson_index < 0 or lesson_index >= len(course.lessons):
        return web.json_response({"error": "Leçon introuvable"}, status=404)

    lesson = course.lessons[lesson_index]
    return web.json_response({
        "course_id": course_id,
        "course_title": course.title,
        "lesson_index": lesson_index,
        "total_lessons": len(course.lessons),
        "lesson": {
            "lesson_id": lesson.lesson_id,
            "title": lesson.title,
            "objective": lesson.objective,
            "prerequisites": lesson.prerequisites,
            "sections": lesson.sections,
            "examples": lesson.examples,
            "check_questions": lesson.check_questions,
            "summary_points": lesson.summary_points,
            "visuals": lesson.visuals,
            "duration_minutes": lesson.duration_minutes,
        },
    })


# ── Quiz ────────────────────────────────────────────────────────────────────

@routes.post("/api/quiz/generate")
async def generate_quiz(request: web.Request) -> web.Response:
    """Génère un quiz."""
    data = await request.json()
    domain = data.get("domain", "")
    lesson_title = data.get("lesson_title", "")
    lang = data.get("lang", "fr")
    grade = data.get("grade", "secondary_5")
    question_count = int(data.get("question_count", 5))

    svc = get_services(lang, grade)
    quiz = svc["quiz_engine"].generate_quiz(domain, lesson_title, question_count)
    return web.json_response(quiz.to_dict())


@routes.post("/api/quiz/grade")
async def grade_quiz(request: web.Request) -> web.Response:
    """Corrige un quiz soumis."""
    data = await request.json()
    quiz_data = data.get("quiz")
    answers = data.get("answers", {})
    student_id = data.get("student_id", "anonymous")
    lang = data.get("lang", "fr")
    grade = data.get("grade", "secondary_5")

    svc = get_services(lang, grade)

    # Reconstruire le quiz depuis les données
    from memory_agent.quiz_engine import Quiz, Question
    questions = [
        Question(
            question_id=q["question_id"],
            question_type=q["question_type"],
            question=q["question"],
            choices=q.get("choices"),
            correct_answer=q["correct_answer"],
            explanation=q.get("explanation", ""),
            difficulty=q.get("difficulty", "medium"),
            points=q.get("points", 1),
            domain=q.get("domain", ""),
            tags=q.get("tags", []),
        )
        for q in quiz_data.get("questions", [])
    ]
    quiz = Quiz(
        quiz_id=quiz_data.get("quiz_id", ""),
        title=quiz_data.get("title", ""),
        description=quiz_data.get("description", ""),
        lang=lang,
        grade=grade,
        domain=quiz_data.get("domain", ""),
        questions=questions,
        total_points=quiz_data.get("total_points", len(questions)),
    )

    result = svc["quiz_engine"].grade_quiz(quiz, answers, student_id)
    feedback = svc["quiz_engine"].get_feedback(result)

    return web.json_response({
        "result": result.to_dict(),
        "feedback": feedback,
    })


@routes.post("/api/exam/generate")
async def generate_exam(request: web.Request) -> web.Response:
    """Génère un examen blanc."""
    data = await request.json()
    domain = data.get("domain", "")
    course_title = data.get("course_title", "")
    lang = data.get("lang", "fr")
    grade = data.get("grade", "secondary_5")

    svc = get_services(lang, grade)
    exam_format = svc["grade_adapter"].get_exam_format(grade)
    exam = svc["quiz_engine"].generate_exam(
        domain,
        course_title,
        question_count=exam_format["question_count"],
        time_limit_minutes=exam_format["duration"],
    )
    return web.json_response(exam.to_dict())


# ── Visuels ─────────────────────────────────────────────────────────────────

@routes.post("/api/visuals/generate")
async def generate_visuals(request: web.Request) -> web.Response:
    """Génère des visuels pour une leçon."""
    data = await request.json()
    domain = data.get("domain", "")
    title = data.get("title", "")
    lesson_number = int(data.get("lesson_number", 1))
    lang = data.get("lang", "fr")

    svc = get_services(lang)
    visuals = svc["visualizer"].generate_for_lesson(domain, title, lesson_number)
    return web.json_response({"visuals": visuals})


# ── Voix ────────────────────────────────────────────────────────────────────

@routes.post("/api/voice/speak")
async def voice_speak(request: web.Request) -> web.Response:
    """Lit un texte à voix haute. Retourne l'audio en MP3."""
    data = await request.json()
    text = data.get("text", "")
    lang = data.get("lang", "fr")
    grade = data.get("grade", "secondary_5")

    if not text:
        return web.json_response({"error": "texte requis"}, status=400)

    svc = get_services(lang, grade)
    audio = await svc["voice_teacher"].speak(text)

    if audio is None:
        return web.json_response({"error": "TTS non disponible"}, status=500)

    return web.Response(body=audio, content_type="audio/mpeg")


@routes.post("/api/voice/listen")
async def voice_listen(request: web.Request) -> web.Response:
    """Transcrit un audio en texte."""
    data = await request.json()
    lang = data.get("lang", "fr")

    svc = get_services(lang)
    audio_b64 = data.get("audio")  # base64
    if audio_b64:
        import base64
        audio_bytes = base64.b64decode(audio_b64)
    else:
        audio_bytes = None

    text = await svc["voice_teacher"].listen(audio_bytes)
    return web.json_response({"text": text})


@routes.get("/api/voice/voices")
async def list_voices(request: web.Request) -> web.Response:
    """Liste les voix disponibles."""
    lang = request.query.get("lang", "fr")
    voices = VoiceTeacher.list_voices(lang)
    return web.json_response({"voices": voices, "lang": lang})


@routes.post("/api/voice/narrate")
async def narrate_course(request: web.Request) -> web.Response:
    """Narre un cours complet en mode podcast."""
    data = await request.json()
    course_id = data.get("course_id", "")
    lang = data.get("lang", "fr")
    grade = data.get("grade", "secondary_5")

    course = CourseGenerator.load(course_id)
    if course is None:
        return web.json_response({"error": "Cours introuvable"}, status=404)

    svc = get_services(lang, grade)
    output_dir = COURSE_DIR / "audio" / course_id
    audio_files = await svc["voice_teacher"].narrate_course(course.to_dict(), str(output_dir))

    return web.json_response({"audio_files": audio_files, "course_id": course_id})


# ── Abonnement ──────────────────────────────────────────────────────────────

@routes.get("/api/subscription/{student_id}")
async def get_subscription(request: web.Request) -> web.Response:
    """Vérifie l'abonnement d'un étudiant."""
    student_id = request.match_info["student_id"]
    svc = get_services()
    sub = svc["sub_manager"].get_subscription(student_id)
    return web.json_response(sub.to_dict() if sub else {"plan": "free"})


@routes.post("/api/subscription/{student_id}")
async def update_subscription(request: web.Request) -> web.Response:
    """Met à jour l'abonnement d'un étudiant."""
    student_id = request.match_info["student_id"]
    data = await request.json()
    plan = data.get("plan", "free")
    svc = get_services()
    sub = svc["sub_manager"].set_subscription(student_id, plan)
    return web.json_response(sub.to_dict())


@routes.get("/api/subscription/plans")
async def list_plans(request: web.Request) -> web.Response:
    """Liste les plans d'abonnement disponibles."""
    lang = request.query.get("lang", "fr")
    svc = get_services(lang)
    plans = svc["sub_manager"].list_plans()
    return web.json_response({"plans": plans})


# ── RSS Feed ────────────────────────────────────────────────────────────────

@routes.get("/api/rss/feed")
async def rss_feed(request: web.Request) -> web.Response:
    """Proxy pour le flux RSS OmniPost (évite les problèmes CORS)."""
    import aiohttp

    rss_url = "https://sxc3030-eng.github.io/omnipost-rss/rss.xml"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(rss_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return web.json_response({"error": f"RSS fetch failed: {resp.status}"}, status=502)
                xml_content = await resp.text()
                return web.Response(text=xml_content, content_type="application/rss+xml")
    except Exception as e:
        return web.json_response({"error": str(e)}, status=502)


# ── Chat Mode (conversation simple, sans catalogue) ──────────────────────────

@routes.post("/api/chat/start")
async def chat_start(request: web.Request) -> web.Response:
    """Démarre une conversation selon le niveau."""
    data = await request.json()
    grade = data.get("grade", "secondary_5")
    lang = data.get("lang", "fr")
    session_id = data.get("session_id", "default")

    svc = get_services(lang, grade)
    grade_info = svc["grade_adapter"].get_grade_info(grade)

    if lang == "fr":
        message = (
            f"Bonjour ! Selon ton niveau de {grade_info['label']}, "
            f"nous pourrions aborder les mathématiques, les sciences, "
            f"le français, l'histoire, ou d'autres sujets qui t'intéressent.\n\n"
            f"As-tu une préférence ? Ou un devoir sur lequel tu voudrais travailler ?"
        )
        suggestions = ["Les maths", "Les sciences", "Le français", "L'histoire", "Aide aux devoirs"]
    else:
        message = (
            f"Hello! Based on your {grade_info['label']} level, "
            f"we could explore math, science, French, history, "
            f"or other topics you're interested in.\n\n"
            f"Any preference? Or homework you'd like help with?"
        )
        suggestions = ["Math", "Science", "French", "History", "Homework help"]

    return web.json_response({
        "message": message,
        "suggestions": suggestions,
        "grade": grade_info,
        "session_id": session_id,
    })


@routes.post("/api/chat/message")
async def chat_message(request: web.Request) -> web.Response:
    """Traite un message dans la conversation."""
    data = await request.json()
    message = data.get("message", "")
    grade = data.get("grade", "secondary_5")
    lang = data.get("lang", "fr")
    session_id = data.get("session_id", "default")

    svc = get_services(lang, grade)

    # Utiliser le guide socratique
    response = svc["socratic_guide"].respond(message, session_id)

    # Générer des suggestions contextuelles selon la réponse
    mode = response.mode.value
    if mode == "question":
        suggestions = []
    elif mode == "hint":
        suggestions = ["Je ne comprends toujours pas", "Peux-tu me donner un exemple ?"]
    elif mode == "validate_step":
        suggestions = ["J'ai vérifié et c'est bon", "Je ne suis pas sûr de ma vérification"]
    elif mode == "encourage":
        suggestions = []
    else:
        suggestions = []

    if lang == "fr" and not suggestions:
        suggestions = ["Explique-moi autrement", "Donne-moi un exemple", "Je veux essayer un exercice"]

    return web.json_response({
        "message": response.message,
        "suggestions": suggestions,
        "mode": mode,
        "hints_remaining": response.hints_remaining,
        "should_generate_visual": response.should_generate_visual,
        "visual_type": response.visual_type,
    })

@routes.post("/api/socratic/respond")
async def socratic_respond(request: web.Request) -> web.Response:
    """Répond à un élève sans jamais donner la réponse directe."""
    data = await request.json()
    message = data.get("message", "")
    session_id = data.get("session_id", "default")
    lang = data.get("lang", "fr")
    grade = data.get("grade", "secondary_5")
    context = data.get("context")

    svc = get_services(lang, grade)
    response = svc["socratic_guide"].respond(message, session_id, context)

    return web.json_response({
        "mode": response.mode.value,
        "message": response.message,
        "hints_remaining": response.hints_remaining,
        "steps_completed": response.steps_completed,
        "next_step": response.next_step,
        "should_generate_visual": response.should_generate_visual,
        "visual_type": response.visual_type,
    })


@routes.post("/api/socratic/visual")
async def socratic_visual(request: web.Request) -> web.Response:
    """Génère un visuel adapté au blocage de l'élève."""
    data = await request.json()
    blockage = data.get("blockage", "")
    domain = data.get("domain", "")
    lang = data.get("lang", "fr")
    grade = data.get("grade", "secondary_5")

    svc = get_services(lang, grade)
    visual = svc["dynamic_visualizer"].generate(blockage, domain, grade)

    return web.json_response(visual)


@routes.post("/api/socratic/reset")
async def socratic_reset(request: web.Request) -> web.Response:
    """Réinitialise une session socratique."""
    data = await request.json()
    session_id = data.get("session_id", "default")
    lang = data.get("lang", "fr")
    grade = data.get("grade", "secondary_5")

    svc = get_services(lang, grade)
    svc["socratic_guide"].reset_session(session_id)
    return web.json_response({"status": "ok", "session_id": session_id})


# ── Rythme Adaptatif ────────────────────────────────────────────────────────────

@routes.post("/api/pace/assess")
async def pace_assess(request: web.Request) -> web.Response:
    """Évalue la perf ormance et ajuste le rythme."""
    data = await request.json()
    student_id = data.get("student_id", "anonymous")
    time_taken = float(data.get("time_taken_seconds", 30))
    is_correct = bool(data.get("is_correct", True))
    hints_used = int(data.get("hints_used", 0))
    difficulty = data.get("question_difficulty", "medium")

    svc = get_services()
    result = svc["adaptive_pacer"].assess(
        student_id, time_taken, is_correct, hints_used, difficulty
    )
    return web.json_response(result)


@routes.get("/api/pace/profile/{student_id}")
async def pace_profile(request: web.Request) -> web.Response:
    """Profil d'apprentissage d'un élève."""
    student_id = request.match_info["student_id"]
    svc = get_services()
    profile = svc["adaptive_pacer"].get_profile(student_id)
    return web.json_response(profile)


@routes.get("/api/pace/recommend/{student_id}")
async def pace_recommend(request: web.Request) -> web.Response:
    """Recommandation pour la prochaine action."""
    student_id = request.match_info["student_id"]
    svc = get_services()
    rec = svc["adaptive_pacer"].get_recommendation(student_id)
    return web.json_response(rec)


@routes.post("/api/pace/session-complete")
async def pace_session_complete(request: web.Request) -> web.Response:
    """Marque une session comme complétée."""
    data = await request.json()
    student_id = data.get("student_id", "anonymous")
    svc = get_services()
    svc["adaptive_pacer"].record_session_complete(student_id)
    return web.json_response({"status": "ok"})


# ── Voix Navigateur ───────────────────────────────────────────────────────

@routes.post("/api/browser-voice/leson")
async def bv_leson(request: web.Request) -> web.Response:
    """Prépare une leçon pour lecture vocale navigateur."""
    data = await request.json()
    sections = data.get("sections", [])
    lang = data.get("lang", "fr")
    grade = data.get("grade", "secondary_5")

    svc = get_services(lang, grade)
    speech_data = svc["browser_voice"].prepare_lesson_speech(sections)
    return web.json_response(svc["browser_voice"].to_browser_json(speech_data))


@routes.post("/api/browser-voice/quiz")
async def bv_quiz(request: web.Request) -> web.Response:
    """Prépare une question quiz pour lecture vocale."""
    data = await request.json()
    question = data.get("question", "")
    choices = data.get("choices")
    lang = data.get("lang", "fr")
    grade = data.get("grade", "secondary_5")

    svc = get_services(lang, grade)
    speech_data = svc["browser_voice"].prepare_quiz_speech(question, choices)
    return web.json_response(svc["browser_voice"].to_browser_json(speech_data))


# ── Visuels Dynamiques ──────────────────────────────────────────────────────

@routes.post("/api/visuels/generate")
async def generate_visuels(request: web.Request) -> web.Response:
    """Génère des visuels adaptés au blocage de l'élève."""
    data = await request.json()
    blockage = data.get("blockage", "")
    domain = data.get("domain", "")
    lang = data.get("lang", "fr")
    grade = data.get("grade", "secondary_5")

    svc = get_services(lang, grade)
    visual = svc["dynamic_visualizer"].generate(blockage, domain, grade)
    return web.json_response(visual)


# ── Progression ─────────────────────────────────────────────────────────────

_progress_store: dict[str, dict[str, Any]] = {}


@routes.get("/api/progress/{student_id}")
async def get_progress(request: web.Request) -> web.Response:
    """Récupère la progression d'un étudiant."""
    student_id = request.match_info["student_id"]
    progress = _progress_store.get(student_id, {"completed_courses": [], "completed_quizzes": [], "total_points": 0})
    return web.json_response(progress)


@routes.post("/api/progress/{student_id}")
async def update_progress(request: web.Request) -> web.Response:
    """Met à jour la progression d'un étudiant."""
    student_id = request.match_info["student_id"]
    data = await request.json()

    if student_id not in _progress_store:
        _progress_store[student_id] = {"completed_courses": [], "completed_quizzes": [], "total_points": 0}

    progress = _progress_store[student_id]

    if "course_id" in data:
        if data["course_id"] not in progress["completed_courses"]:
            progress["completed_courses"].append(data["course_id"])

    if "quiz_result" in data:
        progress["completed_quizzes"].append(data["quiz_result"])
        progress["total_points"] += data["quiz_result"].get("score", 0)

    return web.json_response(progress)


# ── Démarrage ───────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Serveur API AI Formateur MAT-9F")
    parser.add_argument("--port", type=int, default=8100)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    args = parser.parse_args()

    app = web.Application(middlewares=[cors_middleware])
    app.add_routes(routes)

    # Servir les fichiers statiques (UI)
    web_dir = PROJECT_ROOT / "web"
    if web_dir.is_dir():
        app.router.add_static("/", web_dir, show_index=True)

    print(f"🎓 AI Formateur — http://{args.host}:{args.port}")
    print(f"   UI: http://{args.host}:{args.port}/formateur.html")
    print(f"   API: http://{args.host}:{args.port}/api/health")
    web.run_app(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()