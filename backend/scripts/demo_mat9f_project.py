#!/usr/bin/env python3
"""Planifie le projet ORION avec le noyau MAT-9F, entièrement hors ligne."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from memory_agent.mat9f import (  # noqa: E402
    FUNCTION_ORDER as MAT9F_FUNCTION_ORDER,
    FunctionContext,
    MAT9FError,
    NineFunctionBlock,
    RecursiveNineFunctionEngine,
    SignalPacket,
)


PROJECT_SCHEMA = "mat-9f-project-orion-v1"
REPORT_SCHEMA = "mat-9f-project-report-v1"
INPUT_PATH = PROJECT_ROOT / "examples" / "mat9f-project-orion.json"
EXPECTED_FUNCTION_ORDER = (
    "receive",
    "identify",
    "order",
    "associate",
    "contextualize",
    "verify",
    "inhibit",
    "operate",
    "route",
)
FUNCTION_ORDER = tuple(MAT9F_FUNCTION_ORDER)
MAX_INPUT_BYTES = 1_000_000
MAX_SIGNAL_VALUE_BYTES = 100_000
MAX_EVIDENCE_ITEMS = 64
MAX_ROUTES = 81
MAX_WORK_ITEMS = 256
_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


class OrionProjectError(ValueError):
    """Le scénario ORION ou sa décision ne respecte pas le contrat local."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise OrionProjectError(f"clé JSON répétée: {key}")
        result[key] = value
    return result


def _reject_non_finite(value: str) -> None:
    raise OrionProjectError(f"nombre JSON non fini interdit: {value}")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OrionProjectError(f"{field} doit être un objet")
    return value


