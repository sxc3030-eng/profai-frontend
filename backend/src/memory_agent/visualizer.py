# -*- coding: utf-8 -*-
"""Générateur de visuels pédagogiques — AI Formateur MAT-9F.

Génère des diagrammes Mermaid, graphiques et cartes mentales pour
accompagner les leçons. Bilingue FR/EN.

Usage:
    from memory_agent.visualizer import Visualizer
    viz = Visualizer(lang="fr")
    diagrams = viz.generate_for_lesson("formal_science.mathematics.algebra", "Algèbre", 1)
"""

from __future__ import annotations

from typing import Any


class Visualizer:
    """Générateur de visuels pédagogiques."""

    def __init__(self, lang: str = "fr") -> None:
        if lang not in ("fr", "en"):
            raise ValueError(f"Langue non supportée: {lang}")
        self.lang = lang

    # ── API publique ─────────────────────────────────────────────────────

    def generate_for_lesson(
        self, domain: str, title: str, lesson_number: int
    ) -> list[dict[str, str]]:
        """Génère tous les visuels pour une leçon.

        Returns: list of {"type": "mermaid"|"svg"|"chart", "code": "...", "caption": "..."}
        """
        visuals = []

        # Diagramme conceptuel (toujours)
        concept_diagram = self._concept_map(domain, title)
        if concept_diagram:
            visuals.append(concept_diagram)

        # Diagramme de processus (si applicable)
        process_diagram = self._process_diagram(domain, title)
        if process_diagram:
            visuals.append(process_diagram)

        # Frise chronologique (histoire seulement)
        if "history" in domain or "chronology" in domain:
            timeline = self._timeline(domain, title)
            if timeline:
                visuals.append(timeline)

        # Comparaison (leçons 2+)
        if lesson_number >= 2:
            comparison = self._comparison_diagram(domain, title)
            if comparison:
                visuals.append(comparison)

        return visuals

    def mermaid_to_html(self, mermaid_code: str, caption: str = "") -> str:
        """Wrapper HTML pour un diagramme Mermaid."""
        return f"""<div class="visual-container">
  <div class="mermaid">
{mermaid_code}
  </div>
  {f'<p class="visual-caption">{caption}</p>' if caption else ''}
</div>"""

    # ── Diagrammes par domaine ───────────────────────────────────────────

    def _concept_map(self, domain: str, title: str) -> dict[str, str] | None:
        """Carte conceptuelle du domaine."""
        diagrams = {
            "formal_science.mathematics.algebra": {
                "fr": (
                    "graph TD\n"
                    '    A["🔢 Algèbre"] --> B["Variables\net inconnues"]\n'
                    '    A --> C["Équations\net inéquations"]\n'
                    '    A --> D["Fonctions\net graphiques"]\n'
                    '    B --> E["x, y, z"]\n'
                    '    C --> F["2x+3=11"]\n'
                    '    C --> G["x²-9=0"]\n'
                    '    D --> H["f(x)=mx+b"]\n'
                    '    D --> I["Paraboles"]'
                ),
                "en": (
                    "graph TD\n"
                    '    A["🔢 Algebra"] --> B["Variables\nand Unknowns"]\n'
                    '    A --> C["Equations\nand Inequalities"]\n'
                    '    A --> D["Functions\nand Graphs"]\n'
                    '    B --> E["x, y, z"]\n'
                    '    C --> F["2x+3=11"]\n'
                    '    C --> G["x²-9=0"]\n'
                    '    D --> H["f(x)=mx+b"]\n'
                    '    D --> I["Parabolas"]'
                ),
            },
            "formal_science.computer_science.algorithms": {
                "fr": (
                    "graph TD\n"
                    '    A["🤖 Algorithmes"] --> B["Tri"]\n'
                    '    A --> C["Recherche"]\n'
                    '    A --> D["Complexité"]\n'
                    '    B --> E["Bubble sort\nO(n²)"]\n'
                    '    B --> F["Merge sort\nO(n log n)"]\n'
                    '    C --> G["Linéaire\nO(n)"]\n'
                    '    C --> H["Dichotomique\nO(log n)"]\n'
                    '    D --> I["Temps"]\n'
                    '    D --> J["Espace"]'
                ),
                "en": (
                    "graph TD\n"
                    '    A["🤖 Algorithms"] --> B["Sorting"]\n'
                    '    A --> C["Searching"]\n'
                    '    A --> D["Complexity"]\n'
                    '    B --> E["Bubble sort\nO(n²)"]\n'
                    '    B --> F["Merge sort\nO(n log n)"]\n'
                    '    C --> G["Linear\nO(n)"]\n'
                    '    C --> H["Binary\nO(log n)"]\n'
                    '    D --> I["Time"]\n'
                    '    D --> J["Space"]'
                ),
            },
            "formal_science.physics.mechanics": {
                "fr": (
                    "graph TD\n"
                    '    A["⚡ Mécanique"] --> B["Cinématique\nmouvement"]\n'
                    '    A --> C["Dynamique\nforces"]\n'
                    '    A --> D["Énergie"]\n'
                    '    B --> E["Position\nx(t)"]\n'
                    '    B --> F["Vitesse\nv(t)"]\n'
                    '    B --> G["Accélération\na(t)"]\n'
                    '    C --> H["F = ma"]\n'
                    '    D --> I["Cinétique"]\n'
                    '    D --> J["Potentielle"]'
                ),
                "en": (
                    "graph TD\n"
                    '    A["⚡ Mechanics"] --> B["Kinematics\nmotion"]\n'
                    '    A --> C["Dynamics\nforces"]\n'
                    '    A --> D["Energy"]\n'
                    '    B --> E["Position\nx(t)"]\n'
                    '    B --> F["Velocity\nv(t)"]\n'
                    '    B --> G["Acceleration\na(t)"]\n'
                    '    C --> H["F = ma"]\n'
                    '    D --> I["Kinetic"]\n'
                    '    D --> J["Potential"]'
                ),
            },
            "formal_science.life_sciences.cell_biology": {
                "fr": (
                    "graph TD\n"
                    '    A["🧬 Cellule"] --> B["Noyau\nADN"]\n'
                    '    A --> C["Cytoplasme"]\n'
                    '    A --> D["Membrane"]\n'
                    '    B --> E["Chromosomes"]\n'
                    '    B --> F["Nucléole"]\n'
                    '    C --> G["Mitochondries\nénergie"]\n'
                    '    C --> H["Ribosomes\nprotéines"]\n'
                    '    D --> I["Protection"]\n'
                    '    D --> J["Transport"]'
                ),
                "en": (
                    "graph TD\n"
                    '    A["🧬 Cell"] --> B["Nucleus\nDNA"]\n'
                    '    A --> C["Cytoplasm"]\n'
                    '    A --> D["Membrane"]\n'
                    '    B --> E["Chromosomes"]\n'
                    '    B --> F["Nucleolus"]\n'
                    '    C --> G["Mitochondria\nenergy"]\n'
                    '    C --> H["Ribosomes\nproteins"]\n'
                    '    D --> I["Protection"]\n'
                    '    D --> J["Transport"]'
                ),
            },
            "human_social.economics_finance.microeconomics": {
                "fr": (
                    "graph TD\n"
                    '    A["💰 Microéconomie"] --> B["Offre\net Demande"]\n'
                    '    A --> C["Marchés"]\n'
                    '    A --> D["Comportement\ndu consommateur"]\n'
                    '    B --> E["Prix\nd\'équilibre"]\n'
                    '    C --> F["Concurrence\nparfaite"]\n'
                    '    C --> G["Monopole"]\n'
                    '    D --> H["Utilité"]\n'
                    '    D --> I["Contrainte\nbudgétaire"]'
                ),
                "en": (
                    "graph TD\n"
                    '    A["💰 Microeconomics"] --> B["Supply\nand Demand"]\n'
                    '    A --> C["Markets"]\n'
                    '    A --> D["Consumer\nBehavior"]\n'
                    '    B --> E["Equilibrium\nPrice"]\n'
                    '    C --> F["Perfect\nCompetition"]\n'
                    '    C --> G["Monopoly"]\n'
                    '    D --> H["Utility"]\n'
                    '    D --> I["Budget\nConstraint"]'
                ),
            },
        }

        domain_diagrams = diagrams.get(domain, {})
        mermaid = domain_diagrams.get(self.lang)
        if not mermaid:
            return None

        captions = {
            "fr": f"Carte conceptuelle : {title}",
            "en": f"Concept Map: {title}",
        }
        return {"type": "mermaid", "code": mermaid, "caption": captions[self.lang]}

    def _process_diagram(self, domain: str, title: str) -> dict[str, str] | None:
        """Diagramme de processus/flux."""
        diagrams = {
            "formal_science.mathematics.algebra": {
                "fr": (
                    "graph LR\n"
                    '    A["📝 Problème"] --> B["Identifier\nles variables"]\n'
                    '    B --> C["Poser\nl\'équation"]\n'
                    '    C --> D["Isoler\nl\'inconnue"]\n'
                    '    D --> E["Vérifier\nla solution"]\n'
                    '    E --> F["✅ Réponse"]'
                ),
                "en": (
                    "graph LR\n"
                    '    A["📝 Problem"] --> B["Identify\nVariables"]\n'
                    '    B --> C["Set Up\nEquation"]\n'
                    '    C --> D["Isolate\nUnknown"]\n'
                    '    D --> E["Verify\nSolution"]\n'
                    '    E --> F["✅ Answer"]'
                ),
            },
            "formal_science.computer_science.algorithms": {
                "fr": (
                    "graph LR\n"
                    '    A["📥 Entrée"] --> B["Diviser\nle problème"]\n'
                    '    B --> C["Résoudre\nchaque partie"]\n'
                    '    C --> D["Combiner\nles résultats"]\n'
                    '    D --> E["📤 Sortie"]'
                ),
                "en": (
                    "graph LR\n"
                    '    A["📥 Input"] --> B["Divide\nProblem"]\n'
                    '    B --> C["Solve\nEach Part"]\n'
                    '    C --> D["Combine\nResults"]\n'
                    '    D --> E["📤 Output"]'
                ),
            },
        }

        domain_diagrams = diagrams.get(domain, {})
        mermaid = domain_diagrams.get(self.lang)
        if not mermaid:
            return None

        captions = {
            "fr": f"Méthode de résolution : {title}",
            "en": f"Solution Method: {title}",
        }
        return {"type": "mermaid", "code": mermaid, "caption": captions[self.lang]}

    def _timeline(self, domain: str, title: str) -> dict[str, str] | None:
        """Frise chronologique pour les cours d'histoire."""
        captions = {
            "fr": f"Frise chronologique : {title}",
            "en": f"Timeline: {title}",
        }
        return {
            "type": "mermaid",
            "code": (
                "timeline\n"
                '    title Chronologie historique\n'
                "    section Antiquité\n"
                "      -3000 : Premières civilisations\n"
                "      -500 : Âge classique\n"
                "    section Moyen Âge\n"
                "      476 : Chute de Rome\n"
                "      800 : Empire carolingien\n"
                "    section Moderne\n"
                "      1789 : Révolution française\n"
                "      1945 : Fin Seconde Guerre mondiale"
            ),
            "caption": captions[self.lang],
        }

    def _comparison_diagram(self, domain: str, title: str) -> dict[str, str] | None:
        """Diagramme de comparaison."""
        captions = {
            "fr": f"Comparaison : concepts clés de {title}",
            "en": f"Comparison: Key Concepts in {title}",
        }
        return {
            "type": "mermaid",
            "code": (
                "graph LR\n"
                '    subgraph "Concept A"\n'
                "        A1[Caractéristique 1]\n"
                "        A2[Caractéristique 2]\n"
                "    end\n"
                '    subgraph "Concept B"\n'
                "        B1[Caractéristique 1]\n"
                "        B2[Caractéristique 2]\n"
                "    end\n"
                '    A1 -. "Différence" .-> B1\n'
                '    A2 -. "Similaire" .-> B2'
            ),
            "caption": captions[self.lang],
        }