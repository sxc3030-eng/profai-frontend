# -*- coding: utf-8 -*-
"""Visualiseur enrichi — AI Formateur MAT-9F.

Génère diagrammes Mermaid, graphiques SVG, tableaux HTML, équations LaTeX,
cartes mentales, frises chronologiques. Bilingue FR/EN.

Usage:
    from memory_agent.enhanced_visualizer import EnhancedVisualizer
    ev = EnhancedVisualizer(lang="fr")
    visuals = ev.generate_all("formal_science.mathematics.algebra", "Algèbre", 1)
"""

from __future__ import annotations

import json
from typing import Any


class EnhancedVisualizer:
    """Visualiseur enrichi — tous types de visuels pédagogiques."""

    def __init__(self, lang: str = "fr") -> None:
        if lang not in ("fr", "en"):
            raise ValueError(f"Langue non supportée: {lang}")
        self.lang = lang

    # ── API publique ─────────────────────────────────────────────────────

    def generate_all(
        self, domain: str, title: str, lesson_number: int
    ) -> dict[str, list[dict[str, Any]]]:
        """Génère TOUS les types de visuels pour une leçon.

        Returns: {"diagrams": [...], "charts": [...], "tables": [...], "math": [...], "mindmaps": [...]}
        """
        return {
            "diagrams": self.generate_diagrams(domain, title, lesson_number),
            "charts": self.generate_charts(domain, title),
            "tables": self.generate_tables(domain, title),
            "math": self.generate_math(domain, title),
            "mindmaps": self.generate_mindmaps(domain, title),
        }

    # ── Diagrammes Mermaid ───────────────────────────────────────────────

    def generate_diagrams(
        self, domain: str, title: str, lesson_number: int
    ) -> list[dict[str, Any]]:
        """Génère les diagrammes Mermaid pertinents."""
        diagrams = []

        # Toujours : carte conceptuelle
        concept = self._concept_map(domain, title)
        if concept:
            diagrams.append(concept)

        # Processus/flux
        flow = self._flowchart(domain, title)
        if flow:
            diagrams.append(flow)

        # Séquence (pour les processus avec étapes)
        if lesson_number >= 2:
            seq = self._sequence_diagram(domain, title)
            if seq:
                diagrams.append(seq)

        # Timeline (histoire)
        if any(k in domain for k in ["history", "chronology", "evolution"]):
            tl = self._timeline(domain, title)
            if tl:
                diagrams.append(tl)

        # Comparaison
        if lesson_number >= 2:
            comp = self._comparison(domain, title)
            if comp:
                diagrams.append(comp)

        return diagrams

    def _concept_map(self, domain: str, title: str) -> dict[str, Any] | None:
        """Carte conceptuelle."""
        maps = {
            "formal_science.mathematics.algebra": {
                "fr": (
                    "graph TD\n"
                    '    A["🔢 Algèbre"] --> B["Variables"]\n'
                    '    A --> C["Équations"]\n'
                    '    A --> D["Fonctions"]\n'
                    '    B --> E["x, y, z"]\n'
                    '    C --> F["2x+3=11"]\n'
                    '    C --> G["x²-9=0"]\n'
                    '    D --> H["f(x)=mx+b"]\n'
                    '    D --> I["Paraboles"]\n'
                    '    style A fill:#38bdf8,stroke:#0284c7,color:#0f172a\n'
                    '    style B fill:#818cf8,stroke:#4f46e5,color:#fff\n'
                    '    style C fill:#818cf8,stroke:#4f46e5,color:#fff\n'
                    '    style D fill:#818cf8,stroke:#4f46e5,color:#fff'
                ),
                "en": (
                    "graph TD\n"
                    '    A["🔢 Algebra"] --> B["Variables"]\n'
                    '    A --> C["Equations"]\n'
                    '    A --> D["Functions"]\n'
                    '    B --> E["x, y, z"]\n'
                    '    C --> F["2x+3=11"]\n'
                    '    C --> G["x²-9=0"]\n'
                    '    D --> H["f(x)=mx+b"]\n'
                    '    D --> I["Parabolas"]\n'
                    '    style A fill:#38bdf8,stroke:#0284c7,color:#0f172a\n'
                    '    style B fill:#818cf8,stroke:#4f46e5,color:#fff\n'
                    '    style C fill:#818cf8,stroke:#4f46e5,color:#fff\n'
                    '    style D fill:#818cf8,stroke:#4f46e5,color:#fff'
                ),
            },
            "formal_science.computer_science.algorithms": {
                "fr": (
                    "graph TD\n"
                    '    A["🤖 Algorithmes"] --> B["Tri"]\n'
                    '    A --> C["Recherche"]\n'
                    '    A --> D["Complexité"]\n'
                    '    B --> E["Bubble O(n²)"]\n'
                    '    B --> F["Merge O(n log n)"]\n'
                    '    C --> G["Linéaire O(n)"]\n'
                    '    C --> H["Dichotomique O(log n)"]\n'
                    '    D --> I["Temps"]\n'
                    '    D --> J["Espace"]\n'
                    '    style A fill:#38bdf8,stroke:#0284c7,color:#0f172a'
                ),
                "en": (
                    "graph TD\n"
                    '    A["🤖 Algorithms"] --> B["Sorting"]\n'
                    '    A --> C["Searching"]\n'
                    '    A --> D["Complexity"]\n'
                    '    B --> E["Bubble O(n²)"]\n'
                    '    B --> F["Merge O(n log n)"]\n'
                    '    C --> G["Linear O(n)"]\n'
                    '    C --> H["Binary O(log n)"]\n'
                    '    D --> I["Time"]\n'
                    '    D --> J["Space"]\n'
                    '    style A fill:#38bdf8,stroke:#0284c7,color:#0f172a'
                ),
            },
        }
        mermaid = maps.get(domain, {}).get(self.lang)
        if not mermaid:
            return None
        return {
            "type": "mermaid",
            "subtype": "concept_map",
            "code": mermaid,
            "caption": f"Carte conceptuelle : {title}" if self.lang == "fr" else f"Concept Map: {title}",
        }

    def _flowchart(self, domain: str, title: str) -> dict[str, Any] | None:
        """Diagramme de flux."""
        flows = {
            "formal_science.mathematics.algebra": {
                "fr": (
                    "graph LR\n"
                    '    A["📝 Problème"] --> B["Identifier\nvariables"]\n'
                    '    B --> C["Poser\néquation"]\n'
                    '    C --> D["Isoler\ninconnue"]\n'
                    '    D --> E["Vérifier\nsolution"]\n'
                    '    E --> F["✅ Réponse"]\n'
                    '    style A fill:#fbbf24,stroke:#d97706,color:#0f172a\n'
                    '    style F fill:#34d399,stroke:#059669,color:#0f172a'
                ),
                "en": (
                    "graph LR\n"
                    '    A["📝 Problem"] --> B["Identify\nVariables"]\n'
                    '    B --> C["Set Up\nEquation"]\n'
                    '    C --> D["Isolate\nUnknown"]\n'
                    '    D --> E["Verify\nSolution"]\n'
                    '    E --> F["✅ Answer"]\n'
                    '    style A fill:#fbbf24,stroke:#d97706,color:#0f172a\n'
                    '    style F fill:#34d399,stroke:#059669,color:#0f172a'
                ),
            },
        }
        mermaid = flows.get(domain, {}).get(self.lang)
        if not mermaid:
            return None
        return {
            "type": "mermaid",
            "subtype": "flowchart",
            "code": mermaid,
            "caption": f"Méthode : {title}" if self.lang == "fr" else f"Method: {title}",
        }

    def _sequence_diagram(self, domain: str, title: str) -> dict[str, Any] | None:
        """Diagramme de séquence."""
        return {
            "type": "mermaid",
            "subtype": "sequence",
            "code": (
                "sequenceDiagram\n"
                "    participant E as Élève\n"
                "    participant P as Professeur\n"
                "    participant C as Concept\n"
                "    E->>P: Question\n"
                "    P->>C: Vérifier\n"
                "    C-->>P: Explication\n"
                "    P-->>E: Réponse\n"
                "    E->>E: Comprendre ✅"
            ),
            "caption": "Interaction d'apprentissage" if self.lang == "fr" else "Learning Interaction",
        }

    def _timeline(self, domain: str, title: str) -> dict[str, Any] | None:
        """Frise chronologique."""
        return {
            "type": "mermaid",
            "subtype": "timeline",
            "code": (
                "timeline\n"
                "    title " + (f"Chronologie : {title}" if self.lang == "fr" else f"Timeline: {title}") + "\n"
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
            "caption": f"Frise chronologique : {title}" if self.lang == "fr" else f"Timeline: {title}",
        }

    def _comparison(self, domain: str, title: str) -> dict[str, Any] | None:
        """Diagramme de comparaison."""
        return {
            "type": "mermaid",
            "subtype": "comparison",
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
                '    A1 -.->|"Différence"| B1\n'
                '    A2 -.->|"Similaire"| B2'
            ),
            "caption": f"Comparaison : {title}" if self.lang == "fr" else f"Comparison: {title}",
        }

    # ── Graphiques SVG ───────────────────────────────────────────────────

    def generate_charts(self, domain: str, title: str) -> list[dict[str, Any]]:
        """Génère des graphiques SVG."""
        charts = []

        # Graphique en barres (toujours utile)
        bar = self._bar_chart(domain, title)
        if bar:
            charts.append(bar)

        # Courbe (maths, sciences, économie)
        if any(k in domain for k in ["math", "calculus", "physics", "economics", "statistics"]):
            curve = self._line_chart(domain, title)
            if curve:
                charts.append(curve)

        # Camembert (stats, économie, démographie)
        if any(k in domain for k in ["statistics", "economics", "demography", "probability"]):
            pie = self._pie_chart(domain, title)
            if pie:
                charts.append(pie)

        return charts

    def _bar_chart(self, domain: str, title: str) -> dict[str, Any] | None:
        """Graphique en barres SVG."""
        colors = ["#38bdf8", "#818cf8", "#34d399", "#fbbf24", "#f472b6", "#f87171"]
        bars = ""
        values = [85, 72, 63, 91, 78, 55]
        labels_fr = ["Concept A", "Concept B", "Concept C", "Concept D", "Concept E", "Concept F"]
        labels_en = ["Concept A", "Concept B", "Concept C", "Concept D", "Concept E", "Concept F"]
        labels = labels_fr if self.lang == "fr" else labels_en

        for i, (val, label) in enumerate(zip(values[:6], labels[:6])):
            h = val * 2
            y = 200 - h
            bars += f'<rect x="{40 + i * 80}" y="{y}" width="50" height="{h}" fill="{colors[i]}" rx="4">'
            bars += f'<title>{label}: {val}%</title></rect>\n'
            bars += f'<text x="{65 + i * 80}" y="220" text-anchor="middle" fill="#94a3b8" font-size="11">{label}</text>\n'
            bars += f'<text x="{65 + i * 80}" y="{y - 8}" text-anchor="middle" fill="#f1f5f9" font-size="12" font-weight="700">{val}%</text>\n'

        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 250" width="100%" height="auto">\n'
            f'<text x="260" y="25" text-anchor="middle" fill="#f1f5f9" font-size="14" font-weight="700">{title}</text>\n'
            f'{bars}'
            '</svg>'
        )
        return {
            "type": "chart",
            "subtype": "bar",
            "format": "svg",
            "code": svg,
            "caption": f"Comparaison : {title}" if self.lang == "fr" else f"Comparison: {title}",
        }

    def _line_chart(self, domain: str, title: str) -> dict[str, Any] | None:
        """Graphique en courbe SVG."""
        points = "10,150 90,120 170,140 250,80 330,60 410,90 490,40"
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 200" width="100%" height="auto">\n'
            f'<text x="260" y="20" text-anchor="middle" fill="#f1f5f9" font-size="14" font-weight="700">{title}</text>\n'
            f'<polyline points="{points}" fill="none" stroke="#38bdf8" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>\n'
            f'<circle cx="10" cy="150" r="4" fill="#38bdf8"/>\n'
            f'<circle cx="90" cy="120" r="4" fill="#38bdf8"/>\n'
            f'<circle cx="170" cy="140" r="4" fill="#38bdf8"/>\n'
            f'<circle cx="250" cy="80" r="4" fill="#38bdf8"/>\n'
            f'<circle cx="330" cy="60" r="4" fill="#38bdf8"/>\n'
            f'<circle cx="410" cy="90" r="4" fill="#38bdf8"/>\n'
            f'<circle cx="490" cy="40" r="4" fill="#38bdf8"/>\n'
            '</svg>'
        )
        return {
            "type": "chart",
            "subtype": "line",
            "format": "svg",
            "code": svg,
            "caption": f"Évolution : {title}" if self.lang == "fr" else f"Trend: {title}",
        }

    def _pie_chart(self, domain: str, title: str) -> dict[str, Any] | None:
        """Camembert SVG."""
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 200" width="100%" height="auto">\n'
            f'<text x="150" y="20" text-anchor="middle" fill="#f1f5f9" font-size="14" font-weight="700">{title}</text>\n'
            '<circle cx="100" cy="110" r="70" fill="none" stroke="#38bdf8" stroke-width="35" stroke-dasharray="154 264" stroke-dashoffset="0" transform="rotate(-90 100 110)"/>\n'
            '<circle cx="100" cy="110" r="70" fill="none" stroke="#818cf8" stroke-width="35" stroke-dasharray="88 330" stroke-dashoffset="-154" transform="rotate(-90 100 110)"/>\n'
            '<circle cx="100" cy="110" r="70" fill="none" stroke="#34d399" stroke-width="35" stroke-dasharray="66 352" stroke-dashoffset="-242" transform="rotate(-90 100 110)"/>\n'
            '<circle cx="100" cy="110" r="70" fill="none" stroke="#fbbf24" stroke-width="35" stroke-dasharray="44 374" stroke-dashoffset="-308" transform="rotate(-90 100 110)"/>\n'
            '<rect x="190" y="70" width="12" height="12" fill="#38bdf8" rx="2"/><text x="208" y="81" fill="#94a3b8" font-size="11">35%</text>\n'
            '<rect x="190" y="90" width="12" height="12" fill="#818cf8" rx="2"/><text x="208" y="101" fill="#94a3b8" font-size="11">20%</text>\n'
            '<rect x="190" y="110" width="12" height="12" fill="#34d399" rx="2"/><text x="208" y="121" fill="#94a3b8" font-size="11">15%</text>\n'
            '<rect x="190" y="130" width="12" height="12" fill="#fbbf24" rx="2"/><text x="208" y="141" fill="#94a3b8" font-size="11">10%</text>\n'
            '</svg>'
        )
        return {
            "type": "chart",
            "subtype": "pie",
            "format": "svg",
            "code": svg,
            "caption": f"Répartition : {title}" if self.lang == "fr" else f"Distribution: {title}",
        }

    # ── Tableaux ─────────────────────────────────────────────────────────

    def generate_tables(self, domain: str, title: str) -> list[dict[str, Any]]:
        """Génère des tableaux HTML."""
        tables = []

        # Tableau comparatif
        comp = self._comparison_table(domain, title)
        if comp:
            tables.append(comp)

        # Tableau de données
        data = self._data_table(domain, title)
        if data:
            tables.append(data)

        return tables

    def _comparison_table(self, domain: str, title: str) -> dict[str, Any]:
        """Tableau comparatif HTML."""
        headers_fr = ["Critère", "Concept A", "Concept B", "Différence"]
        headers_en = ["Criterion", "Concept A", "Concept B", "Difference"]
        headers = headers_fr if self.lang == "fr" else headers_en

        rows_fr = [
            ["Définition", "Description A", "Description B", "Clé"],
            ["Application", "Usage A", "Usage B", "Contexte"],
            ["Avantages", "➕ Points forts A", "➕ Points forts B", "Comparaison"],
            ["Limites", "⚠️ Limite A", "⚠️ Limite B", "Attention"],
        ]
        rows_en = [
            ["Definition", "Description A", "Description B", "Key difference"],
            ["Application", "Usage A", "Usage B", "Context"],
            ["Advantages", "➕ Strength A", "➕ Strength B", "Comparison"],
            ["Limitations", "⚠️ Limit A", "⚠️ Limit B", "Note"],
        ]
        rows = rows_fr if self.lang == "fr" else rows_en

        html = '<table style="width:100%;border-collapse:collapse;color:#f1f5f9;font-size:0.9rem">\n'
        html += '<thead><tr style="background:#334155">'
        for h in headers:
            html += f'<th style="padding:10px;text-align:left;border-bottom:2px solid #38bdf8">{h}</th>'
        html += '</tr></thead>\n<tbody>'
        for i, row in enumerate(rows):
            bg = "#1e293b" if i % 2 == 0 else "#0f172a"
            html += f'<tr style="background:{bg}">'
            for cell in row:
                html += f'<td style="padding:8px;border-bottom:1px solid #334155">{cell}</td>'
            html += '</tr>\n'
        html += '</tbody></table>'

        return {
            "type": "table",
            "subtype": "comparison",
            "format": "html",
            "code": html,
            "caption": f"Tableau comparatif : {title}" if self.lang == "fr" else f"Comparison Table: {title}",
        }

    def _data_table(self, domain: str, title: str) -> dict[str, Any]:
        """Tableau de données HTML."""
        headers_fr = ["Élément", "Valeur", "Unité", "Notes"]
        headers_en = ["Element", "Value", "Unit", "Notes"]
        headers = headers_fr if self.lang == "fr" else headers_en

        rows_fr = [
            ["Donnée 1", "42", "unités", "Mesuré en 2024"],
            ["Donnée 2", "3.14", "π", "Constante"],
            ["Donnée 3", "299 792", "km/s", "Vitesse lumière"],
            ["Donnée 4", "9.81", "m/s²", "Gravité Terre"],
        ]
        rows_en = [
            ["Data 1", "42", "units", "Measured 2024"],
            ["Data 2", "3.14", "π", "Constant"],
            ["Data 3", "299,792", "km/s", "Speed of light"],
            ["Data 4", "9.81", "m/s²", "Earth gravity"],
        ]
        rows = rows_fr if self.lang == "fr" else rows_en

        html = '<table style="width:100%;border-collapse:collapse;color:#f1f5f9;font-size:0.9rem">\n'
        html += '<thead><tr style="background:#334155">'
        for h in headers:
            html += f'<th style="padding:10px;text-align:left;border-bottom:2px solid #818cf8">{h}</th>'
        html += '</tr></thead>\n<tbody>'
        for i, row in enumerate(rows):
            bg = "#1e293b" if i % 2 == 0 else "#0f172a"
            html += f'<tr style="background:{bg}">'
            for j, cell in enumerate(row):
                style = 'font-weight:700;color:#38bdf8' if j == 1 else ''
                html += f'<td style="padding:8px;border-bottom:1px solid #334155;{style}">{cell}</td>'
            html += '</tr>\n'
        html += '</tbody></table>'

        return {
            "type": "table",
            "subtype": "data",
            "format": "html",
            "code": html,
            "caption": f"Données : {title}" if self.lang == "fr" else f"Data: {title}",
        }

    # ── Équations mathématiques ──────────────────────────────────────────

    def generate_math(self, domain: str, title: str) -> list[dict[str, Any]]:
        """Génère des équations LaTeX."""
        equations = []

        if "algebra" in domain:
            equations.extend([
                {"type": "math", "format": "latex", "code": r"ax^2 + bx + c = 0 \implies x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}",
                 "caption": "Formule quadratique"},
                {"type": "math", "format": "latex", "code": r"(a+b)^2 = a^2 + 2ab + b^2",
                 "caption": "Identité remarquable"},
            ])
        elif "calculus" in domain:
            equations.extend([
                {"type": "math", "format": "latex", "code": r"\frac{d}{dx}x^n = nx^{n-1}",
                 "caption": "Dérivée de xⁿ"},
                {"type": "math", "format": "latex", "code": r"\int x^n dx = \frac{x^{n+1}}{n+1} + C",
                 "caption": "Intégrale de xⁿ"},
            ])
        elif "geometry" in domain:
            equations.extend([
                {"type": "math", "format": "latex", "code": r"a^2 + b^2 = c^2",
                 "caption": "Théorème de Pythagore"},
                {"type": "math", "format": "latex", "code": r"A = \pi r^2",
                 "caption": "Aire du cercle"},
            ])
        elif "physics" in domain:
            equations.extend([
                {"type": "math", "format": "latex", "code": r"F = ma",
                 "caption": "Deuxième loi de Newton"},
                {"type": "math", "format": "latex", "code": r"E = mc^2",
                 "caption": "Équivalence masse-énergie"},
            ])
        elif "statistics" in domain or "probability" in domain:
            equations.extend([
                {"type": "math", "format": "latex", "code": r"P(A|B) = \frac{P(B|A)P(A)}{P(B)}",
                 "caption": "Théorème de Bayes"},
                {"type": "math", "format": "latex", "code": r"\sigma = \sqrt{\frac{1}{N}\sum_{i=1}^N (x_i - \mu)^2}",
                 "caption": "Écart-type"},
            ])

        return equations

    # ── Cartes mentales ──────────────────────────────────────────────────

    def generate_mindmaps(self, domain: str, title: str) -> list[dict[str, Any]]:
        """Génère des cartes mentales Mermaid."""
        mindmap = (
            "mindmap\n"
            f"  root(({title}))\n"
            "    Concepts clés\n"
            "      Concept 1\n"
            "        Sous-concept A\n"
            "        Sous-concept B\n"
            "      Concept 2\n"
            "        Sous-concept C\n"
            "    Applications\n"
            "      Application 1\n"
            "      Application 2\n"
            "    À retenir\n"
            "      Point essentiel 1\n"
            "      Point essentiel 2\n"
            "      Point essentiel 3"
        )
        return [{
            "type": "mermaid",
            "subtype": "mindmap",
            "code": mindmap,
            "caption": f"Carte mentale : {title}" if self.lang == "fr" else f"Mind Map: {title}",
        }]