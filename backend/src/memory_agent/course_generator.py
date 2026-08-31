# -*- coding: utf-8 -*-
"""Générateur de cours structurés — AI Formateur MAT-9F.

Produit des cours complets (leçons, quiz, exercices, visuels) à partir
des spécialistes du catalogue Nexus MoE. Bilingue FR/EN, multi-niveaux
(Secondaire 3 → Université).

Usage:
    from memory_agent.course_generator import CourseGenerator
    gen = CourseGenerator(lang="fr", grade="secondary_5")
    course = gen.generate("formal_science.mathematics.algebra")
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .grade_adapter import GradeAdapter, GradeLevel
from .quiz_engine import QuizEngine
from .visualizer import Visualizer


SCHEMA_VERSION = "ai-formateur-course-v1"
COURSE_DIR = Path(__file__).resolve().parents[2] / "courses"


# ── Banques de contenu pédagogique ──────────────────────────────────────────

LEARNING_OBJECTIVE_VERBS = {
    "fr": [
        "Comprendre", "Expliquer", "Appliquer", "Analyser", "Résoudre",
        "Identifier", "Distinguer", "Calculer", "Démontrer", "Interpréter",
        "Comparer", "Classer", "Décrire", "Formuler", "Évaluer",
    ],
    "en": [
        "Understand", "Explain", "Apply", "Analyze", "Solve",
        "Identify", "Distinguish", "Calculate", "Demonstrate", "Interpret",
        "Compare", "Classify", "Describe", "Formulate", "Evaluate",
    ],
}

LESSON_STRUCTURES = {
    "fr": {
        "intro": "Dans cette leçon, nous allons explorer {topic}. {hook}",
        "prerequisite": "Avant de commencer, assure-toi de bien maîtriser : {prereqs}",
        "concept": "### {concept_name}\n\n{explanation}",
        "example": "**Exemple concret :** {example}",
        "check": "**As-tu bien compris ?** {question}",
        "summary": "**En résumé :**\n{points}",
        "next": "Dans la prochaine leçon : {next_topic}",
    },
    "en": {
        "intro": "In this lesson, we'll explore {topic}. {hook}",
        "prerequisite": "Before we start, make sure you understand: {prereqs}",
        "concept": "### {concept_name}\n\n{explanation}",
        "example": "**Real-world example:** {example}",
        "check": "**Quick check:** {question}",
        "summary": "**Key takeaways:**\n{points}",
        "next": "Up next: {next_topic}",
    },
}

HOOKS = {
    "fr": [
        "C'est une notion fondamentale qui te servira dans de nombreux domaines.",
        "Tu utilises déjà ce concept sans le savoir dans ta vie quotidienne !",
        "Cette idée a changé notre façon de comprendre le monde.",
        "C'est plus simple que tu ne le penses, promis !",
        "Cette notion est la clé pour comprendre la suite du programme.",
    ],
    "en": [
        "This is a fundamental concept you'll use across many fields.",
        "You already use this idea in your daily life without knowing it!",
        "This idea changed how we understand the world.",
        "It's simpler than you think, I promise!",
        "This concept is the key to understanding what comes next.",
    ],
}


@dataclass
class CourseConfig:
    """Configuration d'un cours."""

    domain: str  # e.g. "formal_science.mathematics.algebra"
    lang: str = "fr"  # "fr" | "en"
    grade: str = "secondary_5"  # GradeLevel key
    lesson_count: int = 5
    include_quiz: bool = True
    include_exercises: bool = True
    include_visuals: bool = True
    include_audio: bool = False  # TTS voice reading


@dataclass
class Lesson:
    """Une leçon individuelle."""

    lesson_id: str
    title: str
    objective: str
    prerequisites: list[str] = field(default_factory=list)
    sections: list[dict[str, str]] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    check_questions: list[str] = field(default_factory=list)
    summary_points: list[str] = field(default_factory=list)
    visuals: list[dict[str, str]] = field(default_factory=list)  # {type, code, caption}
    duration_minutes: int = 15


@dataclass
class Course:
    """Un cours complet."""

    course_id: str
    domain: str
    title: str
    description: str
    lang: str
    grade: str
    grade_label: str
    total_lessons: int
    total_duration_minutes: int
    lessons: list[Lesson] = field(default_factory=list)
    final_quiz: dict[str, Any] | None = None
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "course_id": self.course_id,
            "domain": self.domain,
            "title": self.title,
            "description": self.description,
            "lang": self.lang,
            "grade": self.grade,
            "grade_label": self.grade_label,
            "total_lessons": self.total_lessons,
            "total_duration_minutes": self.total_duration_minutes,
            "generated_at": self.generated_at,
            "lessons": [
                {
                    "lesson_id": l.lesson_id,
                    "title": l.title,
                    "objective": l.objective,
                    "prerequisites": l.prerequisites,
                    "sections": l.sections,
                    "examples": l.examples,
                    "check_questions": l.check_questions,
                    "summary_points": l.summary_points,
                    "visuals": l.visuals,
                    "duration_minutes": l.duration_minutes,
                }
                for l in self.lessons
            ],
            "final_quiz": self.final_quiz,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def save(self, directory: Path | None = None) -> Path:
        dest = directory or COURSE_DIR
        dest.mkdir(parents=True, exist_ok=True)
        filepath = dest / f"{self.course_id}.json"
        filepath.write_text(self.to_json(), encoding="utf-8")
        return filepath


