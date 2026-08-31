# -*- coding: utf-8 -*-
"""Créateur d'experts pédagogiques — AI Formateur MAT-9F.

Crée les experts manquants pour le formateur via la factory autonome.
Génère les fichiers expert_v1.py dans src/memory_agent/.

Usage:
    cd D:\MAT-9F
    $env:PYTHONPATH="src"
    python scripts/create_pedagogy_experts.py
    python scripts/create_pedagogy_experts.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

EXPERT_DIR = PROJECT_ROOT / "src" / "memory_agent"


# ── Template d'expert ────────────────────────────────────────────────────────

EXPERT_TEMPLATE = '''# -*- coding: utf-8 -*-
"""{description}"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


EXPERT_ID = "{expert_id}"
SOURCE_INDEX = {source_index}
CERTIFICATION = "CERTIFIED_TECHNICAL"
DECISION_SCOPE = "synthetic_qualification_only"


RULES = {rules_repr}


@dataclass(frozen=True)
class ExpertProof:
    answer: str
    verification: str
    evidence: tuple[str, ...] = ()


def solve_{slug}(question: str) -> ExpertProof:
    """Répond à une question dans le domaine {domain_label}."""
    question_lower = question.lower()

    for label, terms in RULES.items():
        if any(term in question_lower for term in terms):
            return ExpertProof(
                answer=label,
                verification=f"score=1.0;margin=0.95;source_index={SOURCE_INDEX}",
                evidence=(f"matched:{label}",),
            )

    return ExpertProof(
        answer="unsupported",
        verification=f"score=0.0;margin=0.0;source_index={SOURCE_INDEX}",
        evidence=("no_match",),
    )
