"""Label-free dispatch by trial, ordered by cost. A cascade, not a router.

Nothing here modifies the runners that currently work. It is a separate path,
built so it can be measured against them before anything is switched over.

Why not a router
----------------
Every routing decision in this repository is a lookup keyed by benchmark task
name: `TASK_CONTRACTS[task]["route"]` in the HF runners, and
`public_metadata["family"]` read straight from the corpus in the four-arm
campaign. Neither predicts anything, and neither can exist in production, where
a question arrives with no `task` field and no `family` label.

The attempt at a real predictive router is already recorded as a failure:
calibration announced 48% on `ratio_share` and the sealed run delivered 8%.
Prediction was tried and it did not transfer.

Measured here instead, over 400 questions with the label gate removed
(`tests/test_nexus_trial_cascade.py::FalseFireTests`):

    arithmetic expert  fires 100/100 on its own task,  0 on the other three
    calendar expert    fires  26/100 on its own task,  0 on the other three
    ------------------------------------------------------------------
    false fires                                        0

The experts already refuse on content alone. A deterministic trial costs
microseconds and a refusal costs nothing, so asking every expert is strictly
cheaper than being wrong about which one to ask. The label was never carrying
information the experts did not already have.

Cost ordering
-------------
    1. deterministic experts   ~microseconds, refusal free
    2. memory retrieval        ~milliseconds, I/O, fail-closed on grounding
    3. the language model      ~seconds

Each stage only sees what the stage above it refused, so the filtering is
produced by the cascade itself and no classifier is needed anywhere.

The floor
---------
Stage 3 forwards the question unmodified. A cascade that reaches it is
byte-identical to calling the model directly, which is what makes the whole
structure incapable of scoring below the naked model. That property is a test,
not an intention: `test_bypass_is_byte_identical_to_direct`.

A caution about stage 1's arbitration
-------------------------------------
Under exact-match scoring an abstention and a wrong answer both score zero, so
refusing on divergence has no upside on that metric — measured on the full BBH
date set, abstaining on all 3 solver disagreements surrendered 3 correct
answers and prevented none. Arbitration therefore prefers the higher-authority
expert when one exists, and only refuses when the competing claims are equally
authoritative. Callers that genuinely want fail-closed behaviour should report
selective accuracy (see `selective_accuracy`), which is the only framing where
an abstention is worth something.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol, Sequence


CASCADE_SCHEMA = "nexus-trial-cascade-v1"

STAGE_EXPERT = "deterministic_expert"
STAGE_MEMORY = "grounded_memory"
STAGE_DIRECT = "llm_direct_bypass"
STAGE_REFUSED = "refused"


class ExpertRefusal(ValueError):
    """The expert cannot prove an answer. The normal case, never an error."""


class CascadeError(RuntimeError):
    """A contract violation by an expert or a memory backend. Fail closed."""


@dataclass(frozen=True)
class ExpertProof:
    """What an expert must return to be believed.

    `verification` is mandatory and must be a non-empty statement of *how* the
    answer was obtained. An expert that returns an answer without one is a
    contract violation rather than a success: the v1 calendar expert reported
    `nexus_verified` while its entire proof was a hash of its own output, and it
    was wrong on 5 of the 53 questions it accepted.
    """

    expert_id: str
    answer: str
    verification: str
    authority: int = 0

    def __post_init__(self) -> None:
        if not str(self.expert_id).strip():
            raise CascadeError("expert_id is required")
        if not str(self.answer).strip():
            raise CascadeError(f"expert {self.expert_id} returned an empty answer")
        if not str(self.verification).strip():
            raise CascadeError(f"expert {self.expert_id} returned no verification")


class Expert(Protocol):
    def __call__(self, question: str, /) -> ExpertProof: ...


class Memory(Protocol):
    """Retrieval plus a fail-closed grounding decision.

    Split in two on purpose. `retrieve` may return plenty and still ground
    nothing; conflating the two is how "MATmem contributed 0" got reported for
    a memory that was never mounted. `retrieved` and `grounded` are counted
    separately in the trace so an empty index is distinguishable from a
    retrieval that simply did not support any answer.
    """

    def retrieve(self, question: str, /) -> Sequence[Mapping[str, Any]]: ...

    def propose(
        self, question: str, evidence: Sequence[Mapping[str, Any]], /
    ) -> Mapping[str, Any] | None: ...


@dataclass(frozen=True)
class CascadeResult:
    stage: str
    answer: str | None
    verified: bool
    detail: str
    trace: tuple[dict[str, Any], ...] = field(default=())

    @property
    def answered(self) -> bool:
        return self.answer is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": CASCADE_SCHEMA,
            "stage": self.stage,
            "answer": self.answer,
            "answered": self.answered,
            "verified": self.verified,
            "detail": self.detail,
            "trace": [dict(row) for row in self.trace],
        }


def attempt_experts(
    question: str, experts: Sequence[tuple[str, Expert]]
) -> dict[str, Any]:
    """Ask every expert. Refusal is free, so there is nothing to predict."""

    successes: list[ExpertProof] = []
    refusals: list[dict[str, str]] = []
    for expert_id, expert in experts:
        try:
            proof = expert(question)
        except ExpertRefusal as exc:
            refusals.append({"expert_id": expert_id, "reason": str(exc)})
            continue
        except CascadeError:
            raise
        except Exception as exc:  # an expert crash is a bug, not a refusal
            raise CascadeError(
                f"expert {expert_id} crashed: {type(exc).__name__}: {exc}"
            ) from exc
        if not isinstance(proof, ExpertProof):
            raise CascadeError(f"expert {expert_id} did not return an ExpertProof")
        successes.append(proof)

    answers = {proof.answer for proof in successes}
    if not successes:
        outcome, answer = "no_expert_applies", None
    elif len(answers) == 1:
        outcome, answer = "concordant", next(iter(answers))
    else:
        top = max(proof.authority for proof in successes)
        leaders = [proof for proof in successes if proof.authority == top]
        if len({proof.answer for proof in leaders}) == 1:
            outcome, answer = "arbitrated_by_authority", leaders[0].answer
        else:
            outcome, answer = "divergent", None

    return {
        "outcome": outcome,
        "answer": answer,
        "attempted": len(experts),
        "successes": [
            {
                "expert_id": proof.expert_id,
                "answer": proof.answer,
                "verification": proof.verification,
                "authority": proof.authority,
            }
            for proof in successes
        ],
        "refusals": refusals,
    }


def run_cascade(
    question: str,
    *,
    experts: Sequence[tuple[str, Expert]] = (),
    memory: Memory | None = None,
    llm: Callable[[str], str] | None = None,
) -> CascadeResult:
    """Try cheap proofs first; fall through to the model unchanged."""

    if not isinstance(question, str) or not question.strip():
        raise CascadeError("question must be a non-empty string")

    trace: list[dict[str, Any]] = []

    expert_stage = attempt_experts(question, experts)
    trace.append({"stage": STAGE_EXPERT, **expert_stage})
    if expert_stage["outcome"] in {"concordant", "arbitrated_by_authority"}:
        return CascadeResult(
            STAGE_EXPERT,
            str(expert_stage["answer"]),
            True,
            expert_stage["outcome"],
            tuple(trace),
        )
    if expert_stage["outcome"] == "divergent":
        # Equally authoritative experts contradicting each other is the one
        # situation where answering would mean guessing. Nothing below can
        # resolve it either, so stop rather than let a cheaper stage overrule a
        # proof-carrying disagreement.
        return CascadeResult(
            STAGE_REFUSED, None, False, "equally_authoritative_experts_disagree",
            tuple(trace),
        )

    if memory is not None:
        evidence = list(memory.retrieve(question))
        proposal = memory.propose(question, evidence) if evidence else None
        accepted = bool(proposal and proposal.get("accepted"))
        diagnostics = getattr(memory, "diagnostics", None)
        memory_diagnostics = diagnostics() if callable(diagnostics) else {}
        if not isinstance(memory_diagnostics, Mapping):
            raise CascadeError("memory diagnostics must be a mapping")
        trace.append(
            {
                "stage": STAGE_MEMORY,
                "retrieved": len(evidence),
                "grounded": accepted,
                **dict(memory_diagnostics),
                "reason": (proposal or {}).get(
                    "reason", memory_diagnostics.get("reason", "no_evidence_retrieved")
                ),
            }
        )
        if accepted:
            answer = str(proposal.get("answer", "")).strip()
            if not answer:
                raise CascadeError("memory accepted a candidate with no answer")
            return CascadeResult(
                STAGE_MEMORY, answer, True, "grounded_in_signed_evidence", tuple(trace)
            )

    if llm is None:
        return CascadeResult(
            STAGE_REFUSED, None, False, "no_stage_could_answer", tuple(trace)
        )

    # The question is forwarded exactly as received. No instruction, no
    # context, no reformatting: anything added here would make the floor of the
    # cascade something other than the naked model.
    answer = llm(question)
    trace.append({"stage": STAGE_DIRECT, "prompt_unmodified": True})
    return CascadeResult(
        STAGE_DIRECT, str(answer), False, "no_proof_available_forwarded_unchanged",
        tuple(trace),
    )


def selective_accuracy(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Coverage and accuracy-on-answered, reported separately.

    Plain exact-match scores an abstention exactly as it scores a wrong answer,
    which makes every fail-closed refusal invisible and gives a verification
    layer no way to show value. Reporting coverage alongside accuracy is what
    turns "refuses when it cannot prove" from an unmeasurable intention into a
    number.

    Each record needs `answered` (bool) and `correct` (bool).
    """

    total = len(records)
    if total == 0:
        raise CascadeError("selective accuracy needs at least one record")
    answered = [row for row in records if bool(row.get("answered"))]
    correct = sum(1 for row in answered if bool(row.get("correct")))
    wrong_while_answering = len(answered) - correct
    return {
        "n": total,
        "answered": len(answered),
        "coverage": len(answered) / total,
        "correct": correct,
        "accuracy_on_answered": (correct / len(answered)) if answered else 0.0,
        "overall_exact_match": correct / total,
        "wrong_while_answering": wrong_while_answering,
        "abstentions": total - len(answered),
    }


def stage_breakdown(results: Sequence[CascadeResult]) -> dict[str, int]:
    """How many questions each stage actually resolved.

    The number that matters for cost: questions resolved at `deterministic_expert`
    never reach the model at all.
    """

    counts = {
        STAGE_EXPERT: 0,
        STAGE_MEMORY: 0,
        STAGE_DIRECT: 0,
        STAGE_REFUSED: 0,
    }
    for result in results:
        counts[result.stage] = counts.get(result.stage, 0) + 1
    return counts


__all__ = [
    "CASCADE_SCHEMA",
    "STAGE_DIRECT",
    "STAGE_EXPERT",
    "STAGE_MEMORY",
    "STAGE_REFUSED",
    "CascadeError",
    "CascadeResult",
    "Expert",
    "ExpertProof",
    "ExpertRefusal",
    "Memory",
    "attempt_experts",
    "run_cascade",
    "selective_accuracy",
    "stage_breakdown",
]