# ── Domaines et leurs titres ─────────────────────────────────────────────────

DOMAIN_TITLES = {
    "fr": {
        "formal_science.mathematics.arithmetic": "Arithmétique",
        "formal_science.mathematics.algebra": "Algèbre",
        "formal_science.mathematics.geometry": "Géométrie",
        "formal_science.mathematics.calculus": "Calcul différentiel et intégral",
        "formal_science.mathematics.discrete_math": "Mathématiques discrètes",
        "formal_science.mathematics.probability": "Probabilités",
        "formal_science.mathematics.optimization": "Optimisation",
        "formal_science.mathematics.numerical_methods": "Méthodes numériques",
        "formal_science.mathematics.proof_checker": "Preuves mathématiques",
        "formal_science.logic_reasoning.propositional_logic": "Logique propositionnelle",
        "formal_science.logic_reasoning.predicate_logic": "Logique des prédicats",
        "formal_science.logic_reasoning.causal_reasoning": "Raisonnement causal",
        "formal_science.logic_reasoning.argument_critic": "Analyse d'arguments",
        "formal_science.statistics_data.descriptive_statistics": "Statistiques descriptives",
        "formal_science.statistics_data.inference": "Inférence statistique",
        "formal_science.statistics_data.experimental_design": "Planification expérimentale",
        "formal_science.statistics_data.sampling": "Échantillonnage",
        "formal_science.statistics_data.time_series": "Séries temporelles",
        "formal_science.statistics_data.causal_inference": "Inférence causale",
        "formal_science.physics.mechanics": "Mécanique",
        "formal_science.physics.thermodynamics": "Thermodynamique",
        "formal_science.physics.electromagnetism": "Électromagnétisme",
        "formal_science.physics.waves_optics": "Ondes et optique",
        "formal_science.physics.quantum": "Physique quantique",
        "formal_science.physics.relativity": "Relativité",
        "formal_science.chemistry_materials.general_chemistry": "Chimie générale",
        "formal_science.chemistry_materials.organic_chemistry": "Chimie organique",
        "formal_science.chemistry_materials.inorganic_chemistry": "Chimie inorganique",
        "formal_science.chemistry_materials.physical_chemistry": "Chimie physique",
        "formal_science.chemistry_materials.analytical_chemistry": "Chimie analytique",
        "formal_science.chemistry_materials.materials_science": "Science des matériaux",
        "formal_science.life_sciences.cell_biology": "Biologie cellulaire",
        "formal_science.life_sciences.genetics": "Génétique",
        "formal_science.life_sciences.molecular_biology": "Biologie moléculaire",
        "formal_science.life_sciences.physiology": "Physiologie",
        "formal_science.life_sciences.evolution": "Évolution",
        "formal_science.life_sciences.ecology": "Écologie",
        "formal_science.life_sciences.taxonomy": "Taxonomie",
        "formal_science.earth_space.geology": "Géologie",
        "formal_science.earth_space.climate": "Climatologie",
        "formal_science.earth_space.oceanography": "Océanographie",
        "formal_science.earth_space.meteorology": "Météorologie",
        "formal_science.earth_space.planetary_science": "Science planétaire",
        "formal_science.earth_space.astronomy": "Astronomie",
        "formal_science.earth_space.geospatial": "Géospatial",
        "formal_science.computer_science.algorithms": "Algorithmes",
        "formal_science.computer_science.data_structures": "Structures de données",
        "formal_science.computer_science.complexity": "Complexité algorithmique",
        "formal_science.computer_science.programming_languages": "Langages de programmation",
        "formal_science.computer_science.systems": "Systèmes informatiques",
        "formal_science.computer_science.databases": "Bases de données",
        "formal_science.computer_science.networks": "Réseaux",
        "formal_science.computer_science.cybersecurity": "Cybersécurité",
        "formal_science.computer_science.machine_learning": "Apprentissage automatique",
        "human_social.history_biography.chronology": "Chronologie historique",
        "human_social.history_biography.historian": "Histoire",
        "human_social.history_biography.biographer": "Biographies",
        "human_social.history_biography.source_critic": "Critique des sources historiques",
        "human_social.history_biography.intellectual_history": "Histoire des idées",
        "human_social.history_biography.material_culture": "Culture matérielle",
        "human_social.geography_demography.physical_geography": "Géographie physique",
        "human_social.geography_demography.human_geography": "Géographie humaine",
        "human_social.geography_demography.cartography": "Cartographie",
        "human_social.geography_demography.demography": "Démographie",
        "human_social.geography_demography.migration": "Migrations",
        "human_social.geography_demography.urban_studies": "Études urbaines",
        "human_social.economics_finance.microeconomics": "Microéconomie",
        "human_social.economics_finance.macroeconomics": "Macroéconomie",
        "human_social.economics_finance.public_finance": "Finances publiques",
        "human_social.economics_finance.labour_economics": "Économie du travail",
        "human_social.economics_finance.financial_analysis": "Analyse financière",
        "human_social.economics_finance.risk_economics": "Risque économique",
        "human_social.economics_finance.economic_history": "Histoire économique",
        "human_social.philosophy_education.epistemology": "Épistémologie",
        "human_social.philosophy_education.ethics": "Éthique",
        "human_social.philosophy_education.philosophy_science": "Philosophie des sciences",
        "human_social.philosophy_education.critical_thinking": "Pensée critique",
        "human_social.psychology_sociology.cognitive_psychology": "Psychologie cognitive",
        "human_social.psychology_sociology.developmental_psychology": "Psychologie du développement",
        "human_social.psychology_sociology.social_psychology": "Psychologie sociale",
        "human_social.psychology_sociology.sociology": "Sociologie",
        "human_social.psychology_sociology.anthropology": "Anthropologie",
        "human_social.politics_international.political_institutions": "Institutions politiques",
        "human_social.politics_international.elections": "Systèmes électoraux",
        "human_social.politics_international.public_administration": "Administration publique",
        "human_social.politics_international.international_relations": "Relations internationales",
        "human_social.politics_international.conflict_studies": "Études des conflits",
        "human_social.law_public_policy.jurisdiction": "Droit constitutionnel",
        "human_social.law_public_policy.legislation": "Droit législatif",
        "human_social.law_public_policy.case_law": "Jurisprudence",
        "human_social.law_public_policy.regulation": "Droit réglementaire",
        "human_social.law_public_policy.policy_analysis": "Analyse des politiques publiques",
        "creative_practical.literature_media.narrative": "Narration",
        "creative_practical.literature_media.poetry": "Poésie",
        "creative_practical.literature_media.editor": "Édition",
        "creative_practical.literature_media.screen_media": "Médias visuels",
        "creative_practical.literature_media.rhetoric": "Rhétorique",
        "creative_practical.visual_arts_design.art_history": "Histoire de l'art",
        "creative_practical.visual_arts_design.composition": "Composition visuelle",
        "creative_practical.visual_arts_design.color": "Théorie des couleurs",
        "creative_practical.visual_arts_design.typography": "Typographie",
        "creative_practical.visual_arts_design.illustration": "Illustration",
        "creative_practical.visual_arts_design.user_experience": "Design d'expérience utilisateur",
        "creative_practical.music_performing_arts.music_theory": "Théorie musicale",
        "creative_practical.music_performing_arts.composition": "Composition musicale",
        "creative_practical.music_performing_arts.arrangement": "Arrangement musical",
        "creative_practical.music_performing_arts.performance": "Interprétation musicale",
        "creative_practical.music_performing_arts.sound_design": "Design sonore",
        "creative_practical.music_performing_arts.theatre_dance": "Théâtre et danse",
        "creative_practical.software_product.requirements": "Analyse des besoins logiciels",
        "creative_practical.software_product.architecture": "Architecture logicielle",
        "creative_practical.software_product.implementation": "Implémentation logicielle",
        "creative_practical.software_product.testing": "Tests logiciels",
        "creative_practical.software_product.debugging": "Débogage",
        "creative_practical.software_product.security": "Sécurité logicielle",
        "creative_practical.software_product.product_design": "Design de produit numérique",
        "creative_practical.business_operations.strategy": "Stratégie d'entreprise",
        "creative_practical.business_operations.operations": "Gestion des opérations",
        "creative_practical.business_operations.project_management": "Gestion de projet",
        "creative_practical.business_operations.accounting": "Comptabilité",
        "creative_practical.business_operations.marketing": "Marketing",
        "creative_practical.business_operations.customer_research": "Recherche client",
        "creative_practical.business_operations.procurement": "Approvisionnement",
        "creative_practical.culinary_food.recipe_developer": "Développement de recettes",
        "creative_practical.culinary_food.culinary_technique": "Techniques culinaires",
        "creative_practical.culinary_food.baking": "Pâtisserie et boulangerie",
        "creative_practical.culinary_food.nutrition": "Nutrition",
        "creative_practical.culinary_food.food_safety": "Sécurité alimentaire",
        "creative_practical.crafts_home.woodworking": "Menuiserie",
        "creative_practical.crafts_home.sewing": "Couture",
        "creative_practical.crafts_home.electronics_maker": "Électronique",
        "creative_practical.crafts_home.home_maintenance": "Entretien domestique",
        "creative_practical.crafts_home.gardening": "Jardinage",
        "creative_practical.fashion_textiles.fashion_history": "Histoire de la mode",
        "creative_practical.fashion_textiles.garment_design": "Design de vêtements",
        "creative_practical.fashion_textiles.patternmaking": "Patronage",
        "creative_practical.fashion_textiles.textile_science": "Science des textiles",
        "creative_practical.fashion_textiles.construction": "Construction de vêtements",
        "creative_practical.fashion_textiles.styling": "Stylisme",
        "creative_practical.fashion_textiles.sustainable_fashion": "Mode durable",
        "transverse.language_communication.grammarian": "Grammaire",
        "transverse.language_communication.translator": "Traduction FR-EN",
        "transverse.language_communication.pragmatics": "Pragmatique",
        "transverse.language_communication.plain_language": "Langage clair",
        "transverse.language_communication.discourse_analyst": "Analyse du discours",
        "transverse.language_communication.accessibility_editor": "Communication accessible",
        "transverse.dictionary.lexicographer": "Lexicographie",
        "transverse.dictionary.sense_disambiguator": "Désambiguïsation lexicale",
        "transverse.dictionary.terminologist": "Terminologie",
        "transverse.dictionary.etymologist": "Étymologie",
        "transverse.dictionary.orthographer": "Orthographe",
        "transverse.dictionary.bilingual_lexicographer": "Lexicographie bilingue",
        "transverse.dictionary.usage_editor": "Usage et registre",
    },
    "en": {
        "formal_science.mathematics.arithmetic": "Arithmetic",
        "formal_science.mathematics.algebra": "Algebra",
        "formal_science.mathematics.geometry": "Geometry",
        "formal_science.mathematics.calculus": "Calculus",
        "formal_science.mathematics.discrete_math": "Discrete Mathematics",
        "formal_science.mathematics.probability": "Probability",
        "formal_science.mathematics.optimization": "Optimization",
        "formal_science.mathematics.numerical_methods": "Numerical Methods",
        "formal_science.mathematics.proof_checker": "Mathematical Proofs",
        "formal_science.logic_reasoning.propositional_logic": "Propositional Logic",
        "formal_science.logic_reasoning.predicate_logic": "Predicate Logic",
        "formal_science.logic_reasoning.causal_reasoning": "Causal Reasoning",
        "formal_science.logic_reasoning.argument_critic": "Argument Analysis",
        "formal_science.statistics_data.descriptive_statistics": "Descriptive Statistics",
        "formal_science.statistics_data.inference": "Statistical Inference",
        "formal_science.statistics_data.experimental_design": "Experimental Design",
        "formal_science.statistics_data.sampling": "Sampling Methods",
        "formal_science.statistics_data.time_series": "Time Series Analysis",
        "formal_science.statistics_data.causal_inference": "Causal Inference",
        "formal_science.physics.mechanics": "Mechanics",
        "formal_science.physics.thermodynamics": "Thermodynamics",
        "formal_science.physics.electromagnetism": "Electromagnetism",
        "formal_science.physics.waves_optics": "Waves and Optics",
        "formal_science.physics.quantum": "Quantum Physics",
        "formal_science.physics.relativity": "Relativity",
        "formal_science.chemistry_materials.general_chemistry": "General Chemistry",
        "formal_science.chemistry_materials.organic_chemistry": "Organic Chemistry",
        "formal_science.chemistry_materials.inorganic_chemistry": "Inorganic Chemistry",
        "formal_science.chemistry_materials.physical_chemistry": "Physical Chemistry",
        "formal_science.chemistry_materials.analytical_chemistry": "Analytical Chemistry",
        "formal_science.chemistry_materials.materials_science": "Materials Science",
        "formal_science.life_sciences.cell_biology": "Cell Biology",
        "formal_science.life_sciences.genetics": "Genetics",
        "formal_science.life_sciences.molecular_biology": "Molecular Biology",
        "formal_science.life_sciences.physiology": "Physiology",
        "formal_science.life_sciences.evolution": "Evolution",
        "formal_science.life_sciences.ecology": "Ecology",
        "formal_science.life_sciences.taxonomy": "Taxonomy",
        "formal_science.earth_space.geology": "Geology",
        "formal_science.earth_space.climate": "Climate Science",
        "formal_science.earth_space.oceanography": "Oceanography",
        "formal_science.earth_space.meteorology": "Meteorology",
        "formal_science.earth_space.planetary_science": "Planetary Science",
        "formal_science.earth_space.astronomy": "Astronomy",
        "formal_science.earth_space.geospatial": "Geospatial Science",
        "formal_science.computer_science.algorithms": "Algorithms",
        "formal_science.computer_science.data_structures": "Data Structures",
        "formal_science.computer_science.complexity": "Algorithmic Complexity",
        "formal_science.computer_science.programming_languages": "Programming Languages",
        "formal_science.computer_science.systems": "Computer Systems",
        "formal_science.computer_science.databases": "Databases",
        "formal_science.computer_science.networks": "Networks",
        "formal_science.computer_science.cybersecurity": "Cybersecurity",
        "formal_science.computer_science.machine_learning": "Machine Learning",
        "human_social.history_biography.chronology": "Historical Chronology",
        "human_social.history_biography.historian": "History",
        "human_social.history_biography.biographer": "Biographies",
        "human_social.history_biography.source_critic": "Historical Source Criticism",
        "human_social.history_biography.intellectual_history": "Intellectual History",
        "human_social.history_biography.material_culture": "Material Culture",
        "human_social.geography_demography.physical_geography": "Physical Geography",
        "human_social.geography_demography.human_geography": "Human Geography",
        "human_social.geography_demography.cartography": "Cartography",
        "human_social.geography_demography.demography": "Demography",
        "human_social.geography_demography.migration": "Migration Studies",
        "human_social.geography_demography.urban_studies": "Urban Studies",
        "human_social.economics_finance.microeconomics": "Microeconomics",
        "human_social.economics_finance.macroeconomics": "Macroeconomics",
        "human_social.economics_finance.public_finance": "Public Finance",
        "human_social.economics_finance.labour_economics": "Labour Economics",
        "human_social.economics_finance.financial_analysis": "Financial Analysis",
        "human_social.economics_finance.risk_economics": "Economic Risk",
        "human_social.economics_finance.economic_history": "Economic History",
        "human_social.philosophy_education.epistemology": "Epistemology",
        "human_social.philosophy_education.ethics": "Ethics",
        "human_social.philosophy_education.philosophy_science": "Philosophy of Science",
        "human_social.philosophy_education.critical_thinking": "Critical Thinking",
        "human_social.psychology_sociology.cognitive_psychology": "Cognitive Psychology",
        "human_social.psychology_sociology.developmental_psychology": "Developmental Psychology",
        "human_social.psychology_sociology.social_psychology": "Social Psychology",
        "human_social.psychology_sociology.sociology": "Sociology",
        "human_social.psychology_sociology.anthropology": "Anthropology",
        "human_social.politics_international.political_institutions": "Political Institutions",
        "human_social.politics_international.elections": "Electoral Systems",
        "human_social.politics_international.public_administration": "Public Administration",
        "human_social.politics_international.international_relations": "International Relations",
        "human_social.politics_international.conflict_studies": "Conflict Studies",
        "human_social.law_public_policy.jurisdiction": "Constitutional Law",
        "human_social.law_public_policy.legislation": "Legislation",
        "human_social.law_public_policy.case_law": "Case Law",
        "human_social.law_public_policy.regulation": "Regulatory Law",
        "human_social.law_public_policy.policy_analysis": "Public Policy Analysis",
        "creative_practical.literature_media.narrative": "Narrative Design",
        "creative_practical.literature_media.poetry": "Poetry",
        "creative_practical.literature_media.editor": "Editing",
        "creative_practical.literature_media.screen_media": "Screen Media",
        "creative_practical.literature_media.rhetoric": "Rhetoric",
        "creative_practical.visual_arts_design.art_history": "Art History",
        "creative_practical.visual_arts_design.composition": "Visual Composition",
        "creative_practical.visual_arts_design.color": "Color Theory",
        "creative_practical.visual_arts_design.typography": "Typography",
        "creative_practical.visual_arts_design.illustration": "Illustration",
        "creative_practical.visual_arts_design.user_experience": "User Experience Design",
        "creative_practical.music_performing_arts.music_theory": "Music Theory",
        "creative_practical.music_performing_arts.composition": "Music Composition",
        "creative_practical.music_performing_arts.arrangement": "Music Arrangement",
        "creative_practical.music_performing_arts.performance": "Music Performance",
        "creative_practical.music_performing_arts.sound_design": "Sound Design",
        "creative_practical.music_performing_arts.theatre_dance": "Theatre and Dance",
        "creative_practical.software_product.requirements": "Software Requirements",
        "creative_practical.software_product.architecture": "Software Architecture",
        "creative_practical.software_product.implementation": "Software Implementation",
        "creative_practical.software_product.testing": "Software Testing",
        "creative_practical.software_product.debugging": "Debugging",
        "creative_practical.software_product.security": "Software Security",
        "creative_practical.software_product.product_design": "Digital Product Design",
        "creative_practical.business_operations.strategy": "Business Strategy",
        "creative_practical.business_operations.operations": "Operations Management",
        "creative_practical.business_operations.project_management": "Project Management",
        "creative_practical.business_operations.accounting": "Accounting",
        "creative_practical.business_operations.marketing": "Marketing",
        "creative_practical.business_operations.customer_research": "Customer Research",
        "creative_practical.business_operations.procurement": "Procurement",
        "creative_practical.culinary_food.recipe_developer": "Recipe Development",
        "creative_practical.culinary_food.culinary_technique": "Culinary Techniques",
        "creative_practical.culinary_food.baking": "Baking and Pastry",
        "creative_practical.culinary_food.nutrition": "Nutrition",
        "creative_practical.culinary_food.food_safety": "Food Safety",
        "creative_practical.crafts_home.woodworking": "Woodworking",
        "creative_practical.crafts_home.sewing": "Sewing",
        "creative_practical.crafts_home.electronics_maker": "Electronics",
        "creative_practical.crafts_home.home_maintenance": "Home Maintenance",
        "creative_practical.crafts_home.gardening": "Gardening",
        "creative_practical.fashion_textiles.fashion_history": "Fashion History",
        "creative_practical.fashion_textiles.garment_design": "Garment Design",
        "creative_practical.fashion_textiles.patternmaking": "Patternmaking",
        "creative_practical.fashion_textiles.textile_science": "Textile Science",
        "creative_practical.fashion_textiles.construction": "Garment Construction",
        "creative_practical.fashion_textiles.styling": "Styling",
        "creative_practical.fashion_textiles.sustainable_fashion": "Sustainable Fashion",
        "transverse.language_communication.grammarian": "Grammar",
        "transverse.language_communication.translator": "FR-EN Translation",
        "transverse.language_communication.pragmatics": "Pragmatics",
        "transverse.language_communication.plain_language": "Plain Language",
        "transverse.language_communication.discourse_analyst": "Discourse Analysis",
        "transverse.language_communication.accessibility_editor": "Accessible Communication",
        "transverse.dictionary.lexicographer": "Lexicography",
        "transverse.dictionary.sense_disambiguator": "Word Sense Disambiguation",
        "transverse.dictionary.terminologist": "Terminology",
        "transverse.dictionary.etymologist": "Etymology",
        "transverse.dictionary.orthographer": "Orthography",
        "transverse.dictionary.bilingual_lexicographer": "Bilingual Lexicography",
        "transverse.dictionary.usage_editor": "Usage and Register",
    },
}

