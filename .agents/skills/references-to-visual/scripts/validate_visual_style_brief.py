#!/usr/bin/env python3
"""Validate Visual Style Brief 1.2; accept 1.1 as legacy with warnings."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path


REQUIRED_CATEGORIES = {"color", "typography", "composition", "imagery"}


def nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_date(value: object, *, with_time: bool = False) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00")) if with_time else date.fromisoformat(value)
        return True
    except ValueError:
        return False


def main() -> int:
    args = [arg for arg in sys.argv[1:] if arg != "--pipeline"]
    require_pipeline = "--pipeline" in sys.argv[1:]
    if len(args) != 1:
        print("Usage: validate_visual_style_brief.py <visual-style-brief.json> [--pipeline]")
        return 2
    path = Path(args[0]).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: Cannot read valid JSON: {exc}")
        return 1
    if not isinstance(data, dict):
        print("ERROR: Style Brief must be a JSON object")
        return 1

    version = data.get("schemaVersion")
    if data.get("artifactType") != "visual-style-brief":
        errors.append("artifactType must be 'visual-style-brief'")
    if version == "1.1":
        warnings.append("Legacy Style Brief 1.1: upgrade to visual-style-brief/1.2 for new course materials")
    elif version == "1.2":
        if data.get("contract") != "visual-style-brief/1.2":
            errors.append("contract must be 'visual-style-brief/1.2'")
    else:
        errors.append("schemaVersion must be '1.2' (or legacy '1.1')")

    status = data.get("status")
    if status not in {"draft", "review", "approved"}:
        errors.append("status must be draft, review or approved")
    if not valid_date(data.get("createdAt")):
        errors.append("createdAt must be an ISO date")
    if not nonempty(data.get("styleSentence")):
        errors.append("styleSentence is required")
    if version == "1.2" and not nonempty(data.get("project")):
        errors.append("project is required")
    if version == "1.2":
        if data.get("mode") not in {"own-direction", "client-reading", "reference-synthesis"}:
            errors.append("mode is invalid")
        fmt = data.get("format")
        if not isinstance(fmt, dict):
            errors.append("format must be an object")
        else:
            for key in ("targetFormats", "aspectRatios"):
                if not isinstance(fmt.get(key), list) or not fmt[key]:
                    errors.append(f"format.{key} must be a non-empty array")
            for key in ("audience", "targetAction"):
                if not nonempty(fmt.get(key)):
                    errors.append(f"format.{key} is required")

    sources = data.get("sources")
    rules = data.get("rules")
    screens = data.get("controlScreens")
    if not isinstance(sources, list) or not sources:
        errors.append("sources must be a non-empty array")
        sources = []
    if not isinstance(rules, list) or not rules:
        errors.append("rules must be a non-empty array")
        rules = []
    if not isinstance(screens, list) or len(screens) < 3:
        errors.append("controlScreens must contain at least three screens")
        screens = []

    def collect_ids(items: list[object], key: str, pattern: str) -> set[str]:
        values: list[str] = []
        for index, item in enumerate(items):
            value = item.get(key) if isinstance(item, dict) else None
            if not isinstance(value, str) or not re.fullmatch(pattern, value):
                errors.append(f"{key} at index {index} is invalid")
            else:
                values.append(value)
        if len(values) != len(set(values)):
            errors.append(f"{key} values must be unique")
        return set(values)

    source_ids = collect_ids(sources, "sourceId", r"source-[a-z0-9-]+")
    rule_ids = collect_ids(rules, "ruleId", r"rule-[a-z0-9-]+")
    collect_ids(screens, "screenId", r"screen-[a-z0-9-]+" if version == "1.2" else r"[a-z][a-z0-9-]+")
    categories: set[str] = set()
    if version == "1.2":
        for source in sources:
            if not isinstance(source, dict):
                errors.append("each source must be an object")
                continue
            if not nonempty(source.get("location")) or not valid_date(source.get("accessedAt")):
                errors.append(f"{source.get('sourceId')}: location and accessedAt are required")
            if source.get("licenseStatus") not in {"verified", "restricted", "unknown"}:
                errors.append(f"{source.get('sourceId')}.licenseStatus is invalid")
            if not nonempty(source.get("allowedUsage")):
                errors.append(f"{source.get('sourceId')}.allowedUsage is required")
    for rule in rules:
        if not isinstance(rule, dict):
            errors.append("each rule must be an object")
            continue
        categories.add(str(rule.get("category")))
        if version == "1.2" and rule.get("category") not in {"color", "typography", "composition", "imagery", "texture", "motion", "constraint"}:
            errors.append(f"{rule.get('ruleId')}.category is invalid")
        if version == "1.2" and rule.get("evidenceStatus") not in {"Observed", "Confirmed", "Inferred", "Proposed"}:
            errors.append(f"{rule.get('ruleId')}.evidenceStatus is invalid")
        refs = rule.get("sourceIds")
        if not isinstance(refs, list):
            errors.append(f"{rule.get('ruleId')}.sourceIds must be an array")
        elif set(refs) - source_ids:
            errors.append(f"{rule.get('ruleId')}: unknown sourceIds {sorted(set(refs) - source_ids)}")
    if version == "1.2" and REQUIRED_CATEGORIES - categories:
        errors.append(f"missing required rule categories {sorted(REQUIRED_CATEGORIES - categories)}")
    for screen in screens:
        if not isinstance(screen, dict):
            errors.append("each control screen must be an object")
            continue
        refs = screen.get("ruleIds")
        if not isinstance(refs, list) or not refs:
            errors.append(f"{screen.get('screenId')}.ruleIds must be a non-empty array")
        elif set(refs) - rule_ids:
            errors.append(f"{screen.get('screenId')}: unknown ruleIds {sorted(set(refs) - rule_ids)}")
        if version == "1.2" and (not nonempty(screen.get("specification")) or not nonempty(screen.get("expectedResult")) or not isinstance(screen.get("acceptanceCriteria"), list) or not screen["acceptanceCriteria"]):
            errors.append(f"{screen.get('screenId')}: incomplete control-screen specification")
        if version == "1.2" and screen.get("type") not in {"title", "content", "data", "cta", "quote", "product-demo"}:
            errors.append(f"{screen.get('screenId')}.type is invalid")

    pipeline = data.get("pipeline")
    pipeline_mode = isinstance(pipeline, dict) and pipeline.get("mode") == "pipeline"
    if version == "1.2" and (not isinstance(pipeline, dict) or pipeline.get("mode") not in {"pipeline", "standalone"}):
        errors.append("pipeline.mode must be pipeline or standalone")
    if require_pipeline and not pipeline_mode:
        errors.append("--pipeline requires pipeline.mode='pipeline'")
    if pipeline_mode:
        blueprint = pipeline.get("blueprint")
        if not isinstance(blueprint, dict):
            errors.append("pipeline mode requires blueprint reference")
        else:
            location = blueprint.get("location")
            declared_hash = blueprint.get("sha256")
            if not nonempty(location) or not isinstance(declared_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", declared_hash):
                errors.append("pipeline.blueprint requires location and lowercase SHA-256")
            else:
                target = (path.parent / location).resolve()
                if not target.is_file():
                    errors.append(f"Blueprint does not exist: {location}")
                else:
                    actual = hashlib.sha256(target.read_bytes()).hexdigest()
                    if actual != declared_hash:
                        errors.append("Blueprint SHA-256 does not match")
            if version == "1.2" and (blueprint.get("contract") != "presentation-blueprint/1.2" or blueprint.get("schemaVersion") != "1.2"):
                errors.append("pipeline.blueprint must declare presentation-blueprint/1.2")
    elif require_pipeline and version == "1.1":
        errors.append("legacy 1.1 Style Brief has no verifiable Blueprint handoff")

    open_questions = data.get("openQuestions", [])
    if status == "approved":
        approval = data.get("approval")
        if version == "1.2" and (not isinstance(approval, dict) or not nonempty(approval.get("approvedBy")) or not valid_date(approval.get("approvedAt"), with_time=True) or approval.get("criteriaPassed") is not True):
            errors.append("approved Style Brief requires approval.approvedBy, approvedAt and criteriaPassed=true")
        if version == "1.2" and open_questions:
            errors.append("approved Style Brief cannot contain openQuestions")

    for message in warnings:
        print(f"WARNING: {message}")
    if errors:
        print("\n".join(f"ERROR: {message}" for message in errors))
        return 1
    print(f"Visual Style Brief {version} is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
