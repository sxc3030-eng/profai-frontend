"""Owner-controlled improvement inbox for Nexus, experts, and MATmem.

The control plane is intentionally separate from inference.  Supervisors send
metadata-only signals, Nexus groups repeated failures, and the owner receives
actionable proposals.  An approval authorizes preparation of an isolated
candidate; it never edits, trains, promotes, or deploys anything by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import threading
from typing import Any, Mapping
from uuid import uuid4

from .continuous_improvement import (
    AppendOnlyHistory,
    ImprovementRecordError,
    sanitize,
)


CONTROL_SCHEMA = "mat9f-improvement-control-v1"
PROPOSAL_SCHEMA = "mat9f-improvement-proposal-v1"
MEMORY_ASSIGNMENT_SCHEMA = "mat9f-memory-assignment-v1"

_SOURCES = frozenset(
    {
        "nexus",
        "expert_supervisor",
        "memory_supervisor",
        "llm_monitor",
        "system_monitor",
    }
)
_SEVERITIES = frozenset({"info", "warning", "high", "critical"})
_DECISIONS = frozenset({"approve", "reject", "comment"})
_OPEN_STATUSES = frozenset({"PENDING_OWNER", "APPROVED_FOR_PREPARATION"})
_FORBIDDEN_SIGNAL_KEYS = frozenset(
    {
        "answer",
        "canonical_output",
        "expected_answer",
        "oracle",
        "prompt",
        "question",
        "raw_answer",
        "raw_prompt",
        "raw_question",
        "sealed_answer",
        "verified_answer",
    }
)
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _bounded_text(value: Any, *, label: str, maximum: int = 500) -> str:
    text = str(value or "").strip()
    if not text:
        raise ImprovementRecordError(f"{label} is required")
    if len(text) > maximum:
        raise ImprovementRecordError(f"{label} exceeds {maximum} characters")
    return text


def _validate_metadata(value: Mapping[str, Any]) -> dict[str, Any]:
    """Reject answer-bearing fields and return a sanitized JSON-safe copy."""

    def walk(item: Any, path: tuple[str, ...] = ()) -> None:
        if isinstance(item, Mapping):
            for raw_key, child in item.items():
                key = str(raw_key).casefold().replace("-", "_")
                if key in _FORBIDDEN_SIGNAL_KEYS:
                    dotted = ".".join((*path, key))
                    raise ImprovementRecordError(
                        f"answer-bearing supervisor metadata is forbidden: {dotted}"
                    )
                walk(child, (*path, key))
        elif isinstance(item, (list, tuple)):
            for child in item:
                walk(child, path)

    walk(value)
    safe = sanitize(value)
    try:
        encoded = json.dumps(safe, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ImprovementRecordError("metadata must be JSON-safe") from exc
    if len(encoded.encode("utf-8")) > 16_384:
        raise ImprovementRecordError("supervisor metadata is too large")
    return dict(safe)


@dataclass(frozen=True, slots=True)
class SupervisorSignal:
    """One metadata-only observation emitted by Nexus or a supervisor."""

    source: str
    supervisor_id: str
    component: str
    family: str
    severity: str
    request_sha256: str
    summary: str
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.source not in _SOURCES:
            raise ImprovementRecordError("unknown supervisor source")
        if self.severity not in _SEVERITIES:
            raise ImprovementRecordError("unknown supervisor severity")
        for label, value in (
            ("supervisor_id", self.supervisor_id),
            ("component", self.component),
            ("family", self.family),
        ):
            if not _IDENTIFIER.fullmatch(value):
                raise ImprovementRecordError(f"invalid {label}")
        if not _SHA256.fullmatch(self.request_sha256):
            raise ImprovementRecordError("request_sha256 must be a lowercase SHA-256")
        _bounded_text(self.summary, label="summary", maximum=500)
        _validate_metadata(self.metadata)

    @property
    def fingerprint(self) -> str:
        return _digest_text(
            "|".join((self.source, self.component, self.family, self.severity))
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "mat9f-supervisor-signal-v1",
            "source": self.source,
            "supervisor_id": self.supervisor_id,
            "component": self.component,
            "family": self.family,
            "severity": self.severity,
            "request_sha256": self.request_sha256,
            "summary": _bounded_text(self.summary, label="summary", maximum=500),
            "metadata": _validate_metadata(self.metadata),
            "fingerprint": self.fingerprint,
            "contains_raw_prompt": False,
            "contains_answer_or_oracle": False,
        }


class MemoryNeedPolicy:
    """Assign the smallest useful memory surface without writing to it."""

    _HIGH_STAKES = frozenset(
        {"medical", "legal", "finance", "security", "privacy", "compliance"}
    )

    @classmethod
    def assign(
        cls,
        *,
        expert_id: str,
        domain: str,
        need: str,
        verified: bool,
        reusable: bool,
        contains_private_data: bool = False,
        benchmark_or_sealed: bool = False,
    ) -> dict[str, Any]:
        expert_id = _bounded_text(expert_id, label="expert_id", maximum=128)
        domain = _bounded_text(domain, label="domain", maximum=80).casefold()
        need = _bounded_text(need, label="need", maximum=80).casefold()

        if benchmark_or_sealed:
            selected, space, reason, top_k, budget = (
                False,
                "none",
                "benchmark_and_sealed_material_is_never_memory_training_data",
                0,
                0,
            )
        elif need in {"none", "deterministic_proof", "transient_error"}:
            selected, space, reason, top_k, budget = (
                False,
                "none",
                "memory_would_add_latency_without_useful_evidence",
                0,
                0,
            )
        elif domain in cls._HIGH_STAKES:
            selected, space, reason, top_k, budget = (
                True,
                f"reference-curated:{domain}",
                "high_stakes_domain_requires_curated_time_bounded_evidence",
                8,
                12_000,
            )
        elif reusable and verified and not contains_private_data:
            selected, space, reason, top_k, budget = (
                True,
                f"shared-procedural:{domain}",
                "verified_reusable_method_can_be_shared_with_related_experts",
                6,
                8_000,
            )
        else:
            selected, space, reason, top_k, budget = (
                True,
                f"expert-private:{expert_id}",
                "context_is_scoped_to_the_expert_that_needs_it",
                4,
                5_000,
            )

        return {
            "schema_version": MEMORY_ASSIGNMENT_SCHEMA,
            "expert_id": expert_id,
            "domain": domain,
            "need": need,
            "selected": selected,
            "space": space,
            "access": "read_only" if selected else "none",
            "retrieval_top_k": top_k,
            "character_budget": budget,
            "reason": reason,
            "persistent_write_allowed": False,
            "write_candidate_requires_verification": True,
            "owner_approval_required_for_policy_change": True,
            "automatic_learning": False,
        }


class ImprovementInbox:
    """Tamper-evident proposal inbox controlled by the local owner."""

    def __init__(self, history_path: Path) -> None:
        self.history = AppendOnlyHistory(Path(history_path))
        self._lock = threading.RLock()

    def _events(self) -> list[dict[str, Any]]:
        return self.history.read_verified()

    @staticmethod
    def _proposal_states(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        states: dict[str, dict[str, Any]] = {}
        ordered: list[str] = []
        for sequence, event in enumerate(events, start=1):
            payload = event.get("payload", {})
            kind = event.get("kind")
            proposal_id = str(payload.get("proposal_id", ""))
            if kind == "proposal_created" and proposal_id:
                state = dict(payload)
                state["sequence"] = sequence
                state["updated_sequence"] = sequence
                state.setdefault("status", "PENDING_OWNER")
                state.setdefault("comments", [])
                states[proposal_id] = state
                ordered.append(proposal_id)
            elif proposal_id in states and kind == "proposal_evidence_added":
                state = states[proposal_id]
                hashes = list(state.get("evidence_event_hashes", []))
                evidence_hash = payload.get("evidence_event_hash")
                if evidence_hash and evidence_hash not in hashes:
                    hashes.append(evidence_hash)
                state["evidence_event_hashes"] = hashes
                state["occurrences"] = len(hashes)
                state["updated_sequence"] = sequence
            elif proposal_id in states and kind == "owner_comment":
                states[proposal_id].setdefault("comments", []).append(
                    {
                        "actor": payload.get("actor"),
                        "comment": payload.get("comment"),
                        "recorded_at": event.get("recorded_at"),
                    }
                )
                states[proposal_id]["updated_sequence"] = sequence
            elif proposal_id in states and kind == "owner_decision":
                states[proposal_id]["status"] = payload.get("status")
                states[proposal_id]["decision"] = payload.get("decision")
                states[proposal_id]["decided_by"] = payload.get("actor")
                states[proposal_id]["decision_comment"] = payload.get("comment")
                states[proposal_id]["decided_at"] = event.get("recorded_at")
                states[proposal_id]["updated_sequence"] = sequence
        return [states[proposal_id] for proposal_id in ordered]

    @staticmethod
    def _threshold(severity: str) -> int:
        return {"critical": 1, "high": 1, "warning": 2, "info": 3}[severity]

    @staticmethod
    def _recommendation(signal: SupervisorSignal) -> tuple[str, str]:
        family = signal.family.casefold()
        if "route" in family or signal.component.startswith("nexus"):
            return (
                "Auditer le routage et préparer un candidat borné",
                "prepare_isolated_router_candidate",
            )
        if signal.source == "expert_supervisor":
            return (
                "Réexaminer l’expert avec des cas frais puis préparer un correctif isolé",
                "prepare_isolated_expert_candidate",
            )
        if signal.source == "memory_supervisor":
            return (
                "Réviser l’affectation mémoire sans écrire de nouveaux souvenirs",
                "prepare_memory_policy_candidate",
            )
        return (
            "Lancer un audit ciblé puis préparer un correctif isolé",
            "prepare_isolated_component_candidate",
        )

    def submit_signal(self, signal: SupervisorSignal) -> dict[str, Any]:
        """Record a signal and create/update one deduplicated owner proposal."""

        with self._lock:
            signal_event = self.history.append(
                component=signal.component,
                component_version=CONTROL_SCHEMA,
                kind="supervisor_signal",
                payload=signal.to_payload(),
            )
            events = self._events()
            proposals = self._proposal_states(events)
            matching = [
                proposal
                for proposal in proposals
                if proposal.get("fingerprint") == signal.fingerprint
            ]
            existing = matching[-1] if matching else None
            if existing is not None:
                if existing.get("status") == "PENDING_OWNER":
                    self.history.append(
                        component="nexus.improvement_control",
                        component_version=CONTROL_SCHEMA,
                        kind="proposal_evidence_added",
                        payload={
                            "proposal_id": existing["proposal_id"],
                            "evidence_event_hash": signal_event.event_hash,
                            "automatic_execution": False,
                        },
                    )
                    proposal = self.get(existing["proposal_id"])
                else:
                    proposal = existing
                return {
                    "signal_event_hash": signal_event.event_hash,
                    "proposal": proposal,
                    "proposal_created": False,
                }

            matching_signals = [
                event
                for event in events
                if event.get("kind") == "supervisor_signal"
                and event.get("payload", {}).get("fingerprint") == signal.fingerprint
            ]
            if len(matching_signals) < self._threshold(signal.severity):
                return {
                    "signal_event_hash": signal_event.event_hash,
                    "proposal": None,
                    "proposal_created": False,
                }

            label, requested_action = self._recommendation(signal)
            evidence = [event["event_hash"] for event in matching_signals]
            proposal_id = "proposal-" + _digest_text(
                f"{signal.fingerprint}|{evidence[0]}"
            )[:20]
            proposal_payload = {
                "schema_version": PROPOSAL_SCHEMA,
                "proposal_id": proposal_id,
                "fingerprint": signal.fingerprint,
                "title": label,
                "summary": signal.summary,
                "component": signal.component,
                "family": signal.family,
                "severity": signal.severity,
                "source": signal.source,
                "supervisor_id": signal.supervisor_id,
                "occurrences": len(evidence),
                "evidence_event_hashes": evidence,
                "requested_action": requested_action,
                "status": "PENDING_OWNER",
                "choices": ["approve", "reject", "comment"],
                "approval_effect": "authorize_isolated_preparation_only",
                "production_promotion_requires_second_approval": True,
                "automatic_execution": False,
                "automatic_training": False,
                "automatic_promotion": False,
                "sealed_exam_access": False,
                "rollback_required": True,
            }
            self.history.append(
                component="nexus.improvement_control",
                component_version=CONTROL_SCHEMA,
                kind="proposal_created",
                payload=proposal_payload,
            )
            return {
                "signal_event_hash": signal_event.event_hash,
                "proposal": self.get(proposal_id),
                "proposal_created": True,
            }

    def list(
        self,
        *,
        after_sequence: int = 0,
        include_closed: bool = True,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if after_sequence < 0 or limit < 1 or limit > 200:
            raise ImprovementRecordError("invalid proposal list bounds")
        with self._lock:
            proposals = self._proposal_states(self._events())
        if not include_closed:
            proposals = [
                proposal
                for proposal in proposals
                if proposal.get("status") in _OPEN_STATUSES
            ]
        proposals = [
            proposal
            for proposal in proposals
            if int(proposal.get("updated_sequence", 0)) > after_sequence
        ]
        return proposals[-limit:]

    def get(self, proposal_id: str) -> dict[str, Any]:
        proposal_id = _bounded_text(proposal_id, label="proposal_id", maximum=128)
        with self._lock:
            for proposal in self._proposal_states(self._events()):
                if proposal.get("proposal_id") == proposal_id:
                    return proposal
        raise ImprovementRecordError("unknown proposal_id")

    def decide(
        self,
        *,
        proposal_id: str,
        decision: str,
        actor: str,
        comment: str = "",
        decision_id: str | None = None,
    ) -> dict[str, Any]:
        decision = str(decision).casefold().strip()
        if decision not in _DECISIONS:
            raise ImprovementRecordError("decision must be approve, reject, or comment")
        actor = _bounded_text(actor, label="actor", maximum=128)
        if actor.casefold() in {"agent", "automatic", "nexus", "system"}:
            raise ImprovementRecordError("an external local owner is required")
        comment = str(comment or "").strip()
        if len(comment) > 2_000:
            raise ImprovementRecordError("comment exceeds 2000 characters")
        if decision == "comment" and not comment:
            raise ImprovementRecordError("comment text is required")
        decision_id = decision_id or f"decision-{uuid4()}"
        if not _IDENTIFIER.fullmatch(decision_id):
            raise ImprovementRecordError("invalid decision_id")

        with self._lock:
            events = self._events()
            for event in events:
                payload = event.get("payload", {})
                if payload.get("decision_id") == decision_id:
                    return self.get(proposal_id)
            proposal = self.get(proposal_id)
            if decision == "comment":
                self.history.append(
                    component="nexus.improvement_control",
                    component_version=CONTROL_SCHEMA,
                    kind="owner_comment",
                    payload={
                        "proposal_id": proposal_id,
                        "decision_id": decision_id,
                        "actor": actor,
                        "comment": comment,
                        "automatic_execution": False,
                    },
                )
            else:
                if proposal.get("status") != "PENDING_OWNER":
                    raise ImprovementRecordError("proposal is no longer awaiting a decision")
                status = (
                    "APPROVED_FOR_PREPARATION" if decision == "approve" else "REJECTED"
                )
                self.history.append(
                    component="nexus.improvement_control",
                    component_version=CONTROL_SCHEMA,
                    kind="owner_decision",
                    payload={
                        "proposal_id": proposal_id,
                        "decision_id": decision_id,
                        "decision": decision,
                        "status": status,
                        "actor": actor,
                        "comment": comment,
                        "effect": (
                            "isolated_candidate_preparation_authorized"
                            if decision == "approve"
                            else "proposal_closed_without_change"
                        ),
                        "production_files_changed": False,
                        "model_training_started": False,
                        "automatic_execution": False,
                    },
                )
            return self.get(proposal_id)

    def record_memory_assignment(self, assignment: Mapping[str, Any]) -> str:
        if assignment.get("schema_version") != MEMORY_ASSIGNMENT_SCHEMA:
            raise ImprovementRecordError("invalid memory assignment schema")
        with self._lock:
            event = self.history.append(
                component="matmem.assignment_policy",
                component_version=CONTROL_SCHEMA,
                kind="memory_assignment",
                payload=_validate_metadata(assignment),
            )
        return event.event_hash

    def health(self) -> dict[str, Any]:
        with self._lock:
            events = self._events()
            proposals = self._proposal_states(events)
        status_counts: dict[str, int] = {}
        for proposal in proposals:
            status = str(proposal.get("status", "UNKNOWN"))
            status_counts[status] = status_counts.get(status, 0) + 1
        return {
            "schema_version": CONTROL_SCHEMA,
            "ready": True,
            "event_count": len(events),
            "signal_count": sum(event.get("kind") == "supervisor_signal" for event in events),
            "proposal_count": len(proposals),
            "proposal_status": status_counts,
            "history_verified": True,
            "automatic_mutation": False,
            "automatic_training": False,
            "automatic_promotion": False,
            "owner_decision_required": True,
        }


class NexusImprovementCoordinator:
    """Small integration surface shared by Nexus, expert supervisors and UI."""

    def __init__(self, history_path: Path) -> None:
        self.inbox = ImprovementInbox(history_path)

    @staticmethod
    def request_hash(request_id: str) -> str:
        return _digest_text(_bounded_text(request_id, label="request_id", maximum=256))

    def report(
        self,
        *,
        source: str,
        supervisor_id: str,
        component: str,
        family: str,
        severity: str,
        request_id: str,
        summary: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        signal = SupervisorSignal(
            source=source,
            supervisor_id=supervisor_id,
            component=component,
            family=family,
            severity=severity,
            request_sha256=self.request_hash(request_id),
            summary=summary,
            metadata=dict(metadata or {}),
        )
        return self.inbox.submit_signal(signal)

    def assign_memory(self, **request: Any) -> dict[str, Any]:
        assignment = MemoryNeedPolicy.assign(**request)
        assignment["assignment_event_hash"] = self.inbox.record_memory_assignment(
            assignment
        )
        return assignment

    def health(self) -> dict[str, Any]:
        return self.inbox.health()


def default_owner_name() -> str:
    value = os.environ.get("USERNAME") or os.environ.get("USER") or "local-owner"
    value = re.sub(r"[^A-Za-z0-9._:-]", "-", value.strip())[:128]
    if not value or value.casefold() in {"agent", "automatic", "nexus", "system"}:
        return "local-owner"
    return value


__all__ = [
    "CONTROL_SCHEMA",
    "ImprovementInbox",
    "MEMORY_ASSIGNMENT_SCHEMA",
    "MemoryNeedPolicy",
    "NexusImprovementCoordinator",
    "PROPOSAL_SCHEMA",
    "SupervisorSignal",
    "default_owner_name",
]
