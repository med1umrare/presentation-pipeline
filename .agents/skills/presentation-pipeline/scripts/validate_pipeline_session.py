#!/usr/bin/env python3
"""Validate presentation-pipeline-session/1.0 and optionally its artifacts."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


STAGES = (
    ("context", "context-plan-skill", "presentation-blueprint", "presentation-blueprint/1.2", "file", None),
    ("references", "references-to-visual", "visual-style-brief", "visual-style-brief/1.2", "file", None),
    ("style-kit", "presentation-style-kit", "visual-dna", "presentation-visual-dna/1.2", "directory", "visual-dna-manifest.json"),
    ("build", "branding-visual-skill", "presentation-build", "presentation-build/1.2", "directory", "build-manifest.json"),
)
VALID_STATUSES = {"pending", "active", "review", "approved", "skipped", "blocked"}
TERMINAL = {"approved", "skipped"}


def iso_datetime(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def resolve_artifact(base: Path, artifact: object, errors: list[str], label: str) -> Path | None:
    if not isinstance(artifact, dict):
        errors.append(f"{label}: artifact must be an object")
        return None
    location = artifact.get("location")
    kind = artifact.get("locationKind")
    entrypoint = artifact.get("entrypoint")
    if not isinstance(location, str) or not location.strip():
        errors.append(f"{label}: artifact.location is required")
        return None
    path = (base / location).resolve()
    if kind == "file":
        if entrypoint is not None:
            errors.append(f"{label}: file artifact entrypoint must be null")
        target = path
        if not target.is_file():
            errors.append(f"{label}: artifact file does not exist: {location}")
            return None
    elif kind == "directory":
        if not path.is_dir():
            errors.append(f"{label}: artifact directory does not exist: {location}")
            return None
        if not isinstance(entrypoint, str) or not entrypoint.strip():
            errors.append(f"{label}: directory artifact requires entrypoint")
            return None
        target = (path / entrypoint).resolve()
        if path not in target.parents or not target.is_file():
            errors.append(f"{label}: entrypoint does not exist inside artifact directory")
            return None
    else:
        errors.append(f"{label}: locationKind must be file or directory")
        return None
    declared = artifact.get("sha256")
    if not isinstance(declared, str) or not re.fullmatch(r"[0-9a-f]{64}", declared):
        errors.append(f"{label}: lowercase SHA-256 is required")
    elif hashlib.sha256(target.read_bytes()).hexdigest() != declared:
        errors.append(f"{label}: SHA-256 does not match")
    return path


def run_deep_validator(skills_root: Path, stage_id: str, path: Path, *, references_pipeline: bool = True) -> tuple[bool, str]:
    scripts = {
        "context": skills_root / "context-plan-skill/scripts/validate_presentation_blueprint.py",
        "references": skills_root / "references-to-visual/scripts/validate_visual_style_brief.py",
        "style-kit": skills_root / "presentation-style-kit/scripts/validate_visual_dna.py",
        "build": skills_root / "branding-visual-skill/scripts/validate_presentation_build.py",
    }
    script = scripts[stage_id]
    if not script.is_file():
        return False, f"missing dependency validator: {script}"
    args = [sys.executable, str(script), str(path)]
    if stage_id == "references" and references_pipeline:
        args.append("--pipeline")
    result = subprocess.run(args, text=True, capture_output=True)
    output = (result.stdout + result.stderr).strip()
    return result.returncode == 0, output


def main() -> int:
    args = [arg for arg in sys.argv[1:] if arg != "--deep"]
    deep = "--deep" in sys.argv[1:]
    if len(args) != 1:
        print("Usage: validate_pipeline_session.py <presentation-pipeline-session.json> [--deep]")
        return 2
    session_path = Path(args[0]).resolve()
    base = session_path.parent
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(session_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: Cannot read valid session JSON: {exc}")
        return 1
    if not isinstance(data, dict):
        print("ERROR: Session must be a JSON object")
        return 1
    expected_header = {
        "artifactType": "presentation-pipeline-session",
        "contract": "presentation-pipeline-session/1.0",
        "schemaVersion": "1.0",
    }
    for key, value in expected_header.items():
        if data.get(key) != value:
            errors.append(f"{key} must be {value!r}")
    if not isinstance(data.get("sessionId"), str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}", data["sessionId"]):
        errors.append("sessionId is invalid")
    if not isinstance(data.get("projectRoot"), str) or not data["projectRoot"].strip():
        errors.append("projectRoot is required")
    for key in ("createdAt", "updatedAt"):
        if not iso_datetime(data.get(key)):
            errors.append(f"{key} must be an ISO date-time")
    if data.get("lastValidatedAt") is not None and not iso_datetime(data.get("lastValidatedAt")):
        errors.append("lastValidatedAt must be null or an ISO date-time")
    if data.get("status") not in {"active", "paused", "blocked", "completed"}:
        errors.append("invalid session status")
    if data.get("interactionMode") not in {"question-answer", "accelerated"}:
        errors.append("interactionMode must be question-answer or accelerated")

    stages = data.get("stages")
    if not isinstance(stages, list) or len(stages) != 4:
        errors.append("stages must contain exactly four entries")
        stages = []
    active_like: list[str] = []
    canonical_paths: dict[str, Path] = {}
    for index, expected in enumerate(STAGES):
        if index >= len(stages):
            break
        stage = stages[index]
        stage_id, skill, artifact_type, contract, kind, entrypoint = expected
        if not isinstance(stage, dict):
            errors.append(f"stage {index + 1} must be an object")
            continue
        if stage.get("id") != stage_id or stage.get("order") != index + 1 or stage.get("skill") != skill:
            errors.append(f"stage {index + 1} identity/order/skill mismatch")
        status = stage.get("status")
        if status not in VALID_STATUSES:
            errors.append(f"{stage_id}: invalid status")
            continue
        if status in {"active", "review", "blocked"}:
            active_like.append(stage_id)
        if index > 0 and status != "pending":
            prior = [item.get("status") for item in stages[:index] if isinstance(item, dict)]
            if any(item not in TERMINAL for item in prior):
                errors.append(f"{stage_id}: cannot start before all previous stages are approved or skipped")
        artifact = stage.get("artifact")
        if status == "approved" and not isinstance(artifact, dict):
            errors.append(f"{stage_id}: approved stage requires artifact")
        if isinstance(artifact, dict):
            if artifact.get("artifactType") != artifact_type or artifact.get("contract") != contract or artifact.get("schemaVersion") != "1.2":
                errors.append(f"{stage_id}: artifact contract mismatch")
            if artifact.get("locationKind") != kind or artifact.get("entrypoint") != entrypoint:
                errors.append(f"{stage_id}: artifact location contract mismatch")
            if status == "approved" and artifact.get("status") != "approved":
                errors.append(f"{stage_id}: approved stage requires approved artifact")
            resolved = resolve_artifact(base, artifact, errors, stage_id)
            if resolved is not None:
                canonical_paths[stage_id] = resolved
        skip = stage.get("skip")
        if isinstance(skip, dict):
            if not iso_datetime(skip.get("requestedAt")):
                errors.append(f"{stage_id}: skip.requestedAt must be an ISO date-time")
            if not isinstance(skip.get("reason"), str) or not skip["reason"].strip():
                errors.append(f"{stage_id}: skip.reason is required")
            if not isinstance(skip.get("consequences"), list) or not skip["consequences"]:
                errors.append(f"{stage_id}: skip consequences are required")
            if not isinstance(skip.get("confirmationQuestion"), str) or not skip["confirmationQuestion"].strip():
                errors.append(f"{stage_id}: skip.confirmationQuestion is required")
            if not isinstance(skip.get("confirmed"), bool):
                errors.append(f"{stage_id}: skip.confirmed must be boolean")
        if status == "skipped":
            if not isinstance(skip, dict):
                errors.append(f"{stage_id}: skipped stage requires skip record")
            else:
                if skip.get("confirmed") is not True or not skip.get("confirmedBy") or not iso_datetime(skip.get("confirmedAt")):
                    errors.append(f"{stage_id}: skip is not explicitly confirmed")
                replacement = skip.get("replacementArtifact")
                if replacement is not None:
                    resolve_artifact(base, replacement, errors, f"{stage_id}.replacementArtifact")
        elif isinstance(skip, dict) and skip.get("confirmed") is True:
            errors.append(f"{stage_id}: confirmed skip must set stage status to skipped")
        if status in TERMINAL and not iso_datetime(stage.get("completedAt")):
            errors.append(f"{stage_id}: terminal stage requires completedAt")
    if len(active_like) > 1:
        errors.append(f"only one stage can be active/review/blocked: {active_like}")

    nonterminal = [item.get("id") for item in stages if isinstance(item, dict) and item.get("status") not in TERMINAL]
    current = data.get("currentStage")
    if data.get("status") == "completed":
        if current != "complete" or nonterminal:
            errors.append("completed session requires currentStage=complete and all stages terminal")
    elif stages:
        expected_current = nonterminal[0] if nonterminal else "complete"
        if current != expected_current:
            errors.append(f"currentStage must be {expected_current!r}")

    question = data.get("pendingQuestion")
    decisions = data.get("decisions")
    if not isinstance(decisions, list):
        errors.append("decisions must be an array")
        decisions = []
    question_ids = set()
    decision_ids = set()
    for decision in decisions:
        if not isinstance(decision, dict):
            errors.append("each decision must be an object")
            continue
        decision_id = decision.get("decisionId")
        if not isinstance(decision_id, str) or not re.fullmatch(r"decision-[a-z0-9-]+", decision_id):
            errors.append("decisionId is invalid")
        if decision_id in decision_ids:
            errors.append(f"duplicate decisionId: {decision_id}")
        decision_ids.add(decision_id)
        question_ids.add(decision.get("questionId"))
        if not isinstance(decision.get("questionId"), str) or not re.fullmatch(r"question-[a-z0-9-]+", decision["questionId"]):
            errors.append(f"{decision_id}: questionId is invalid")
        if not isinstance(decision.get("answer"), str) or not decision["answer"].strip():
            errors.append(f"{decision_id}: answer is required")
        if not iso_datetime(decision.get("recordedAt")):
            errors.append(f"{decision_id}: recordedAt must be an ISO date-time")
    if question is not None:
        if not isinstance(question, dict):
            errors.append("pendingQuestion must be null or an object")
        else:
            if not isinstance(question.get("questionId"), str) or not re.fullmatch(r"question-[a-z0-9-]+", question["questionId"]):
                errors.append("pendingQuestion.questionId is invalid")
            if question.get("stageId") != current:
                errors.append("pendingQuestion must belong to currentStage")
            if question.get("kind") not in {"intake", "choice", "verification", "approval", "skip-request", "skip-confirmation", "resume"}:
                errors.append("pendingQuestion.kind is invalid")
            if not isinstance(question.get("text"), str) or not question["text"].strip():
                errors.append("pendingQuestion.text is required")
            if question.get("questionId") in question_ids:
                errors.append("pendingQuestion already has a recorded decision")
            if not iso_datetime(question.get("askedAt")):
                errors.append("pendingQuestion.askedAt must be an ISO date-time")

    if deep and not errors:
        skills_root = Path(__file__).resolve().parents[2]
        context_stage = next(item for item in stages if item.get("id") == "context")
        context_skip = context_stage.get("skip") if isinstance(context_stage, dict) else None
        references_pipeline = context_stage.get("status") == "approved" or (
            isinstance(context_skip, dict) and isinstance(context_skip.get("replacementArtifact"), dict)
            and context_skip["replacementArtifact"].get("contract") == "presentation-blueprint/1.2"
        )
        for stage_id, path in canonical_paths.items():
            stage = next(item for item in stages if item.get("id") == stage_id)
            if stage.get("status") not in {"review", "approved"}:
                continue
            ok, output = run_deep_validator(skills_root, stage_id, path, references_pipeline=references_pipeline)
            if not ok:
                errors.append(f"{stage_id}: deep validation failed\n{output}")
            elif output:
                warnings.append(f"{stage_id}: {output}")

    for warning in warnings:
        print(f"CHECK: {warning}")
    if errors:
        print("\n".join(f"ERROR: {item}" for item in errors))
        return 1
    print("Presentation pipeline session is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
