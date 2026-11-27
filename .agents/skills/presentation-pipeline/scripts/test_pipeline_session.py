#!/usr/bin/env python3
"""Positive and negative tests for presentation pipeline session transitions."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


NOW = "2026-01-01T10:00:00+00:00"


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(validator: Path, session: Path, success: bool) -> None:
    result = subprocess.run([sys.executable, str(validator), str(session)], text=True, capture_output=True)
    if (result.returncode == 0) != success:
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        raise AssertionError(f"Expected success={success}, got {result.returncode}")


def stage(stage_id: str, order: int, skill: str, status: str = "pending") -> dict:
    return {"id": stage_id, "order": order, "skill": skill, "status": status, "startedAt": None, "completedAt": None, "artifact": None, "skip": None}


def base_session() -> dict:
    stages = [
        stage("context", 1, "context-plan-skill", "active"),
        stage("references", 2, "references-to-visual"),
        stage("style-kit", 3, "presentation-style-kit"),
        stage("build", 4, "branding-visual-skill"),
    ]
    stages[0]["startedAt"] = NOW
    return {
        "artifactType": "presentation-pipeline-session", "contract": "presentation-pipeline-session/1.0", "schemaVersion": "1.0",
        "sessionId": "course-fixture", "createdAt": NOW, "updatedAt": NOW, "status": "active", "currentStage": "context",
        "interactionMode": "question-answer", "projectRoot": ".", "stages": stages,
        "pendingQuestion": {"questionId": "question-context-goal", "stageId": "context", "kind": "intake", "text": "Какое решение должна принять аудитория?", "why": "Это определяет тезис.", "required": True, "askedAt": NOW},
        "decisions": [], "lastValidatedAt": None,
    }


def confirmed_skip(reason: str) -> dict:
    return {
        "requestedAt": NOW, "reason": reason, "consequences": ["Артефакт этапа не будет создан"],
        "confirmationQuestion": "Подтверждаете пропуск?", "confirmed": True, "confirmedBy": "user", "confirmedAt": NOW,
        "replacementArtifact": None,
    }


def main() -> int:
    validator = Path(__file__).resolve().with_name("validate_pipeline_session.py")
    with tempfile.TemporaryDirectory(prefix="pipeline-session-") as temp:
        root = Path(temp)
        session_path = root / "presentation-pipeline-session.json"

        active = base_session()
        write(session_path, active)
        run(validator, session_path, True)

        requested = copy.deepcopy(active)
        requested["stages"][0]["skip"] = {
            "requestedAt": NOW, "reason": "Пользователь хочет начать со стиля", "consequences": ["Blueprint не будет создан"],
            "confirmationQuestion": "Подтверждаете пропуск Blueprint?", "confirmed": False, "confirmedBy": None, "confirmedAt": None,
            "replacementArtifact": None,
        }
        requested["pendingQuestion"] = {"questionId": "question-context-skip", "stageId": "context", "kind": "skip-confirmation", "text": "Подтверждаете пропуск Blueprint?", "why": "Без него смысл не проверен.", "required": True, "askedAt": NOW}
        write(session_path, requested)
        run(validator, session_path, True)

        unconfirmed = copy.deepcopy(requested)
        unconfirmed["stages"][0]["status"] = "skipped"
        unconfirmed["stages"][0]["completedAt"] = NOW
        unconfirmed["stages"][1]["status"] = "active"
        unconfirmed["stages"][1]["startedAt"] = NOW
        unconfirmed["currentStage"] = "references"
        unconfirmed["pendingQuestion"]["stageId"] = "references"
        write(session_path, unconfirmed)
        run(validator, session_path, False)

        skipped = copy.deepcopy(unconfirmed)
        skipped["stages"][0]["skip"] = confirmed_skip("Пользователь подтвердил маршрут без Blueprint")
        skipped["pendingQuestion"] = {"questionId": "question-references-source", "stageId": "references", "kind": "intake", "text": "Какие референсы использовать?", "why": "Нужны источники направления.", "required": True, "askedAt": NOW}
        write(session_path, skipped)
        run(validator, session_path, True)

        artifact_file = root / "presentation-blueprint.json"
        artifact_file.write_text("fixture\n", encoding="utf-8")
        review = base_session()
        review["stages"][0]["status"] = "review"
        review["stages"][0]["artifact"] = {
            "artifactType": "presentation-blueprint", "contract": "presentation-blueprint/1.2", "schemaVersion": "1.2", "status": "review",
            "location": "presentation-blueprint.json", "locationKind": "file", "entrypoint": None,
            "sha256": hashlib.sha256(artifact_file.read_bytes()).hexdigest(),
        }
        review["pendingQuestion"] = {"questionId": "question-context-approval", "stageId": "context", "kind": "approval", "text": "Утвердить Blueprint?", "why": "Это gate этапа.", "required": True, "askedAt": NOW}
        write(session_path, review)
        run(validator, session_path, True)

        artifact_file.write_text("tampered\n", encoding="utf-8")
        run(validator, session_path, False)

        out_of_order = base_session()
        out_of_order["stages"][0]["status"] = "pending"
        out_of_order["stages"][0]["startedAt"] = None
        out_of_order["stages"][1]["status"] = "active"
        out_of_order["stages"][1]["startedAt"] = NOW
        out_of_order["currentStage"] = "references"
        out_of_order["pendingQuestion"]["stageId"] = "references"
        write(session_path, out_of_order)
        run(validator, session_path, False)

        complete = base_session()
        for item in complete["stages"]:
            item["status"] = "skipped"
            item["startedAt"] = NOW
            item["completedAt"] = NOW
            item["skip"] = confirmed_skip(f"Подтверждён пропуск {item['id']}")
        complete["status"] = "completed"
        complete["currentStage"] = "complete"
        complete["pendingQuestion"] = None
        write(session_path, complete)
        run(validator, session_path, True)

    print("Pipeline session transition tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
