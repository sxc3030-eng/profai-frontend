# -*- coding: utf-8 -*-
"""Visualiseur dynamique — AI Formateur MAT-9F.

Génère des visuels À LA DEMANDE selon le contexte de l'élève.
Ne montre JAMAIS la réponse — seulement la structure, les relations,
les axes, les étapes.

Le visuel s'adapte au niveau et au blocage spécifique de l'élève.

Usage:
    from memory_agent.dynamic_visualizer import DynamicVisualizer
    dv = DynamicVisualizer(lang="fr")
    visual = dv.generate("L'élève bloque sur la factorisation de x²-9",
                         domain="algebra", grade="secondary_4")
"""

from __future__ import annotations

from typing import Any


class DynamicVisualizer:
    """Génère des visuels dynamiques adaptés au blocage de l'élève."""

    def __init__(self, lang: str = "fr") -> None:
        if lang not in ("fr", "en"):
            raise ValueError(f"Langue non supportée: {lang}")
        self.lang = lang

    # ── API publique ─────────────────────────────────────────────────────

    def generate(
        self,
        student_blockage: str,
        domain: str = "",
        grade: str = "secondary_5",
        visual_type: str = "auto",
    ) -> dict[str, Any]:
        """Génère le visuel le plus adapté au blocage de l'élève.

        Args:
            student_blockage: Description de ce qui bloque l'élève
            domain: Domaine (ex: "algebra", "physics")
            grade: Niveau scolaire
            visual_type: "auto", "diagram", "equation", "graph", "table", "flowchart", "timeline"

        Returns:
            {"type": str, "format": str, "code": str, "caption": str, "hint": str}
        """
        if visual_type == "auto":
            visual_type = self._infer_type(student_blockage, domain)

        generator = getattr(self, f"_generate_{visual_type}", self._generate_diagram)
        return generator(student_blockage, domain, grade)

    # ── Générateurs par type ─────────────────────────────────────────────

    def _generate_diagram(
        self, blockage: str, domain: str, grade: str
    ) -> dict[str, Any]:
        """Diagramme de relations — montre la structure, pas les valeurs."""
        blockage_lower = blockage.lower()

        if "factoris" in blockage_lower or "factoring" in blockage_lower:
            return {
                "type": "diagram",
                "format": "mermaid",
                "code": (
                    "graph TD\n"
                    '    A["Expression à factoriser"] --> B["Chercher un facteur commun"]\n'
                    '    A --> C["Reconnaître une identité remarquable"]\n'
                    '    B --> D["Extraire le facteur"]\n'
                    '    C --> E["a² - b² = (a-b)(a+b)"]\n'
                    '    C --> F["a² + 2ab + b² = (a+b)²"]\n'
                    '    D --> G["✅ Expression factorisée"]\n'
                    '    E --> G\n'
                    '    F --> G\n'
                    '    style A fill:#38bdf8,color:#0f172a\n'
                    '    style G fill:#34d399,color:#0f172a'
                ),
                "caption": "Méthode de factorisation" if self.lang == "fr" else "Factoring Method",
                "hint": "Quelle case correspond à TON expression ?" if self.lang == "fr" else "Which box matches YOUR expression?",
            }

        if "équation" in blockage_lower or "equation" in blockage_lower:
            return {
                "type": "diagram",
                "format": "mermaid",
                "code": (
                    "graph LR\n"
                    '    A["Équation de départ"] --> B["① Isoler le terme avec x"]\n'
                    '    B --> C["② Simplifier"]\n'
                    '    C --> D["③ Diviser par le coefficient"]\n'
                    '    D --> E["④ Vérifier en remplaçant"]\n'
                    '    E --> F["✅ Solution"]\n'
                    '    style A fill:#fbbf24,color:#0f172a\n'
                    '    style F fill:#34d399,color:#0f172a'
                ),
                "caption": "Étapes de résolution" if self.lang == "fr" else "Solution Steps",
                "hint": "À quelle étape es-tu rendu·e ?" if self.lang == "fr" else "Which step are you on?",
            }

        if "fonction" in blockage_lower or "function" in blockage_lower or "graph" in blockage_lower:
            return {
                "type": "diagram",
                "format": "mermaid",
                "code": (
                    "graph TD\n"
                    '    A["Fonction f(x)"] --> B["Tableau de valeurs"]\n'
                    '    A --> C["Forme y = mx + b"]\n'
                    '    B --> D["Placer les points"]\n'
                    '    C --> E["Ordonnée à l\'origine = b"]\n'
                    '    C --> F["Pente = m"]\n'
                    '    D --> G["Tracer la droite"]\n'
                    '    E --> G\n'
                    '    F --> G\n'
                    '    style A fill:#38bdf8,color:#0f172a\n'
                    '    style G fill:#34d399,color:#0f172a'
                ),
                "caption": "Comment tracer une fonction affine" if self.lang == "fr" else "How to Graph a Linear Function",
                "hint": "Quelle information te manque ?" if self.lang == "fr" else "What information are you missing?",
            }

        # Diagramme générique
        return {
            "type": "diagram",
            "format": "mermaid",
            "code": (
                "graph TD\n"
                '    A["Ce qu\'on sait"] --> B["Étape 1"]\n'
                '    B --> C["Étape 2"]\n'
                '    C --> D["Étape 3"]\n'
                '    D --> E["Ce qu\'on cherche"]\n'
                '    style A fill:#38bdf8,color:#0f172a\n'
                '    style E fill:#34d399,color:#0f172a'
            ),
            "caption": "Structure du problème" if self.lang == "fr" else "Problem Structure",
            "hint": "Complète les étapes dans ta tête." if self.lang == "fr" else "Fill in the steps in your mind.",
        }

    def _generate_equation(
        self, blockage: str, domain: str, grade: str
    ) -> dict[str, Any]:
        """Équation formatée — montre la structure, pas les valeurs finales."""
        blockage_lower = blockage.lower()

        if "pythagore" in blockage_lower or "pythagoras" in blockage_lower:
            return {
                "type": "equation",
                "format": "latex",
                "code": r"\text{Étape 1 : } a^2 + b^2 = c^2 \\ \text{Étape 2 : } c = \sqrt{a^2 + b^2} \\ \text{Étape 3 : Remplace } a \text{ et } b \text{ par leurs valeurs}",
                "caption": "Théorème de Pythagore — démarche" if self.lang == "fr" else "Pythagorean Theorem — Steps",
                "hint": "Remplace a et b par TES valeurs." if self.lang == "fr" else "Replace a and b with YOUR values.",
            }

        if "dérivé" in blockage_lower or "derivative" in blockage_lower:
            return {
                "type": "equation",
                "format": "latex",
                "code": r"\frac{d}{dx}[f(x)] = \lim_{h \to 0} \frac{f(x+h) - f(x)}{h} \\ \text{Règle : } \frac{d}{dx}[x^n] = nx^{n-1}",
                "caption": "Définition et règle de dérivation",
                "hint": "Quel est ton n dans xⁿ ?" if self.lang == "fr" else "What's your n in xⁿ?",
            }

        if "pourcentage" in blockage_lower or "percent" in blockage_lower:
            return {
                "type": "equation",
                "format": "latex",
                "code": r"\text{Pourcentage} = \frac{\text{Partie}}{\text{Total}} \times 100 \\ \text{Partie} = \frac{\text{Pourcentage}}{100} \times \text{Total}",
                "caption": "Formules de pourcentage" if self.lang == "fr" else "Percentage Formulas",
                "hint": "Qu'est-ce qui est la partie ? Le total ?" if self.lang == "fr" else "What's the part? The total?",
            }

        return {
            "type": "equation",
            "format": "latex",
            "code": r"\text{Formule générale} \\ \text{Étape 1 : Identifier les variables connues} \\ \text{Étape 2 : Isoler l'inconnue} \\ \text{Étape 3 : Remplacer et calculer}",
            "caption": "Démarche de résolution" if self.lang == "fr" else "Solution Approach",
            "hint": "Quelles variables connais-tu ?" if self.lang == "fr" else "Which variables do you know?",
        }

    def _generate_graph(
        self, blockage: str, domain: str, grade: str
    ) -> dict[str, Any]:
        """Graphique — montre les axes et la structure, pas les données exactes."""
        return {
            "type": "graph",
            "format": "svg",
            "code": (
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" width="100%" height="auto">\n'
                '  <!-- Axes -->\n'
                '  <line x1="50" y1="250" x2="380" y2="250" stroke="#94a3b8" stroke-width="2"/>\n'
                '  <line x1="50" y1="250" x2="50" y2="20" stroke="#94a3b8" stroke-width="2"/>\n'
                '  <!-- Flèches -->\n'
                '  <polygon points="380,250 370,245 370,255" fill="#94a3b8"/>\n'
                '  <polygon points="50,20 45,30 55,30" fill="#94a3b8"/>\n'
                '  <!-- Labels -->\n'
                f'  <text x="200" y="280" text-anchor="middle" fill="#94a3b8" font-size="12">{"x" if self.lang == "fr" else "x"}</text>\n'
                f'  <text x="20" y="140" text-anchor="middle" fill="#94a3b8" font-size="12" transform="rotate(-90 20 140)">{"y" if self.lang == "fr" else "y"}</text>\n'
                '  <!-- Zone de traçage (vide — à l\'élève de remplir) -->\n'
                '  <rect x="50" y="20" width="330" height="230" fill="none" stroke="#334155" stroke-dasharray="5,5" rx="4"/>\n'
                f'  <text x="215" y="140" text-anchor="middle" fill="#475569" font-size="14">{"À toi de tracer !" if self.lang == "fr" else "Your turn to draw!"}</text>\n'
                '</svg>'
            ),
            "caption": "Repère — à toi de placer les points" if self.lang == "fr" else "Grid — place your points",
            "hint": "Place tes points connus d'abord." if self.lang == "fr" else "Plot your known points first.",
        }

    def _generate_table(
        self, blockage: str, domain: str, grade: str
    ) -> dict[str, Any]:
        """Tableau — montre la structure, pas les valeurs."""
        headers_fr = ["Étape", "Ce que je fais", "Pourquoi", "Résultat"]
        headers_en = ["Step", "What I do", "Why", "Result"]
        headers = headers_fr if self.lang == "fr" else headers_en

        empty_rows = ""
        for i in range(1, 5):
            empty_rows += f"<tr><td>{i}</td><td>...</td><td>...</td><td>...</td></tr>\n"

        html = (
            '<table style="width:100%;border-collapse:collapse;color:#f1f5f9;font-size:0.9rem">\n'
            '<thead><tr style="background:#334155">'
            + "".join(f'<th style="padding:10px;text-align:left;border-bottom:2px solid #38bdf8">{h}</th>' for h in headers)
            + f'</tr></thead>\n<tbody>{empty_rows}</tbody>\n'
            '</table>'
        )

        return {
            "type": "table",
            "format": "html",
            "code": html,
            "caption": "Tableau de résolution — à toi de remplir" if self.lang == "fr" else "Solution Table — fill it in",
            "hint": "Remplis une ligne à la fois." if self.lang == "fr" else "Fill one row at a time.",
        }

    def _generate_flowchart(
        self, blockage: str, domain: str, grade: str
    ) -> dict[str, Any]:
        """Flowchart de raisonnement."""
        return {
            "type": "flowchart",
            "format": "mermaid",
            "code": (
                "graph TD\n"
                '    A["🧐 Je lis le problème"] --> B{"Qu\'est-ce que je cherche ?"}\n'
                '    B --> C["📋 Je note les données"]\n'
                '    C --> D{"Quelle méthode ?"}\n'
                '    D -->|"Méthode A"| E["J\'applique A"]\n'
                '    D -->|"Méthode B"| F["J\'applique B"]\n'
                '    E --> G["✅ Je vérifie"]\n'
                '    F --> G\n'
                '    style A fill:#38bdf8,color:#0f172a\n'
                '    style G fill:#34d399,color:#0f172a'
            ),
            "caption": "Cheminement de résolution" if self.lang == "fr" else "Problem-Solving Flow",
            "hint": "Quelle méthode choisis-tu ?" if self.lang == "fr" else "Which method do you choose?",
        }

    def _generate_timeline(
        self, blockage: str, domain: str, grade: str
    ) -> dict[str, Any]:
        """Frise chronologique — montre les périodes, pas les dates exactes."""
        return {
            "type": "timeline",
            "format": "mermaid",
            "code": (
                "timeline\n"
                "    title Périodes historiques\n"
                "    section Antiquité\n"
                "      Événement 1\n"
                "      Événement 2\n"
                "    section Moyen Âge\n"
                "      Événement 3\n"
                "      Événement 4\n"
                "    section Époque moderne\n"
                "      Événement 5\n"
                "      Événement 6"
            ),
            "caption": "Frise chronologique — replace les événements" if self.lang == "fr" else "Timeline — place the events",
            "hint": "Dans quelle période se situe ton événement ?" if self.lang == "fr" else "Which period does your event belong to?",
        }

    # ── Inférence ────────────────────────────────────────────────────────

    def _infer_type(self, blockage: str, domain: str) -> str:
        """Détermine le meilleur type de visuel selon le blocage."""
        bl = blockage.lower()

        if any(w in bl for w in ["factoris", "équation", "equation", "formule", "pythagore",
                                  "dérivé", "derivative", "pourcentage", "percent"]):
            return "equation"

        if any(w in bl for w in ["graph", "courbe", "fonction", "tracer", "plot"]):
            return "graph"

        if any(w in bl for w in ["étapes", "steps", "processus", "process", "méthode", "method"]):
            return "flowchart"

        if any(w in bl for w in ["compar", "tableau", "table", "données", "data"]):
            return "table"

        if any(w in bl for w in ["date", "période", "chronologie", "histoire", "history"]):
            return "timeline"

        return "diagram"