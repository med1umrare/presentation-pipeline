#!/usr/bin/env python3
"""Integration and negative tests for the four-stage presentation pipeline 1.2."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(script: Path, target: Path, *args: str, success: bool = True) -> None:
    result = subprocess.run([sys.executable, str(script), str(target), *args], text=True, capture_output=True)
    if (result.returncode == 0) != success:
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        expectation = "success" if success else "failure"
        raise AssertionError(f"{script.name} expected {expectation}, got {result.returncode}")


def main() -> int:
    skills = Path(__file__).resolve().parents[2]
    blueprint_validator = skills / "context-plan-skill/scripts/validate_presentation_blueprint.py"
    brief_validator = skills / "references-to-visual/scripts/validate_visual_style_brief.py"
    dna_validator = skills / "presentation-style-kit/scripts/validate_visual_dna.py"
    build_validator = skills / "branding-visual-skill/scripts/validate_presentation_build.py"
    session_validator = skills / "presentation-pipeline/scripts/validate_pipeline_session.py"
    for script in (blueprint_validator, brief_validator, dna_validator, build_validator, session_validator):
        if not script.is_file():
            raise FileNotFoundError(script)

    with tempfile.TemporaryDirectory(prefix="presentation-pipeline-1.2-") as temp:
        root = Path(temp)
        blueprint_path = root / "presentation-blueprint.json"
        blueprint = {
            "artifactType": "presentation-blueprint", "contract": "presentation-blueprint/1.2",
            "schemaVersion": "1.2", "status": "approved", "createdAt": "2026-01-01", "language": "ru",
            "decision": {"presentationNeeded": True, "reason": "Последовательность улучшает понимание."},
            "context": {"audience": "Команда", "situation": "Встреча", "desiredOutcome": "Утвердить пилот", "owner": "Автор", "constraints": "10 минут"},
            "format": {"primary": "PPTX", "fallback": "PDF", "reason": "Нужна редактируемость."},
            "centralThesis": "Пилот снижает риск решения.", "desiredAction": "Утвердить пилот.",
            "claims": [{"claimId": "claim-pilot", "statement": "Пилот проверяет гипотезу.", "audienceValue": "Снижает риск.", "evidence": "План эксперимента.", "status": "confirmed", "sourceIds": ["source-plan"], "verificationOwner": "Автор"}],
            "narrativeRoute": ["Контекст", "Решение", "Действие"],
            "slides": [{"slideId": "slide-title", "number": 1, "narrativeJob": "Открыть", "mainPoint": "Проверяем до масштабирования", "claimIds": ["claim-pilot"], "material": "Заголовок", "visualForm": "Тезис"}],
            "visualizationMap": [{"slideId": "slide-title", "insight": "Сначала проверка", "form": "Схема", "assets": []}],
            "sources": [{"sourceId": "source-plan", "location": "plan.md", "verificationStatus": "verified"}],
            "openIssues": [], "approval": {"approvedBy": "Владелец", "approvedAt": "2026-01-01T10:00:00+00:00", "criteriaPassed": True}
        }
        write_json(blueprint_path, blueprint)
        run(blueprint_validator, blueprint_path)

        brief_path = root / "visual-style-brief.json"
        rules = [
            {"ruleId": "rule-color", "category": "color", "value": "Синий акцент", "evidenceStatus": "Confirmed", "sourceIds": ["source-ref"]},
            {"ruleId": "rule-type", "category": "typography", "value": "Контрастная шкала", "evidenceStatus": "Proposed", "sourceIds": ["source-ref"]},
            {"ruleId": "rule-comp", "category": "composition", "value": "Один ведущий объект", "evidenceStatus": "Proposed", "sourceIds": ["source-ref"]},
            {"ruleId": "rule-image", "category": "imagery", "value": "Оригинальные схемы", "evidenceStatus": "Proposed", "sourceIds": ["source-ref"]}
        ]
        screens = [
            {"screenId": "screen-title", "type": "title", "ruleIds": ["rule-color", "rule-type"], "specification": "Титульный экран", "expectedResult": "Ясное открытие", "acceptanceCriteria": ["Контраст"]},
            {"screenId": "screen-content", "type": "content", "ruleIds": ["rule-comp", "rule-type"], "specification": "Содержательный экран", "expectedResult": "Одна мысль", "acceptanceCriteria": ["Иерархия"]},
            {"screenId": "screen-data", "type": "data", "ruleIds": ["rule-image", "rule-color"], "specification": "Экран данных", "expectedResult": "Читаемая схема", "acceptanceCriteria": ["Подписи"]}
        ]
        brief = {
            "artifactType": "visual-style-brief", "contract": "visual-style-brief/1.2", "schemaVersion": "1.2",
            "status": "approved", "createdAt": "2026-01-01", "project": "Pipeline fixture",
            "pipeline": {"mode": "pipeline", "blueprint": {"location": "presentation-blueprint.json", "contract": "presentation-blueprint/1.2", "schemaVersion": "1.2", "sha256": sha(blueprint_path)}},
            "mode": "own-direction", "format": {"targetFormats": ["PPTX"], "aspectRatios": ["16:9"], "audience": "Команда", "targetAction": "Утвердить пилот"},
            "styleSentence": "Строгая светлая система с синим акцентом.",
            "sources": [{"sourceId": "source-ref", "location": "reference.png", "accessedAt": "2026-01-01", "licenseStatus": "verified", "allowedUsage": "Анализ"}],
            "rules": rules, "controlScreens": screens, "openQuestions": [],
            "approval": {"approvedBy": "Владелец", "approvedAt": "2026-01-01T11:00:00+00:00", "criteriaPassed": True}
        }
        write_json(brief_path, brief)
        run(brief_validator, brief_path, "--pipeline")

        dna = root / "visual-dna"
        for relative in ("README.md", "principles.md", "typography.md", "composition.md", "imagery.md", "motion.md", "do-dont.md", "prompts.md", "references-manifest.md", "examples/README.md"):
            path = dna / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {path.stem}\n", encoding="utf-8")
        tokens = {
            "artifactType": "visual-dna-tokens", "contract": "presentation-visual-dna-tokens/1.2", "schemaVersion": "1.2",
            "colors": {"background": "#ffffff", "surface": "#f5f5f5", "text": "#111111", "text-muted": "#666666", "accent": "#0055cc", "border": "#cccccc"},
            "typography": {"display": "Arial, sans-serif", "body": "Arial, sans-serif", "technical": "Consolas, monospace", "fallback": "sans-serif"},
            "fontSizes": {"display": "48px", "body": "24px", "caption": "16px"},
            "spacing": {"sm": "8px", "md": "16px", "lg": "32px"},
            "geometry": {"radius": {"card": "8px"}, "borderWidth": {"default": "1px"}, "shadow": {"card": "0 2px 8px #0002"}},
            "formats": {"pptx": {"aspectRatio": "16:9"}}
        }
        write_json(dna / "tokens.json", tokens)
        css_lines = [":root {"]
        for key, value in tokens["colors"].items(): css_lines.append(f"  --color-{key}: {value};")
        for key, value in tokens["typography"].items(): css_lines.append(f"  --font-{key}: {value};")
        for key, value in tokens["fontSizes"].items(): css_lines.append(f"  --font-size-{key}: {value};")
        for key, value in tokens["spacing"].items(): css_lines.append(f"  --space-{key}: {value};")
        for key, value in tokens["geometry"]["radius"].items(): css_lines.append(f"  --radius-{key}: {value};")
        for key, value in tokens["geometry"]["borderWidth"].items(): css_lines.append(f"  --border-width-{key}: {value};")
        for key, value in tokens["geometry"]["shadow"].items(): css_lines.append(f"  --shadow-{key}: {value};")
        css_lines.append("}")
        (dna / "tokens.css").write_text("\n".join(css_lines) + "\n", encoding="utf-8")
        examples = []
        for kind in ("title", "content", "data"):
            example = dna / f"examples/{kind}.svg"
            example.write_text(f"<svg xmlns=\"http://www.w3.org/2000/svg\"><text>{kind}</text></svg>\n", encoding="utf-8")
            examples.append({"path": f"examples/{kind}.svg", "type": kind, "status": "approved", "provenance": "Original fixture", "allowedUsage": "Course tests", "sha256": sha(example)})
        dna_manifest = {
            "artifactType": "visual-dna", "contract": "presentation-visual-dna/1.2", "schemaVersion": "1.2", "status": "approved",
            "createdAt": "2026-01-01", "owner": "Владелец", "targetFormats": ["PPTX"],
            "sourceBrief": {"location": "../visual-style-brief.json", "contract": "visual-style-brief/1.2", "schemaVersion": "1.2", "status": "approved", "sha256": sha(brief_path)},
            "scope": "Course fixture", "openIssues": [], "examples": examples,
            "approval": {"approvedBy": "Владелец", "approvedAt": "2026-01-01T12:00:00+00:00", "criteriaPassed": True}
        }
        write_json(dna / "visual-dna-manifest.json", dna_manifest)
        run(dna_validator, dna)

        build = root / "presentation-build"
        for relative in ("README.md", "sources.md", "format-fallbacks.md", "qa-report.md", "source/main.txt", "output/deck.txt", "renders/slide-1.txt"):
            path = build / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture\n", encoding="utf-8")
        manifest = {
            "artifactType": "presentation-build", "contract": "presentation-build/1.2", "schemaVersion": "1.2", "status": "approved",
            "buildMode": "pipeline", "withoutReusableDna": False, "builderVersion": "1.2.0", "createdAt": "2026-01-01T13:00:00+00:00",
            "inputs": [
                {"type": "presentation-blueprint", "location": "../presentation-blueprint.json", "contract": "presentation-blueprint/1.2", "schemaVersion": "1.2", "sha256": sha(blueprint_path)},
                {"type": "visual-dna", "location": "../visual-dna/visual-dna-manifest.json", "contract": "presentation-visual-dna/1.2", "schemaVersion": "1.2", "sha256": sha(dna / "visual-dna-manifest.json")}
            ],
            "targetFormats": ["PPTX"], "dnaRoleMapping": {}, "fontSubstitutions": [], "syntheticData": [],
            "outputs": ["output/deck.txt"], "qa": {"semantic": "pass", "visual": "pass", "technical": "pass"}, "reviewBlockers": [],
            "approval": {"approvedBy": "Владелец", "approvedAt": "2026-01-01T14:00:00+00:00", "criteriaPassed": True}
        }
        write_json(build / "build-manifest.json", manifest)
        run(build_validator, build)

        session = {
            "artifactType": "presentation-pipeline-session", "contract": "presentation-pipeline-session/1.0", "schemaVersion": "1.0",
            "sessionId": "deep-fixture", "createdAt": "2026-01-01T09:00:00+00:00", "updatedAt": "2026-01-01T15:00:00+00:00",
            "status": "completed", "currentStage": "complete", "interactionMode": "question-answer", "projectRoot": ".",
            "stages": [
                {"id": "context", "order": 1, "skill": "context-plan-skill", "status": "approved", "startedAt": "2026-01-01T09:00:00+00:00", "completedAt": "2026-01-01T10:00:00+00:00", "artifact": {"artifactType": "presentation-blueprint", "contract": "presentation-blueprint/1.2", "schemaVersion": "1.2", "status": "approved", "location": "presentation-blueprint.json", "locationKind": "file", "entrypoint": None, "sha256": sha(blueprint_path)}, "skip": None},
                {"id": "references", "order": 2, "skill": "references-to-visual", "status": "approved", "startedAt": "2026-01-01T10:00:00+00:00", "completedAt": "2026-01-01T11:00:00+00:00", "artifact": {"artifactType": "visual-style-brief", "contract": "visual-style-brief/1.2", "schemaVersion": "1.2", "status": "approved", "location": "visual-style-brief.json", "locationKind": "file", "entrypoint": None, "sha256": sha(brief_path)}, "skip": None},
                {"id": "style-kit", "order": 3, "skill": "presentation-style-kit", "status": "approved", "startedAt": "2026-01-01T11:00:00+00:00", "completedAt": "2026-01-01T12:00:00+00:00", "artifact": {"artifactType": "visual-dna", "contract": "presentation-visual-dna/1.2", "schemaVersion": "1.2", "status": "approved", "location": "visual-dna", "locationKind": "directory", "entrypoint": "visual-dna-manifest.json", "sha256": sha(dna / "visual-dna-manifest.json")}, "skip": None},
                {"id": "build", "order": 4, "skill": "branding-visual-skill", "status": "approved", "startedAt": "2026-01-01T12:00:00+00:00", "completedAt": "2026-01-01T15:00:00+00:00", "artifact": {"artifactType": "presentation-build", "contract": "presentation-build/1.2", "schemaVersion": "1.2", "status": "approved", "location": "presentation-build", "locationKind": "directory", "entrypoint": "build-manifest.json", "sha256": sha(build / "build-manifest.json")}, "skip": None}
            ],
            "pendingQuestion": None, "decisions": [], "lastValidatedAt": "2026-01-01T15:00:00+00:00"
        }
        session_path = root / "presentation-pipeline-session.json"
        write_json(session_path, session)
        run(session_validator, session_path, "--deep")

        one_off_manifest = json.loads(json.dumps(manifest))
        one_off_manifest["buildMode"] = "one-off"
        one_off_manifest["withoutReusableDna"] = True
        one_off_manifest["inputs"] = [
            {"type": "presentation-blueprint", "location": "../presentation-blueprint.json", "contract": "presentation-blueprint/1.2", "schemaVersion": "1.2", "sha256": sha(blueprint_path)},
            {"type": "visual-style-brief", "location": "../visual-style-brief.json", "contract": "visual-style-brief/1.2", "schemaVersion": "1.2", "sha256": sha(brief_path)}
        ]
        write_json(build / "build-manifest.json", one_off_manifest)
        run(build_validator, build)
        one_off_session = json.loads(json.dumps(session))
        one_off_session["stages"][2]["status"] = "skipped"
        one_off_session["stages"][2]["artifact"] = None
        one_off_session["stages"][2]["skip"] = {
            "requestedAt": "2026-01-01T11:00:00+00:00", "reason": "Разовая презентация",
            "consequences": ["Сборка не получает reusable Visual DNA"],
            "confirmationQuestion": "Подтверждаете пропуск Visual DNA?", "confirmed": True,
            "confirmedBy": "user", "confirmedAt": "2026-01-01T11:05:00+00:00", "replacementArtifact": None
        }
        one_off_session["stages"][3]["artifact"]["sha256"] = sha(build / "build-manifest.json")
        write_json(session_path, one_off_session)
        run(session_validator, session_path, "--deep")
        write_json(build / "build-manifest.json", manifest)

        blueprint["openIssues"] = ["Незакрытый блокер"]
        write_json(blueprint_path, blueprint)
        run(blueprint_validator, blueprint_path, success=False)
        blueprint["openIssues"] = []
        write_json(blueprint_path, blueprint)

        brief["pipeline"]["blueprint"]["sha256"] = sha(blueprint_path)
        brief["openQuestions"] = ["Незакрытый вопрос"]
        write_json(brief_path, brief)
        run(brief_validator, brief_path, "--pipeline", success=False)
        brief["openQuestions"] = []
        write_json(brief_path, brief)

        dna_manifest["sourceBrief"]["sha256"] = sha(brief_path)
        dna_manifest["sourceBrief"]["status"] = "review"
        write_json(dna / "visual-dna-manifest.json", dna_manifest)
        run(dna_validator, dna, success=False)
        dna_manifest["sourceBrief"]["status"] = "approved"
        write_json(dna / "visual-dna-manifest.json", dna_manifest)

        manifest["inputs"][0]["sha256"] = sha(blueprint_path)
        manifest["inputs"][1]["sha256"] = sha(dna / "visual-dna-manifest.json")
        manifest["qa"]["visual"] = "warning"
        write_json(build / "build-manifest.json", manifest)
        run(build_validator, build, success=False)
        manifest["qa"]["visual"] = "pass"
        write_json(build / "build-manifest.json", manifest)

        original_blueprint = blueprint_path.read_text(encoding="utf-8")
        blueprint_path.write_text(original_blueprint + " ", encoding="utf-8")
        run(brief_validator, brief_path, "--pipeline", success=False)
        run(build_validator, build, success=False)
        blueprint_path.write_text(original_blueprint, encoding="utf-8")

        original_brief = brief_path.read_text(encoding="utf-8")
        brief_path.write_text(original_brief + " ", encoding="utf-8")
        run(dna_validator, dna, success=False)
        brief_path.write_text(original_brief, encoding="utf-8")

        original_css = (dna / "tokens.css").read_text(encoding="utf-8")
        (dna / "tokens.css").write_text(original_css.replace("#0055cc", "#ff0000"), encoding="utf-8")
        run(dna_validator, dna, success=False)

    print("Pipeline 1.2 integration and negative tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
