#!/usr/bin/env python3
"""Interroge localement Granite + adaptateur MAT-LM et imprime uniquement du JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from memory_agent.matlm_inference import (  # noqa: E402
    InferenceConfig,
    MATLMInputLimitError,
    MATLMInferenceError,
    MATLMInferenceSession,
    MATLMRequestInvalidError,
    MATLMRuntimeFatalError,
    contract_retry_eligible,
    dry_run_plan,
    inference_status,
    load_capsule_file,
)
from memory_agent.matlm_protocol import interactive_ready_frame  # noqa: E402
from memory_agent.native_llm_contract import (  # noqa: E402
    MAX_CAPSULE_BYTES,
    ContractValidationError,
    validate_capsule,
)


def _json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MATLMRequestInvalidError(f"clé JSON répétée: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise MATLMRequestInvalidError(f"nombre JSON non fini interdit: {value}")


def _stdin_capsule() -> dict[str, Any]:
    raw = sys.stdin.buffer.read(MAX_CAPSULE_BYTES + 1)
    if len(raw) > MAX_CAPSULE_BYTES:
        raise MATLMInputLimitError(
            f"capsule supérieure à {MAX_CAPSULE_BYTES} octets"
        )
    try:
        return validate_capsule(raw)
    except ContractValidationError as error:
        raise MATLMInferenceError(f"capsule native invalide: {error}") from error


def _capsule(argument: str | None) -> dict[str, Any]:
    if argument is None:
        raise MATLMInferenceError("--capsule est requis hors mode --status/--interactive")
    return _stdin_capsule() if argument == "-" else load_capsule_file(argument)


def _interactive_request(
    line: str, line_number: int
) -> tuple[dict[str, Any], str, bool]:
    if len(line.encode("utf-8")) > MAX_CAPSULE_BYTES:
        raise MATLMInputLimitError(f"ligne {line_number}: requête trop grande")
    try:
        value = json.loads(
            line,
            object_pairs_hook=_reject_duplicates,
            parse_constant=_reject_constant,
        )
    except MATLMInferenceError:
        raise
    except json.JSONDecodeError as error:
        raise MATLMRequestInvalidError(
            f"ligne {line_number}: JSON invalide"
        ) from error
    if isinstance(value, Mapping) and set(value) == {"interaction_mode", "capsule"}:
        try:
            capsule = validate_capsule(value["capsule"])
        except ContractValidationError as error:
            raise MATLMRequestInvalidError(
                f"ligne {line_number}: capsule invalide: {error}"
            ) from error
        interaction_mode = value["interaction_mode"]
        if interaction_mode not in {"general", "code"}:
            raise MATLMRequestInvalidError(
                f"ligne {line_number}: interaction_mode invalide"
            )
        return capsule, interaction_mode, False
    if isinstance(value, Mapping) and set(value) == {
        "interaction_mode",
        "contract_retry",
        "capsule",
    }:
        if value["interaction_mode"] != "general":
            raise MATLMRequestInvalidError(
                f"ligne {line_number}: contract_retry est réservé au mode general"
            )
        if value["contract_retry"] is not True:
            raise MATLMRequestInvalidError(
                f"ligne {line_number}: contract_retry doit valoir true"
            )
        try:
            capsule = validate_capsule(value["capsule"])
        except ContractValidationError as error:
            raise MATLMRequestInvalidError(
                f"ligne {line_number}: capsule invalide: {error}"
            ) from error
        if not contract_retry_eligible(capsule, "general"):
            raise MATLMRequestInvalidError(
                f"ligne {line_number}: contract_retry interdit pour cette capsule"
            )
        return capsule, "general", True
    try:
        return validate_capsule(value), "general", False
    except ContractValidationError as error:
        raise MATLMRequestInvalidError(
            f"ligne {line_number}: capsule invalide: {error}"
        ) from error


def _interactive_error_frame(
    line_number: int, error: MATLMInferenceError
) -> dict[str, Any]:
    diagnostics = getattr(error, "diagnostics", {})
    diagnostics = diagnostics if isinstance(diagnostics, Mapping) else {}
    token_count = diagnostics.get("generated_token_count")
    max_tokens_hit = diagnostics.get("max_tokens_hit")
    output_sha256 = diagnostics.get("output_sha256")
    recovery_reason = diagnostics.get("recovery_reason")
    return {
        "ok": False,
        "line": line_number,
        "error": " ".join(str(error).split())[:500],
        "error_code": str(getattr(error, "error_code", "runtime_fatal"))[:64],
        "retryable": bool(getattr(error, "retryable", False)),
        "fatal": bool(getattr(error, "fatal", False)),
        "restart_required": bool(getattr(error, "restart_required", False)),
        "diagnostics": {
            "generated_token_count": (
                token_count
                if isinstance(token_count, int)
                and not isinstance(token_count, bool)
                and token_count >= 0
                else None
            ),
            "max_tokens_hit": (
                max_tokens_hit if isinstance(max_tokens_hit, bool) else None
            ),
            "output_sha256": (
                output_sha256
                if isinstance(output_sha256, str)
                and len(output_sha256) == 64
                and all(character in "0123456789abcdef" for character in output_sha256)
                else None
            ),
            "recovery_reason": (
                recovery_reason[:128]
                if isinstance(recovery_reason, str) and recovery_reason
                else None
            ),
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", type=Path, default=None, help="Dossier PEFT local optionnel.")
    parser.add_argument("--code-adapter", type=Path, default=None, help="Adaptateur Code local.")
    parser.add_argument("--base-model", default="ibm-granite/granite-3.3-2b-instruct")
    parser.add_argument("--load-mode", choices=("auto", "qlora-nf4", "bf16"), default="auto")
    parser.add_argument("--device-index", type=int, default=0)
    parser.add_argument("--max-input-tokens", type=int, default=4096)
    parser.add_argument("--max-new-tokens", type=int, default=768)
    parser.add_argument("--seed", type=int, default=20_260_721)
    parser.add_argument(
        "--allow-model-download",
        action="store_true",
        help="Autorise explicitement Transformers à télécharger les fichiers Granite manquants.",
    )
    parser.add_argument("--capsule", help="Fichier capsule JSON; '-' lit stdin.")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--status", action="store_true", help="État sans importer la pile ML.")
    modes.add_argument("--dry-run", action="store_true", help="Valide sans charger le modèle.")
    modes.add_argument(
        "--interactive",
        action="store_true",
        help="Lit une capsule ou {question,capsule} JSON par ligne sur stdin.",
    )
    return parser


def _config(arguments: argparse.Namespace) -> InferenceConfig:
    return InferenceConfig(
        adapter_path=arguments.adapter,
        code_adapter_path=arguments.code_adapter,
        base_model=arguments.base_model,
        load_mode=arguments.load_mode,
        device_index=arguments.device_index,
        max_input_tokens=arguments.max_input_tokens,
        max_new_tokens=arguments.max_new_tokens,
        seed=arguments.seed,
        allow_model_download=arguments.allow_model_download,
    )


def _interactive(session: MATLMInferenceSession) -> int:
    # Cette trame n'est emise qu'apres l'entree dans MATLMInferenceSession,
    # donc une fois le modele et l'adaptateur effectivement charges.
    sys.stdout.write(_json(interactive_ready_frame()) + "\n")
    sys.stdout.flush()
    for line_number, line in enumerate(sys.stdin, start=1):
        if not line.strip():
            continue
        try:
            capsule, interaction_mode, contract_retry = _interactive_request(
                line, line_number
            )
        except (MATLMInferenceError, ContractValidationError) as error:
            if not isinstance(error, MATLMInferenceError):
                error = MATLMRequestInvalidError(str(error))
            sys.stdout.write(_json(_interactive_error_frame(line_number, error)) + "\n")
            sys.stdout.flush()
            continue
        try:
            answer = (
                session.ask(capsule, interaction_mode="code")
                if interaction_mode == "code"
                else (
                    session.ask(capsule, contract_retry=True)
                    if contract_retry
                    else session.ask(capsule)
                )
            )
            sys.stdout.write(_json(answer) + "\n")
            sys.stdout.flush()
        except (MATLMInferenceError, ContractValidationError) as error:
            if not isinstance(error, MATLMInferenceError):
                error = MATLMRequestInvalidError(str(error))
            sys.stdout.write(_json(_interactive_error_frame(line_number, error)) + "\n")
            sys.stdout.flush()
            if error.fatal:
                return 2
        except Exception as error:
            fatal = MATLMRuntimeFatalError(
                f"erreur d'exécution locale: {type(error).__name__}"
            )
            sys.stdout.write(_json(_interactive_error_frame(line_number, fatal)) + "\n")
            sys.stdout.flush()
            return 2
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    config = _config(arguments)
    try:
        if arguments.status:
            sys.stdout.write(_json(inference_status(config)) + "\n")
            return 0
        if arguments.interactive and arguments.capsule is not None:
            raise MATLMInferenceError("--capsule et --interactive sont incompatibles")
        if arguments.dry_run:
            sys.stdout.write(_json(dry_run_plan(config, _capsule(arguments.capsule))) + "\n")
            return 0
        capsule = None if arguments.interactive else _capsule(arguments.capsule)
        with MATLMInferenceSession(config) as session:
            if arguments.interactive:
                return _interactive(session)
            answer = session.ask(capsule)
        # stdout ne reçoit que l'objet validé, jamais la génération brute.
        sys.stdout.write(_json(answer) + "\n")
        return 0
    except (MATLMInferenceError, ContractValidationError) as error:
        sys.stderr.write(f"Erreur MAT-LM: {' '.join(str(error).split())[:1000]}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