def _array(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise OrionProjectError(f"{field} doit être une liste")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise OrionProjectError(f"{field} doit être un texte non vide")
    return value


def _identifier(value: Any, field: str) -> str:
    result = _text(value, field)
    if not _ID_PATTERN.fullmatch(result):
        raise OrionProjectError(f"{field} doit être un identifiant MAT-9F valide")
    return result


def _integer(value: Any, field: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise OrionProjectError(f"{field} doit être un entier entre {minimum} et {maximum}")
    return value


def _unique_identifier_array(value: Any, field: str, *, maximum: int) -> list[str]:
    items = _array(value, field)
    if len(items) > maximum:
        raise OrionProjectError(f"{field} dépasse la limite de {maximum}")
    result = [
        _identifier(item, f"{field}[{index}]") for index, item in enumerate(items)
    ]
    if len(set(result)) != len(result):
        raise OrionProjectError(f"{field} contient un doublon")
    return result


def load_project(path: Path = INPUT_PATH) -> dict[str, Any]:
    """Charge l'unique scénario borné sans accepter de ressource distante."""

    resolved = path.resolve()
    if resolved != INPUT_PATH.resolve() or not resolved.is_file():
        raise OrionProjectError("le scénario ORION local attendu est introuvable")
    size = resolved.stat().st_size
    if not 0 < size <= MAX_INPUT_BYTES:
        raise OrionProjectError("le scénario ORION est vide ou trop volumineux")
    try:
        parsed = json.loads(
            resolved.read_text(encoding="utf-8", errors="strict"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise OrionProjectError("le scénario ORION n'est pas un JSON UTF-8 valide") from error
    if not isinstance(parsed, dict):
        raise OrionProjectError("le scénario ORION doit être un objet JSON")
    return parsed


def validate_project(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Valide les bornes, les références et l'ordre du projet."""

    if not isinstance(raw, Mapping):
        raise OrionProjectError("le scénario ORION doit être un objet")
    if raw.get("schema_version") != PROJECT_SCHEMA:
        raise OrionProjectError(f"schema_version doit valoir {PROJECT_SCHEMA}")
    project = _object(raw.get("project"), "project")
    constraints = _object(raw.get("constraints"), "constraints")
    evidence = _array(raw.get("evidence"), "evidence")
    routes = _array(raw.get("routes"), "routes")
    work_items = _array(raw.get("work_items"), "work_items")
    expected = _object(raw.get("expected_decision"), "expected_decision")

    project_id = _identifier(project.get("project_id"), "project.project_id")
    request_id = _identifier(project.get("request_id"), "project.request_id")
    context_id = _identifier(project.get("context_id"), "project.context_id")
    _text(project.get("objective"), "project.objective")
    if constraints.get("offline_only") is not True:
        raise OrionProjectError("ORION exige constraints.offline_only=true")
    if constraints.get("external_api_allowed") is not False:
        raise OrionProjectError("ORION interdit toute API externe")
    if constraints.get("cloud_storage_allowed") is not False:
        raise OrionProjectError("ORION interdit le stockage cloud")
    if constraints.get("evidence_required") is not True:
        raise OrionProjectError("ORION exige des preuves")
    maximum_hours = _integer(
        constraints.get("maximum_total_hours"),
        "constraints.maximum_total_hours",
        minimum=1,
        maximum=1_000,
    )
    maximum_task_hours = _integer(
        constraints.get("maximum_task_hours"),
        "constraints.maximum_task_hours",
        minimum=1,
        maximum=maximum_hours,
    )
    maximum_active_paths = _integer(
        constraints.get("maximum_active_paths"),
        "constraints.maximum_active_paths",
        minimum=1,
        maximum=9,
    )
    maximum_depth = _integer(
        constraints.get("maximum_depth"),
        "constraints.maximum_depth",
        minimum=1,
        maximum=4,
    )

    evidence_ids: set[str] = set()
    normalized_evidence: list[dict[str, Any]] = []
    if not 1 <= len(evidence) <= MAX_EVIDENCE_ITEMS:
        raise OrionProjectError(
            f"evidence doit contenir entre 1 et {MAX_EVIDENCE_ITEMS} éléments"
        )
    for index, item_value in enumerate(evidence):
        item = _object(item_value, f"evidence[{index}]")
        evidence_id = _identifier(
            item.get("evidence_id"), f"evidence[{index}].evidence_id"
        )
        if evidence_id in evidence_ids:
            raise OrionProjectError(f"preuve répétée: {evidence_id}")
        if item.get("status") != "verified":
            raise OrionProjectError(f"preuve non vérifiée: {evidence_id}")
        _text(item.get("statement"), f"evidence[{index}].statement")
        evidence_ids.add(evidence_id)
        normalized_evidence.append(dict(item))
    if not normalized_evidence:
        raise OrionProjectError("ORION exige au moins une preuve")

    route_ids: set[str] = set()
    normalized_routes: list[dict[str, Any]] = []
    if not 1 <= len(routes) <= MAX_ROUTES:
        raise OrionProjectError(f"routes doit contenir entre 1 et {MAX_ROUTES} éléments")
    for index, route_value in enumerate(routes):
        route = _object(route_value, f"routes[{index}]")
        route_id = _identifier(route.get("route_id"), f"routes[{index}].route_id")
        _text(route.get("label"), f"routes[{index}].label")
        if route_id in route_ids:
            raise OrionProjectError(f"route répétée: {route_id}")
        route_references = _unique_identifier_array(
            route.get("evidence_ids"),
            f"routes[{index}].evidence_ids",
            maximum=MAX_EVIDENCE_ITEMS,
        )
        references = set(route_references)
        unknown = sorted(references - evidence_ids)
        if unknown:
            raise OrionProjectError(f"route {route_id}: preuve inconnue {unknown[0]}")
        for field in (
            "requires_network",
            "requires_external_api",
            "keeps_documents_local",
            "supports_evidence",
        ):
            if not isinstance(route.get(field), bool):
                raise OrionProjectError(f"routes[{index}].{field} doit être booléen")
        route_ids.add(route_id)
        normalized_routes.append(dict(route))
    if not normalized_routes:
        raise OrionProjectError("ORION exige au moins une route")

    work_ids: set[str] = set()
    normalized_work: list[dict[str, Any]] = []
    planned_hours = 0
    if not 1 <= len(work_items) <= MAX_WORK_ITEMS:
        raise OrionProjectError(
            f"work_items doit contenir entre 1 et {MAX_WORK_ITEMS} éléments"
        )
    for index, work_value in enumerate(work_items):
        work = _object(work_value, f"work_items[{index}]")
        work_id = _identifier(work.get("work_id"), f"work_items[{index}].work_id")
        _text(work.get("label"), f"work_items[{index}].label")
        if work_id in work_ids:
            raise OrionProjectError(f"travail répété: {work_id}")
        order = _integer(work.get("order"), f"work_items[{index}].order", minimum=1, maximum=100)
        if order != index + 1:
            raise OrionProjectError("les travaux doivent être ordonnés de façon continue")
        hours = _integer(
            work.get("hours"),
            f"work_items[{index}].hours",
            minimum=0,
            maximum=maximum_task_hours,
        )
        dependency_values = _unique_identifier_array(
            work.get("depends_on"),
            f"work_items[{index}].depends_on",
            maximum=MAX_WORK_ITEMS,
        )
        dependencies = set(dependency_values)
        unknown_dependencies = sorted(dependencies - work_ids)
        if unknown_dependencies:
            raise OrionProjectError(
                f"travail {work_id}: dépendance absente ou postérieure {unknown_dependencies[0]}"
            )
        reference_values = _unique_identifier_array(
            work.get("evidence_ids"),
            f"work_items[{index}].evidence_ids",
            maximum=MAX_EVIDENCE_ITEMS,
        )
        references = set(reference_values)
        unknown_evidence = sorted(references - evidence_ids)
        if unknown_evidence:
            raise OrionProjectError(f"travail {work_id}: preuve inconnue {unknown_evidence[0]}")
        planned_hours += hours
        work_ids.add(work_id)
        normalized_work.append(dict(work))
    if not normalized_work or planned_hours > maximum_hours:
        raise OrionProjectError("le budget ORION est vide ou dépasse sa limite globale")

    selected_route_id = _identifier(
        expected.get("selected_route_id"), "expected_decision.selected_route_id"
    )
    rejected_route_ids = _unique_identifier_array(
        expected.get("rejected_route_ids"),
        "expected_decision.rejected_route_ids",
        maximum=MAX_ROUTES,
    )
    if selected_route_id not in route_ids or set(rejected_route_ids) != route_ids - {
        selected_route_id
    }:
        raise OrionProjectError("expected_decision ne couvre pas exactement les routes")
    if expected.get("planned_hours") != planned_hours:
        raise OrionProjectError("expected_decision.planned_hours ne correspond pas au budget")
    if expected.get("remaining_hours") != maximum_hours - planned_hours:
        raise OrionProjectError("expected_decision.remaining_hours ne correspond pas au budget")

    normalized = {
        "project": dict(project),
        "constraints": dict(constraints),
        "evidence": normalized_evidence,
        "routes": normalized_routes,
        "work_items": normalized_work,
        "expected_decision": dict(expected),
        "project_id": project_id,
        "request_id": request_id,
        "context_id": context_id,
        "evidence_ids": sorted(evidence_ids),
        "maximum_hours": maximum_hours,
        "maximum_task_hours": maximum_task_hours,
        "maximum_active_paths": maximum_active_paths,
        "maximum_depth": maximum_depth,
        "planned_hours": planned_hours,
    }
    signal_projection = {
        "project": normalized["project"],
        "constraints": normalized["constraints"],
        "evidence": normalized["evidence"],
        "routes": normalized["routes"],
        "work_items": normalized["work_items"],
        "operation": "sum_work_hours",
    }
    if len(_canonical_bytes(signal_projection)) > MAX_SIGNAL_VALUE_BYTES:
        raise OrionProjectError(
            f"le paquet 9F dépasse {MAX_SIGNAL_VALUE_BYTES} octets"
        )
    return normalized


def decide_routes(project: Mapping[str, Any]) -> dict[str, Any]:
    """Applique les contraintes explicites sans score caché ni appel externe."""

    rejected: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    for route in project["routes"]:
        reasons: list[str] = []
        if route["requires_network"] or route["requires_external_api"]:
            reasons.append("network_or_external_api_forbidden")
        if not route["keeps_documents_local"]:
            reasons.append("documents_must_remain_local")
        if not route["supports_evidence"]:
            reasons.append("evidence_support_required")
        if reasons:
            rejected.append(
                {
                    "route_id": route["route_id"],
                    "reasons": reasons,
                    "evidence_ids": list(route["evidence_ids"]),
                }
            )
        else:
            eligible.append(route)
    if len(eligible) != 1:
        raise OrionProjectError("ORION exige exactement une route admissible")
    selected = eligible[0]
    decision = {
        "selected_route": {
            "route_id": selected["route_id"],
            "label": selected["label"],
            "evidence_ids": list(selected["evidence_ids"]),
        },
        "rejected_routes": sorted(rejected, key=lambda item: item["route_id"]),
    }
    expected = project["expected_decision"]
    if decision["selected_route"]["route_id"] != expected["selected_route_id"]:
        raise OrionProjectError("la route calculée diffère de la décision attendue")
    if {item["route_id"] for item in rejected} != set(expected["rejected_route_ids"]):
        raise OrionProjectError("les routes inhibées diffèrent de la décision attendue")
    return decision


def build_budget(project: Mapping[str, Any]) -> dict[str, Any]:
    """Produit un budget entier et borné, sans estimation libre du modèle."""

    items = [
        {
            "work_id": item["work_id"],
            "order": item["order"],
            "label": item["label"],
            "hours": item["hours"],
            "depends_on": list(item["depends_on"]),
            "evidence_ids": list(item["evidence_ids"]),
        }
        for item in project["work_items"]
    ]
    planned = sum(item["hours"] for item in items)
    limit = project["maximum_hours"]
    return {
        "unit": "hours",
        "items": items,
        "maximum_task_hours": project["maximum_task_hours"],
        "planned_hours": planned,
        "limit_hours": limit,
        "remaining_hours": limit - planned,
        "within_limit": planned <= limit,
    }


def _run_engine(
    project: Mapping[str, Any],
    decision: Mapping[str, Any],
    budget: Mapping[str, Any],
) -> dict[str, Any]:
    """Active le bloc complet, puis sa propagation récursive bornée."""

    if FUNCTION_ORDER != EXPECTED_FUNCTION_ORDER:
        raise OrionProjectError("l'ordre des neuf fonctions du noyau a changé")
    signal_value = {
        "project": project["project"],
        "constraints": project["constraints"],
        "evidence": project["evidence"],
        "routes": project["routes"],
        "work_items": project["work_items"],
        "operation": "sum_work_hours",
    }
    packet = SignalPacket(
        signal_id="signal:orion:root",
        request_id=project["request_id"],
        function="receive",
        state=1,
        value=signal_value,
        strength=1.0,
        confidence=1.0,
        context_id=project["context_id"],
        path=(),
        evidence_ids=(),
        ttl=4,
        effect="excite",
    )
    context = FunctionContext(
        concept_aliases={
            project["project_id"]: "concept:assistant-documentaire-local",
        },
        associations={},
        allowed_context_ids=(project["context_id"],),
        trusted_evidence_statuses=("verified",),
        allowed_operations=("sum_work_hours",),
        activation_threshold=0.5,
    )

    block_results = NineFunctionBlock().process(packet, context)
    observed_order = tuple(result.function for result in block_results)
    if observed_order != FUNCTION_ORDER:
        raise OrionProjectError("le bloc 9F n'a pas traversé les fonctions dans l'ordre")
    by_function = {result.function: result.to_dict() for result in block_results}
    for function_name, result in by_function.items():
        if result["state"] != 1:
            raise OrionProjectError(f"la fonction {function_name} n'a pas été activée")

    inhibited = by_function["inhibit"]["packet"]["value"]["mat9f"]["inhibit"]
    rejected_ids = {
        item["route_id"] for item in inhibited.get("rejected_routes", [])
    }
    expected_rejected = {
        item["route_id"] for item in decision["rejected_routes"]
    }
    if rejected_ids != expected_rejected:
        raise OrionProjectError("l'inhibition 9F ne rejette pas les routes attendues")
    route_result = by_function["route"]["packet"]["value"]["mat9f"]["route"]
    if route_result.get("selected_route_id") != decision["selected_route"]["route_id"]:
        raise OrionProjectError("le routage 9F ne retient pas la route locale attendue")
    operation = by_function["operate"]["packet"]["value"]["mat9f"]["operate"]
    calculated_budget = operation.get("result")
    if not isinstance(calculated_budget, dict) or (
        calculated_budget.get("planned_hours") != budget["planned_hours"]
        or calculated_budget.get("remaining_hours") != budget["remaining_hours"]
        or calculated_budget.get("within_budget") is not True
    ):
        raise OrionProjectError("le budget calculé par 9F ne correspond pas au plan")

    propagation = RecursiveNineFunctionEngine(
        activation_threshold=context.activation_threshold
    ).run(
        packet,
        context,
        depth=project["maximum_depth"],
        max_active_paths=project["maximum_active_paths"],
    ).to_dict()
    if tuple(item["function"] for item in propagation["trace"][:9]) != FUNCTION_ORDER:
        raise OrionProjectError("la propagation ne commence pas par un bloc 9F complet")
    if not set(project["evidence_ids"]).issubset(propagation["evidence_ids"]):
        raise OrionProjectError("la propagation a perdu des preuves vérifiées")

    block_trace = [
        {
            "function": result["function"],
            "state": result["state"],
            "effect": result["effect"],
            "scope": result["scope"],
            "reason": result["reason"],
            "signal_id": result["packet"]["signal_id"],
            "path": result["packet"]["path"],
            "evidence_ids": result["packet"]["evidence_ids"],
            "function_output": result["packet"]["value"]["mat9f"][result["function"]],
        }
        for result in by_function.values()
    ]
    propagation_trace = [
        {
            "function": item["function"],
            "state": item["state"],
            "effect": item["effect"],
            "scope": item["scope"],
            "reason": item["reason"],
            "signal_id": item["packet"]["signal_id"],
            "path": item["packet"]["path"],
            "evidence_ids": item["packet"]["evidence_ids"],
        }
        for item in propagation.pop("trace")
    ]
    return {
        "status": "completed",
        "function_order": list(FUNCTION_ORDER),
        "block_traversal": block_trace,
        "propagation": {**propagation, "trace": propagation_trace},
    }


def build_report(
    raw: Mapping[str, Any],
    project: Mapping[str, Any],
    *,
    dry_run: bool,
) -> dict[str, Any]:
    decision = decide_routes(project)
    budget = build_budget(project)
    engine = (
        {
            "status": "not_executed",
            "function_order": list(FUNCTION_ORDER),
            "depth": project["maximum_depth"],
            "max_active_paths": project["maximum_active_paths"],
        }
        if dry_run
        else _run_engine(project, decision, budget)
    )
    decision_projection = {
        "project_id": project["project_id"],
        "request_id": project["request_id"],
        "function_order": list(FUNCTION_ORDER),
        "decision": decision,
        "budget": budget,
        "evidence_ids": project["evidence_ids"],
    }
    return {
        "schema_version": REPORT_SCHEMA,
        "mode": "dry-run" if dry_run else "executed",
        "project_id": project["project_id"],
        "request_id": project["request_id"],
        "objective": project["project"]["objective"],
        "status": "planned",
        "engine": engine,
        "decision": decision,
        "budget": budget,
        "evidence_ids": project["evidence_ids"],
        "reproducibility": {
            "input_sha256": _sha256(raw),
            "decision_sha256": _sha256(decision_projection),
            "network_used": False,
            "external_api_used": False,
        },
    }


def _encoded_report(report: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(report),
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def _write_new(path: Path, content: str) -> Path:
    output = path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    except FileExistsError as error:
        raise OrionProjectError(f"la sortie existe déjà: {output}") from error
    return output


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valide et affiche le plan sans activer le moteur ni écrire de fichier.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Écrit un nouveau rapport JSON; stdout par défaut.",
    )
    arguments = parser.parse_args(argv)
    if arguments.dry_run and arguments.output is not None:
        parser.error("--dry-run ne peut pas être combiné avec --output")
    try:
        raw = load_project()
        project = validate_project(raw)
        report = build_report(raw, project, dry_run=arguments.dry_run)
        encoded = _encoded_report(report)
        if arguments.output is None:
            sys.stdout.write(encoded)
        else:
            output = _write_new(arguments.output, encoded)
            sys.stdout.write(
                json.dumps(
                    {
                        "ok": True,
                        "output": str(output),
                        "report_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
                    },
                    ensure_ascii=False,
                    allow_nan=False,
                    sort_keys=True,
                )
                + "\n"
            )
        return 0
    except (OrionProjectError, MAT9FError) as error:
        parser.exit(2, f"erreur ORION: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