DOMAIN_DESCRIPTIONS = {
    "fr": {
        "formal_science.mathematics.algebra": "L'étude des relations symboliques, des équations et des structures algébriques.",
        "formal_science.mathematics.geometry": "L'étude des formes, des espaces et des relations spatiales.",
        "formal_science.mathematics.calculus": "L'étude du changement, des limites, des dérivées et des intégrales.",
        "formal_science.physics.mechanics": "L'étude des forces, du mouvement et des lois de Newton.",
        "formal_science.life_sciences.cell_biology": "L'étude de la structure et du fonctionnement des cellules.",
        "formal_science.computer_science.algorithms": "L'étude des méthodes systématiques de résolution de problèmes.",
        "human_social.history_biography.historian": "L'étude des événements passés et de leur interprétation.",
        "human_social.economics_finance.microeconomics": "L'étude des choix individuels, des marchés et des incitations.",
        "human_social.philosophy_education.ethics": "L'étude des principes moraux et des cadres éthiques.",
        "creative_practical.music_performing_arts.music_theory": "L'étude des structures musicales : rythme, mélodie et harmonie.",
    },
    "en": {
        "formal_science.mathematics.algebra": "The study of symbolic relations, equations, and algebraic structures.",
        "formal_science.mathematics.geometry": "The study of shapes, spaces, and spatial relationships.",
        "formal_science.mathematics.calculus": "The study of change, limits, derivatives, and integrals.",
        "formal_science.physics.mechanics": "The study of forces, motion, and Newton's laws.",
        "formal_science.life_sciences.cell_biology": "The study of cell structure and function.",
        "formal_science.computer_science.algorithms": "The study of systematic problem-solving methods.",
        "human_social.history_biography.historian": "The study of past events and their interpretation.",
        "human_social.economics_finance.microeconomics": "The study of individual choices, markets, and incentives.",
        "human_social.philosophy_education.ethics": "The study of moral principles and ethical frameworks.",
        "creative_practical.music_performing_arts.music_theory": "The study of musical structures: rhythm, melody, and harmony.",
    },
}