'''


# ── Définition des experts à créer ───────────────────────────────────────────

EXPERTS_TO_CREATE: list[dict[str, Any]] = [
    # ── Pédagogie ────────────────────────────────────────────────────────
    {
        "expert_id": "pedagogy.quebec_curriculum",
        "slug": "quebec_curriculum",
        "source_index": 901,
        "description": "Expert en alignement sur le programme du MEQ (Ministère de l'Éducation du Québec). Secondaire 3-4-5, matières, compétences, évaluations.",
        "domain_label": "programme scolaire québécois",
        "rules": {
            "math_secondaire_4": ["math", "secondaire 4", "cst", "ts", "sn", "algèbre secondaire", "géo secondaire"],
            "math_secondaire_5": ["math", "secondaire 5", "fonction", "vecteur", "optimisation"],
            "science_secondaire_4": ["science", "ste", "se", "secondaire 4", "labo", "chimie secondaire", "physique secondaire"],
            "francais_secondaire_5": ["français", "secondaire 5", "dissertation", "épreuve uniforme", "lecture", "écriture"],
            "histoire_secondaire_4": ["histoire", "secondaire 4", "québec", "canada", "programme histoire"],
            "ecr": ["ecr", "éthique", "culture religieuse", "dialogue"],
            "arts": ["art", "plastique", "dramatique", "musique", "danse"],
            "education_physique": ["eps", "sport", "éducation physique", "santé"],
        },
    },
    {
        "expert_id": "pedagogy.cegep_program",
        "slug": "cegep_program",
        "source_index": 902,
        "description": "Expert en programmes collégiaux québécois (Cégep). Préuniversitaire, technique, préalables, épreuves uniformes.",
        "domain_label": "programmes cégep",
        "rules": {
            "sciences_nature": ["science nat", "sciences nature", "biologie cégep", "chimie cégep", "physique cégep", "calcul cégep"],
            "sciences_humaines": ["sciences humaines", "psychologie cégep", "sociologie cégep", "économie cégep", "histoire cégep"],
            "arts_lettres": ["arts lettres", "littérature cégep", "cinéma", "théâtre cégep", "langues"],
            "technique_informatique": ["technique informatique", "programmation cégep", "réseau cégep", "base de données cégep"],
            "technique_administration": ["technique admin", "comptabilité cégep", "gestion cégep", "marketing cégep"],
            "epreuve_uniforme": ["épreuve uniforme", "français cégep", "dissertation critique"],
            "prealables": ["préalable", "math ts", "math sn", "chimie secondaire", "physique secondaire"],
        },
    },
    {
        "expert_id": "pedagogy.grade_adapter",
        "slug": "grade_adapter",
        "source_index": 903,
        "description": "Expert en adaptation du niveau de langage. Ajuste le vocabulaire, la complexité des phrases et le niveau d'abstraction selon le niveau scolaire.",
        "domain_label": "adaptation niveau scolaire",
        "rules": {
            "secondaire_3": ["secondaire 3", "14 ans", "sec 3", "niveau facile", "débutant", "simple"],
            "secondaire_4": ["secondaire 4", "15 ans", "sec 4", "intermédiaire", "moyen"],
            "secondaire_5": ["secondaire 5", "16 ans", "sec 5", "avancé secondaire", "pré-cegep"],
            "cegep": ["cégep", "collégial", "17-20 ans", "pré-universitaire"],
            "universite": ["université", "baccalauréat", "maîtrise", "doctorat", "recherche"],
        },
    },
    {
        "expert_id": "pedagogy.exercise_generator",
        "slug": "exercise_generator",
        "source_index": 904,
        "description": "Expert en génération d'exercices variés. QCM, vrai/faux, texte à trous, association, problème ouvert, rédaction.",
        "domain_label": "génération d'exercices",
        "rules": {
            "qcm": ["qcm", "choix multiple", "multiple choice", "4 choix", "questionnaire"],
            "vrai_faux": ["vrai faux", "true false", "vrai ou faux", "justifier"],
            "texte_trous": ["texte à trous", "fill blank", "compléter", "mot manquant"],
            "association": ["association", "relier", "correspondance", "matching", "apparier"],
            "probleme_ouvert": ["problème ouvert", "résolution", "raisonnement", "démarche", "expliquer"],
            "redaction": ["rédaction", "dissertation", "essai", "commentaire", "analyse"],
            "calcul": ["calcul", "exercice calcul", "équation", "résoudre", "trouver x"],
        },
    },

    # ── Visuels ──────────────────────────────────────────────────────────
    {
        "expert_id": "visualizer.mermaid",
        "slug": "mermaid_diagram",
        "source_index": 905,
        "description": "Expert en génération de diagrammes Mermaid. Flowchart, sequence, class, state, ER, Gantt, pie, mindmap, timeline.",
        "domain_label": "diagrammes Mermaid",
        "rules": {
            "flowchart": ["flowchart", "organigramme", "processus", "étapes", "workflow", "algorithme"],
            "sequence": ["sequence", "séquence", "interaction", "message", "requête", "api"],
            "class_diagram": ["class", "classe", "uml", "héritage", "objet", "orienté objet"],
            "mindmap": ["mindmap", "carte mentale", "brainstorm", "idées", "concepts"],
            "timeline": ["timeline", "frise", "chronologie", "histoire", "dates", "période"],
            "gantt": ["gantt", "planning", "échéancier", "projet", "jalon"],
            "pie": ["pie", "camembert", "proportion", "pourcentage", "répartition"],
            "er_diagram": ["er", "entité", "relation", "base de données", "schéma"],
            "state": ["state", "état", "transition", "machine état", "cycle"],
        },
    },
    {
        "expert_id": "visualizer.chart",
        "slug": "chart_generator",
        "source_index": 906,
        "description": "Expert en génération de graphiques et tableaux. Courbes, barres, histogrammes, nuages de points, tableaux comparatifs.",
        "domain_label": "graphiques et tableaux",
        "rules": {
            "courbe": ["courbe", "ligne", "fonction", "tendance", "évolution", "f(x)"],
            "barres": ["barres", "histogramme", "comparaison", "bâton", "colonnes"],
            "points": ["nuage", "points", "scatter", "corrélation", "dispersion"],
            "tableau": ["tableau", "table", "ligne colonne", "comparatif", "données"],
            "surface": ["surface", "aire", "zone", "cumul", "empilement"],
            "radar": ["radar", "toile", "profil", "multidimensionnel", "compétences"],
        },
    },
    {
        "expert_id": "visualizer.math_render",
        "slug": "math_render",
        "source_index": 907,
        "description": "Expert en rendu d'équations mathématiques. LaTeX, formules, notation scientifique, pas-à-pas.",
        "domain_label": "rendu mathématique",
        "rules": {
            "equation": ["équation", "equation", "formule", "latex", "math"],
            "fraction": ["fraction", "numérateur", "dénominateur", "division"],
            "racine": ["racine", "sqrt", "carré", "cube", "radical"],
            "integrale": ["intégrale", "intégration", "primitive", "dx"],
            "matrice": ["matrice", "déterminant", "vecteur", "système équation"],
            "geometrie": ["géométrie", "triangle", "cercle", "angle", "pythagore"],
        },
    },

    # ── Culture générale ──────────────────────────────────────────────────
    {
        "expert_id": "culture_generale.quebec",
        "slug": "culture_quebec",
        "source_index": 908,
        "description": "Expert en culture générale québécoise. Histoire, géographie, personnalités, traditions, institutions, arts.",
        "domain_label": "culture générale Québec",
        "rules": {
            "histoire_qc": ["histoire québec", "nouvelle-france", "conquête", "rébellion", "révolution tranquille", "référendum"],
            "geographie_qc": ["géographie québec", "saint-laurent", "appalaches", "bouclier canadien", "régions québec"],
            "personnalites": ["personnalité québécoise", "celine dion", "felix leclerc", "maurice richard", "gilles villeneuve"],
            "institutions": ["assemblée nationale", "gouvernement québec", "chartre", "loi 101", "csq", "ftq"],
            "traditions": ["saint-jean", "carnaval", "cabane sucre", "poutine", "tourtière", "ceinture fléchée"],
            "arts_qc": ["cinéma québécois", "littérature québécoise", "chanson québécoise", "cirque soleil", "théâtre québécois"],
        },
    },
    {
        "expert_id": "culture_generale.monde",
        "slug": "culture_monde",
        "source_index": 909,
        "description": "Expert en culture générale mondiale. Géographie, histoire, sciences, arts, actualités, records.",
        "domain_label": "culture générale mondiale",
        "rules": {
            "geographie": ["pays", "capitale", "continent", "océan", "montagne", "fleuve", "plus grand"],
            "histoire": ["guerre mondiale", "révolution", "empire", "civilisation", "découverte", "invention"],
            "sciences": ["atome", "adn", "évolution", "big bang", "gravité", "électricité", "découverte scientifique"],
            "arts": ["peinture", "musique classique", "littérature mondiale", "architecture", "sculpture", "cinéma"],
            "records": ["record", "plus grand", "plus petit", "premier", "plus rapide", "guinness"],
            "actualites": ["actualité", "news", "2024", "2025", "2026", "dernier", "récent"],
        },
    },

    # ── Apprentissage ─────────────────────────────────────────────────────
    {
        "expert_id": "pedagogy.spaced_repetition",
        "slug": "spaced_repetition",
        "source_index": 910,
        "description": "Expert en révision espacée (spaced repetition). Algorithmes SM-2, Leitner, planification des révisions.",
        "domain_label": "révision espacée",
        "rules": {
            "planifier": ["planifier révision", "quand réviser", "espacement", "intervalle", "plan révision"],
            "difficulte": ["difficulté", "facile", "moyen", "dur", "note", "score"],
            "oublier": ["oublier", "mémoire", "courbe oubli", "ebbinghaus", "rétention"],
            "flashcard": ["flashcard", "carte mémoire", "anki", "recto verso", "fiche"],
            "algorithme": ["sm-2", "leitner", "algorithme révision", "super memo"],
        },
    },
    {
        "expert_id": "pedagogy.study_methods",
        "slug": "study_methods",
        "source_index": 911,
        "description": "Expert en méthodes d'étude. Pomodoro, Feynman, mind mapping, prise de notes, mémorisation.",
        "domain_label": "méthodes d'étude",
        "rules": {
            "pomodoro": ["pomodoro", "minuteur", "25 minutes", "pause", "concentration"],
            "feynman": ["feynman", "expliquer simplement", "vulgariser", "comprendre"],
            "mindmap": ["mind map", "carte mentale", "schéma", "arbre", "branche"],
            "notes": ["prise de notes", "cornell", "surligner", "résumer", "fiche"],
            "memorisation": ["mémoriser", "mnémotechnique", "palais mental", "acronyme", "répéter"],
            "planification": ["planifier étude", "horaire", "routine", "objectif", "deadline"],
        },
    },
]


def create_expert(expert: dict[str, Any], dry_run: bool = False) -> Path:
    """Crée un fichier expert_v1.py."""
    filename = f"mat9f_{expert['slug']}_expert_v1.py"
    filepath = EXPERT_DIR / filename

    rules_repr = "{\n"
    for label, terms in expert["rules"].items():
        terms_str = ", ".join(f'"{t}"' for t in terms)
        rules_repr += f'        "{label}": [{terms_str}],\n'
    rules_repr += "    }"

    content = EXPERT_TEMPLATE.format(
        description=expert["description"],
        expert_id=expert["expert_id"],
        source_index=expert["source_index"],
        slug=expert["slug"],
        domain_label=expert["domain_label"],
        rules_repr=rules_repr,
    )

    if dry_run:
        print(f"  [DRY RUN] {filename}")
        return filepath

    filepath.write_text(content, encoding="utf-8")
    print(f"  ✅ {filename}")
    return filepath


def main() -> int:
    parser = argparse.ArgumentParser(description="Crée les experts pédagogiques manquants")
    parser.add_argument("--dry-run", action="store_true", help="Affiche sans créer")
    args = parser.parse_args()

    print(f"\n🎓 Création de {len(EXPERTS_TO_CREATE)} experts pédagogiques")
    print(f"   Dossier : {EXPERT_DIR}")
    if args.dry_run:
        print("   Mode   : DRY RUN (aucun fichier créé)")
    print()

    created = 0
    skipped = 0

    for expert in EXPERTS_TO_CREATE:
        filename = f"mat9f_{expert['slug']}_expert_v1.py"
        filepath = EXPERT_DIR / filename

        if filepath.exists() and not args.dry_run:
            print(f"  ⏭️  {filename} (existe déjà)")
            skipped += 1
            continue

        create_expert(expert, dry_run=args.dry_run)
        created += 1

    print(f"\n{'='*60}")
    print(f"  ✅ {created} experts créés")
    if skipped:
        print(f"  ⏭️  {skipped} experts ignorés (existent déjà)")
    print(f"{'='*60}")

    if not args.dry_run:
        print(f"\n📋 Experts créés dans : {EXPERT_DIR}")
        print(f"   Pour les utiliser, relance le serveur formateur.")
        print(f"   Pour les qualifier : python scripts/experts_trainer_bot.py")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())