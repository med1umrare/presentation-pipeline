#!/usr/bin/env python3
"""Integration and negative tests for data charts across the pipeline.

Covers presentation-chart-spec/1.0, Blueprint datasets/chartType, the Visual DNA
dataviz section and charts in presentation-build/1.2.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_pipeline_contracts import run, sha, write_json  # noqa: E402


def main() -> int:
    skills = Path(__file__).resolve().parents[2]
    chart_validator = skills / "branding-visual-skill/scripts/validate_chart_spec.py"
    blueprint_validator = skills / "context-plan-skill/scripts/validate_presentation_blueprint.py"
    dna_validator = skills / "presentation-style-kit/scripts/validate_visual_dna.py"
    build_validator = skills / "branding-visual-skill/scripts/validate_presentation_build.py"
    demo = skills / "branding-visual-skill/examples/dataviz-demo"

    chart_types = json.loads((skills / "branding-visual-skill/references/chart-spec.schema.json").read_text(encoding="utf-8"))["properties"]["type"]["enum"]
    blueprint_schema = json.loads((skills / "context-plan-skill/references/presentation-blueprint.schema.json").read_text(encoding="utf-8"))
    planned_types = blueprint_schema["properties"]["visualizationMap"]["items"]["properties"]["chartType"]["enum"]
    if chart_types != planned_types:
        raise AssertionError("chartType enum in Blueprint schema differs from chart-spec type enum")

    run(chart_validator, demo / "charts")

    with tempfile.TemporaryDirectory(prefix="presentation-dataviz-") as temp:
        root = Path(temp)

        # Blueprint with a registered dataset and a charted slide.
        (root / "data").mkdir()
        shutil.copy(demo / "data/revenue-bridge.csv", root / "data/revenue-bridge.csv")
        blueprint_path = root / "presentation-blueprint.json"
        blueprint = {
            "artifactType": "presentation-blueprint", "contract": "presentation-blueprint/1.2",
            "schemaVersion": "1.2", "status": "approved", "createdAt": "2026-01-01", "language": "ru",
            "decision": {"presentationNeeded": True, "reason": "Числа убедительнее показать."},
            "context": {"audience": "Собственник", "situation": "Итоги года", "desiredOutcome": "Вложиться в бренд-съёмки", "owner": "Автор", "constraints": "10 минут"},
            "format": {"primary": "PPTX", "fallback": "PDF", "reason": "Нужна редактируемость."},
            "centralThesis": "Рост дали бренд-съёмки.", "desiredAction": "Утвердить бюджет.",
            "claims": [{"claimId": "claim-revenue-drivers", "statement": "Рост дали бренд-съёмки и портреты.", "audienceValue": "Куда вкладываться.", "evidence": "Выручка по типам.", "status": "confirmed", "sourceIds": ["source-accounting"], "verificationOwner": "Автор"}],
            "narrativeRoute": ["Итог", "Причины", "Решение"],
            "slides": [{"slideId": "slide-revenue-bridge", "number": 1, "narrativeJob": "Доказать", "mainPoint": "Бренд-съёмки и портреты дали +1,5 млн ₽", "claimIds": ["claim-revenue-drivers"], "material": "revenue-bridge.csv", "visualForm": "Waterfall"}],
            "visualizationMap": [{"slideId": "slide-revenue-bridge", "insight": "Из чего сложился рост", "form": "Диаграмма", "assets": [], "chartType": "waterfall", "datasetIds": ["dataset-revenue-bridge"]}],
            "datasets": [{"datasetId": "dataset-revenue-bridge", "location": "data/revenue-bridge.csv", "description": "Выручка по типам съёмок", "period": "2024–2025", "dataStatus": "synthetic", "sourceIds": ["source-accounting"], "sha256": sha(root / "data/revenue-bridge.csv")}],
            "sources": [{"sourceId": "source-accounting", "location": "accounting.xlsx", "verificationStatus": "verified"}],
            "openIssues": [], "approval": {"approvedBy": "Владелец", "approvedAt": "2026-01-01T10:00:00+00:00", "criteriaPassed": True}
        }
        write_json(blueprint_path, blueprint)
        run(blueprint_validator, blueprint_path)

        def blueprint_fails(change) -> None:
            broken = json.loads(json.dumps(blueprint))
            change(broken)
            write_json(blueprint_path, broken)
            run(blueprint_validator, blueprint_path, success=False)
            write_json(blueprint_path, blueprint)

        blueprint_fails(lambda b: b["visualizationMap"][0].pop("datasetIds"))
        blueprint_fails(lambda b: b["visualizationMap"][0].update(datasetIds=["dataset-missing"]))
        blueprint_fails(lambda b: b["visualizationMap"][0].update(chartType="pie"))
        blueprint_fails(lambda b: b["datasets"][0].update(dataStatus="pending"))
        blueprint_fails(lambda b: b["datasets"][0].update(sha256="0" * 64))

        # Visual DNA with a dataviz section.
        brief_path = root / "visual-style-brief.json"
        write_json(brief_path, {"artifactType": "visual-style-brief", "contract": "visual-style-brief/1.2", "schemaVersion": "1.2", "status": "approved"})
        dna = root / "visual-dna"
        for relative in ("README.md", "principles.md", "typography.md", "composition.md", "imagery.md", "motion.md", "do-dont.md", "prompts.md", "references-manifest.md", "examples/README.md"):
            path = dna / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {path.stem}\n", encoding="utf-8")
        tokens = json.loads((demo / "tokens.json").read_text(encoding="utf-8"))
        write_json(dna / "tokens.json", tokens)

        def write_css(tokens: dict) -> None:
            lines = [":root {"]
            for prefix, group in (("color", tokens["colors"]), ("font", tokens["typography"]), ("font-size", tokens["fontSizes"]), ("space", tokens["spacing"]),
                                  ("radius", tokens["geometry"]["radius"]), ("border-width", tokens["geometry"]["borderWidth"]), ("shadow", tokens["geometry"]["shadow"]),
                                  ("dataviz", tokens.get("dataviz", {}).get("colors", {}))):
                lines += [f"  --{prefix}-{key}: {value};" for key, value in group.items()]
            (dna / "tokens.css").write_text("\n".join(lines + ["}"]) + "\n", encoding="utf-8")

        write_css(tokens)
        examples = []
        for kind in ("title", "content", "data"):
            example = dna / f"examples/{kind}.svg"
            example.write_text(f"<svg xmlns=\"http://www.w3.org/2000/svg\"><text>{kind}</text></svg>\n", encoding="utf-8")
            examples.append({"path": f"examples/{kind}.svg", "type": kind, "status": "approved", "provenance": "Original fixture", "allowedUsage": "Course tests", "sha256": sha(example)})
        write_json(dna / "visual-dna-manifest.json", {
            "artifactType": "visual-dna", "contract": "presentation-visual-dna/1.2", "schemaVersion": "1.2", "status": "approved",
            "createdAt": "2026-01-01", "owner": "Владелец", "targetFormats": ["PPTX"],
            "sourceBrief": {"location": "../visual-style-brief.json", "contract": "visual-style-brief/1.2", "schemaVersion": "1.2", "status": "approved", "sha256": sha(brief_path)},
            "scope": "Dataviz fixture", "openIssues": [], "examples": examples,
            "approval": {"approvedBy": "Владелец", "approvedAt": "2026-01-01T12:00:00+00:00", "criteriaPassed": True}
        })
        run(dna_validator, dna)

        def dna_fails(change, css_from_tokens: bool = True) -> None:
            broken = json.loads(json.dumps(tokens))
            change(broken)
            write_json(dna / "tokens.json", broken)
            write_css(broken if css_from_tokens else tokens)
            run(dna_validator, dna, success=False)
            write_json(dna / "tokens.json", tokens)
            write_css(tokens)

        dna_fails(lambda t: t["dataviz"]["colors"].pop("focus"))
        dna_fails(lambda t: t["dataviz"]["colors"].update(focus="rgb(7, 87, 201)"))
        dna_fails(lambda t: t["dataviz"]["sizesPt"].update(title="26px"))
        dna_fails(lambda t: t["dataviz"]["colors"].update(context="#000000"), css_from_tokens=False)
        dna_fails(lambda t: t["dataviz"]["numberFormat"].update(thousandsSeparator=","))

        # Build with one chart.
        build = root / "presentation-build"
        for relative in ("README.md", "sources.md", "format-fallbacks.md", "qa-report.md", "output/deck.pptx", "renders/slide-01.png"):
            path = build / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture\n", encoding="utf-8")
        (build / "source/data").mkdir(parents=True)
        (build / "source/charts").mkdir(parents=True)
        shutil.copy(demo / "data/revenue-bridge.csv", build / "source/data/revenue-bridge.csv")
        spec_path = build / "source/charts/01-revenue-bridge.chart.json"
        spec = json.loads((demo / "charts/02-waterfall.chart.json").read_text(encoding="utf-8"))
        write_json(spec_path, spec)
        run(chart_validator, build / "source/charts")
        manifest = {
            "artifactType": "presentation-build", "contract": "presentation-build/1.2", "schemaVersion": "1.2", "status": "approved",
            "buildMode": "pipeline", "withoutReusableDna": False, "builderVersion": "1.2.0", "createdAt": "2026-01-01T13:00:00+00:00",
            "inputs": [
                {"type": "presentation-blueprint", "location": "../presentation-blueprint.json", "contract": "presentation-blueprint/1.2", "schemaVersion": "1.2", "sha256": sha(blueprint_path)},
                {"type": "visual-dna", "location": "../visual-dna/visual-dna-manifest.json", "contract": "presentation-visual-dna/1.2", "schemaVersion": "1.2", "sha256": sha(dna / "visual-dna-manifest.json")}
            ],
            "targetFormats": ["PPTX"], "dnaRoleMapping": {}, "fontSubstitutions": [], "syntheticData": ["source/data/revenue-bridge.csv"],
            "outputs": ["output/deck.pptx"],
            "charts": [{"chartId": spec["chartId"], "location": "source/charts/01-revenue-bridge.chart.json", "contract": "presentation-chart-spec/1.0", "sha256": sha(spec_path)}],
            "qa": {"semantic": "pass", "visual": "pass", "technical": "pass", "data": "pass"}, "reviewBlockers": [],
            "approval": {"approvedBy": "Владелец", "approvedAt": "2026-01-01T14:00:00+00:00", "criteriaPassed": True}
        }
        write_json(build / "build-manifest.json", manifest)
        run(build_validator, build)

        def build_fails(change_manifest=None, change_spec=None) -> None:
            broken = json.loads(json.dumps(manifest))
            if change_spec:
                bad_spec = json.loads(json.dumps(spec))
                change_spec(bad_spec)
                write_json(spec_path, bad_spec)
                broken["charts"][0]["sha256"] = sha(spec_path)
            if change_manifest:
                change_manifest(broken)
            write_json(build / "build-manifest.json", broken)
            run(build_validator, build, success=False)
            write_json(spec_path, spec)
            write_json(build / "build-manifest.json", manifest)

        build_fails(change_manifest=lambda m: m["qa"].pop("data"))
        build_fails(change_manifest=lambda m: m["qa"].update(data="warning"))
        build_fails(change_manifest=lambda m: m["charts"][0].update(sha256="0" * 64))
        build_fails(change_spec=lambda s: s.update(annotation="Без бренд-съёмок рост составил бы 0,7 млн ₽ вместо 1,4."))
        build_fails(change_spec=lambda s: s.update(title="Бренд-съёмки и портреты дали +1,6 млн ₽"))
        build_fails(change_spec=lambda s: s.update(slideId="slide-unknown"))
        build_fails(change_spec=lambda s: s.update(claimIds=["claim-unknown"]))
        build_fails(change_spec=lambda s: s.update(verifiedNumbers=[{"value": "0,7", "note": ""}], annotation="Рост составил бы 0,7 млн ₽."))

        csv_path = build / "source/data/revenue-bridge.csv"
        original_csv = csv_path.read_bytes()
        csv_path.write_bytes(original_csv.replace(b"0.9", b"1.0"))
        run(build_validator, build, success=False)
        csv_path.write_bytes(original_csv)
        run(build_validator, build)

        unbalanced = json.loads(json.dumps(spec))
        bad_csv = build / "source/data/unbalanced.csv"
        bad_csv.write_bytes(original_csv.replace(b"5.6", b"5.9"))
        unbalanced["data"].update(location="data/unbalanced.csv", sha256=sha(bad_csv))
        write_json(spec_path, unbalanced)
        run(chart_validator, build / "source/charts", success=False)

    print("Dataviz contract tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