class CourseGenerator:
    """Générateur de cours structurés à partir des spécialistes MAT-9F."""

    def __init__(
        self,
        lang: str = "fr",
        grade: str = "secondary_5",
        include_visuals: bool = True,
        include_audio: bool = False,
    ) -> None:
        if lang not in ("fr", "en"):
            raise ValueError(f"Langue non supportée: {lang}")
        self.lang = lang
        self.grade = grade
        self.include_visuals = include_visuals
        self.include_audio = include_audio
        self.grade_adapter = GradeAdapter(lang=lang)
        self.quiz_engine = QuizEngine(lang=lang, grade=grade)
        self.visualizer = Visualizer(lang=lang)

    # ── API publique ─────────────────────────────────────────────────────

    def generate(self, domain: str, lesson_count: int = 5) -> Course:
        """Génère un cours complet pour un domaine expert."""
        title = self._domain_title(domain)
        description = self._domain_description(domain)
        grade_info = self.grade_adapter.get_grade_info(self.grade)
        course_id = self._make_course_id(domain, self.grade, self.lang)

        lessons = []
        for i in range(lesson_count):
            lesson = self._generate_lesson(domain, title, i + 1, lesson_count)
            lessons.append(lesson)

        total_duration = sum(l.duration_minutes for l in lessons)

        course = Course(
            course_id=course_id,
            domain=domain,
            title=title,
            description=description,
            lang=self.lang,
            grade=self.grade,
            grade_label=grade_info["label"],
            total_lessons=lesson_count,
            total_duration_minutes=total_duration,
            lessons=lessons,
        )

        if self.include_visuals:
            course.final_quiz = self.quiz_engine.generate_final_quiz(domain, title, lessons)

        return course

    def list_domains(self) -> list[dict[str, str]]:
        """Liste tous les domaines disponibles avec leurs titres."""
        titles = DOMAIN_TITLES.get(self.lang, DOMAIN_TITLES["en"])
        descriptions = DOMAIN_DESCRIPTIONS.get(self.lang, DOMAIN_DESCRIPTIONS["en"])
        result = []
        for domain_id, title in sorted(titles.items()):
            result.append({
                "domain": domain_id,
                "title": title,
                "description": descriptions.get(domain_id, ""),
                "family": domain_id.split(".")[0],
                "wheel": ".".join(domain_id.split(".")[:2]),
            })
        return result

    def list_domains_by_family(self) -> dict[str, list[dict[str, str]]]:
        """Liste les domaines regroupés par famille."""
        families: dict[str, list[dict[str, str]]] = {}
        for d in self.list_domains():
            families.setdefault(d["family"], []).append(d)
        return families

    # ── Génération interne ───────────────────────────────────────────────

    def _generate_lesson(
        self, domain: str, course_title: str, number: int, total: int
    ) -> Lesson:
        """Génère une leçon individuelle."""
        tpl = LESSON_STRUCTURES[self.lang]
        grade_info = self.grade_adapter.get_grade_info(self.grade)
        topic = self._domain_title(domain)

        # Titre et objectif
        lesson_titles = self._lesson_titles(domain, total)
        title = lesson_titles[number - 1] if number <= len(lesson_titles) else f"{topic} — Partie {number}"
        objective_verb = random.choice(LEARNING_OBJECTIVE_VERBS[self.lang])
        objective = f"{objective_verb} {title.lower()}" if self.lang == "fr" else f"{objective_verb} {title.lower()}"

        # Prérequis
        prerequisites = self._get_prerequisites(domain, number)

        # Sections de contenu
        sections = self._build_sections(domain, title, number, grade_info)

        # Exemples
        examples = self._get_examples(domain, number)

        # Questions de vérification
        check_questions = self._get_check_questions(domain, title, number)

        # Résumé
        summary_points = self._get_summary_points(domain, title, number)

        # Visuels
        visuals = []
        if self.include_visuals:
            visuals = self.visualizer.generate_for_lesson(domain, title, number)

        # Durée estimée
        duration = 15 + (5 if self.include_visuals else 0)

        lesson_id = f"{self._make_course_id(domain, self.grade, self.lang)}-L{number:02d}"

        return Lesson(
            lesson_id=lesson_id,
            title=title,
            objective=objective,
            prerequisites=prerequisites,
            sections=sections,
            examples=examples,
            check_questions=check_questions,
            summary_points=summary_points,
            visuals=visuals,
            duration_minutes=duration,
        )

    def _build_sections(
        self, domain: str, title: str, number: int, grade_info: dict[str, Any]
    ) -> list[dict[str, str]]:
        """Construit les sections de contenu de la leçon."""
        tpl = LESSON_STRUCTURES[self.lang]
        hook = random.choice(HOOKS[self.lang])
        topic = self._domain_title(domain)

        sections = []

        # Introduction
        sections.append({
            "type": "intro",
            "content": tpl["intro"].format(topic=topic, hook=hook),
        })

        # Prérequis si nécessaire
        prereqs = self._get_prerequisites(domain, number)
        if prereqs:
            sections.append({
                "type": "prerequisites",
                "content": tpl["prerequisite"].format(
                    prereqs=", ".join(prereqs)
                ),
            })

        # Concepts principaux (3-4 par leçon)
        concepts = self._get_concepts(domain, number)
        for concept in concepts:
            sections.append({
                "type": "concept",
                "concept_name": concept["name"],
                "content": tpl["concept"].format(
                    concept_name=concept["name"],
                    explanation=concept["explanation"],
                ),
            })

        # Exemple
        examples = self._get_examples(domain, number)
        if examples:
            sections.append({
                "type": "example",
                "content": tpl["example"].format(example=examples[0]),
            })

        # Vérification
        checks = self._get_check_questions(domain, title, number)
        if checks:
            sections.append({
                "type": "check",
                "content": tpl["check"].format(question=checks[0]),
            })

        # Résumé
        summary = self._get_summary_points(domain, title, number)
        sections.append({
            "type": "summary",
            "content": tpl["summary"].format(
                points="\n".join(f"- {p}" for p in summary)
            ),
        })

        return sections

    # ── Contenu par domaine ──────────────────────────────────────────────

    def _lesson_titles(self, domain: str, total: int) -> list[str]:
        """Titres des leçons pour un domaine donné."""
        base = self._domain_title(domain)
        if self.lang == "fr":
            return [
                f"Introduction à {base.lower()}",
                f"Les concepts fondamentaux",
                f"Applications et exemples",
                f"Approfondissement",
                f"Révision et synthèse",
            ][:total]
        return [
            f"Introduction to {base}",
            f"Core Concepts",
            f"Applications and Examples",
            f"Going Deeper",
            f"Review and Synthesis",
        ][:total]

    def _get_prerequisites(self, domain: str, lesson_number: int) -> list[str]:
        """Prérequis pour une leçon."""
        if lesson_number == 1:
            return []
        if self.lang == "fr":
            return [f"Leçon {lesson_number - 1} : {self._lesson_titles(domain, lesson_number)[lesson_number - 2]}"]
        return [f"Lesson {lesson_number - 1}: {self._lesson_titles(domain, lesson_number)[lesson_number - 2]}"]

    def _get_concepts(self, domain: str, lesson_number: int) -> list[dict[str, str]]:
        """Concepts clés pour une leçon."""
        # Concepts génériques par domaine — sera enrichi par les experts
        concepts_map = {
            "formal_science.mathematics.algebra": {
                "fr": [
                    {"name": "Variables et inconnues", "explanation": "Une variable est un symbole qui représente une valeur qu'on ne connaît pas encore. C'est comme une boîte mystère dont on doit trouver le contenu."},
                    {"name": "Équations du premier degré", "explanation": "Une équation comme 2x + 3 = 7 exprime une égalité. Résoudre l'équation, c'est trouver la valeur de x qui rend l'égalité vraie."},
                    {"name": "Factorisation", "explanation": "Factoriser, c'est transformer une expression en produit de facteurs. Par exemple, x² - 9 = (x-3)(x+3)."},
                ],
                "en": [
                    {"name": "Variables and Unknowns", "explanation": "A variable is a symbol that represents a value we don't know yet. It's like a mystery box whose contents we need to discover."},
                    {"name": "First-Degree Equations", "explanation": "An equation like 2x + 3 = 7 expresses an equality. Solving it means finding the value of x that makes the equality true."},
                    {"name": "Factoring", "explanation": "Factoring transforms an expression into a product of factors. For example, x² - 9 = (x-3)(x+3)."},
                ],
            },
            "formal_science.computer_science.algorithms": {
                "fr": [
                    {"name": "Qu'est-ce qu'un algorithme ?", "explanation": "Un algorithme est une suite d'instructions précises pour résoudre un problème. Comme une recette de cuisine, mais pour les ordinateurs."},
                    {"name": "Complexité", "explanation": "La complexité mesure l'efficacité d'un algorithme : combien de temps et de mémoire il utilise quand la taille des données augmente."},
                    {"name": "Tri et recherche", "explanation": "Trier des données et retrouver un élément sont deux des problèmes les plus fondamentaux en informatique."},
                ],
                "en": [
                    {"name": "What is an Algorithm?", "explanation": "An algorithm is a precise sequence of instructions to solve a problem. Like a cooking recipe, but for computers."},
                    {"name": "Complexity", "explanation": "Complexity measures an algorithm's efficiency: how much time and memory it uses as data size grows."},
                    {"name": "Sorting and Searching", "explanation": "Sorting data and finding an element are two of the most fundamental problems in computer science."},
                ],
            },
        }

        domain_concepts = concepts_map.get(domain, {}).get(self.lang, [])
        if domain_concepts:
            return domain_concepts[:3]

        # Concepts génériques par défaut
        if self.lang == "fr":
            return [
                {"name": "Concept fondamental", "explanation": "Ce concept est la base sur laquelle repose tout le reste de la matière."},
                {"name": "Mise en pratique", "explanation": "Voyons comment ce concept s'applique dans des situations concrètes."},
                {"name": "Pièges à éviter", "explanation": "Les erreurs les plus courantes et comment les éviter."},
            ]
        return [
            {"name": "Core Concept", "explanation": "This concept is the foundation upon which the rest of the subject is built."},
            {"name": "Practical Application", "explanation": "Let's see how this concept applies in real-world situations."},
            {"name": "Common Pitfalls", "explanation": "The most common mistakes and how to avoid them."},
        ]

    def _get_examples(self, domain: str, lesson_number: int) -> list[str]:
        """Exemples concrets pour une leçon."""
        if self.lang == "fr":
            return [
                "Prenons un exemple concret que tu peux observer dans la vie de tous les jours.",
                "Imagine que tu es dans cette situation : comment appliquerais-tu ce qu'on vient d'apprendre ?",
            ]
        return [
            "Let's take a concrete example you can observe in everyday life.",
            "Imagine you're in this situation: how would you apply what we just learned?",
        ]

    def _get_check_questions(self, domain: str, title: str, number: int) -> list[str]:
        """Questions de vérification de compréhension."""
        if self.lang == "fr":
            return [
                f"Peux-tu expliquer dans tes propres mots ce qu'est {title.lower()} ?",
                "Quelle est la différence entre les deux concepts qu'on vient de voir ?",
                "Peux-tu donner un exemple différent de celui présenté dans la leçon ?",
            ]
        return [
            f"Can you explain {title} in your own words?",
            "What's the difference between the two concepts we just covered?",
            "Can you give a different example from the one shown in the lesson?",
        ]

    def _get_summary_points(self, domain: str, title: str, number: int) -> list[str]:
        """Points clés du résumé."""
        if self.lang == "fr":
            return [
                f"Tu as découvert les bases de {title.lower()}",
                "Tu comprends maintenant les concepts fondamentaux",
                "Tu peux appliquer ces notions à des exemples concrets",
            ]
        return [
            f"You've discovered the basics of {title}",
            "You now understand the core concepts",
            "You can apply these ideas to concrete examples",
        ]

    # ── Utilitaires ──────────────────────────────────────────────────────

    def _domain_title(self, domain: str) -> str:
        titles = DOMAIN_TITLES.get(self.lang, DOMAIN_TITLES["en"])
        return titles.get(domain, domain.rsplit(".", 1)[-1].replace("_", " ").title())

    def _domain_description(self, domain: str) -> str:
        descriptions = DOMAIN_DESCRIPTIONS.get(self.lang, DOMAIN_DESCRIPTIONS["en"])
        default = (
            "Un cours complet pour maîtriser ce domaine."
            if self.lang == "fr"
            else "A complete course to master this domain."
        )
        return descriptions.get(domain, default)

    def _make_course_id(self, domain: str, grade: str, lang: str) -> str:
        raw = f"{domain}-{grade}-{lang}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

    @staticmethod
    def load(course_id: str, directory: Path | None = None) -> Course | None:
        """Charge un cours depuis le disque."""
        dest = directory or COURSE_DIR
        filepath = dest / f"{course_id}.json"
        if not filepath.exists():
            return None
        data = json.loads(filepath.read_text(encoding="utf-8"))
        lessons = [
            Lesson(
                lesson_id=l["lesson_id"],
                title=l["title"],
                objective=l["objective"],
                prerequisites=l.get("prerequisites", []),
                sections=l.get("sections", []),
                examples=l.get("examples", []),
                check_questions=l.get("check_questions", []),
                summary_points=l.get("summary_points", []),
                visuals=l.get("visuals", []),
                duration_minutes=l.get("duration_minutes", 15),
            )
            for l in data["lessons"]
        ]
        return Course(
            course_id=data["course_id"],
            domain=data["domain"],
            title=data["title"],
            description=data["description"],
            lang=data["lang"],
            grade=data["grade"],
            grade_label=data["grade_label"],
            total_lessons=data["total_lessons"],
            total_duration_minutes=data["total_duration_minutes"],
            lessons=lessons,
            final_quiz=data.get("final_quiz"),
            generated_at=data.get("generated_at", ""),
        )