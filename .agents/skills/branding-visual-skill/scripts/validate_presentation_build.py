#!/usr/bin/env python3
"""Final pipeline gate for presentation-build/1.2; accept 1.1 as legacy."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_chart_spec import CONTRACT as CHART_CONTRACT, validate as validate_chart  # noqa: E402


REQUIRED_FILES = ("README.md", "build-manifest.json", "sources.md", "format-fallbacks.md", "qa-report.md")
REQUIRED_DIRS = ("source", "output", "renders")
EXPECTED_INPUTS = {
    "presentation-blueprint": ("presentation-blueprint", "presentation-blueprint/1.2"),
    "visual-style-brief": ("visual-style-brief", "visual-style-brief/1.2"),
    "visual-dna": ("visual-dna", "presentation-visual-dna/1.2"),
}


def load_json(path: Path, errors: list[str], label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"Cannot read valid {label}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{label} must contain a JSON object")
        return {}
    return value


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate_presentation_build.py <presentation-build-directory>")
        return 2
    root = Path(sys.argv[1]).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            errors.append(f"Missing required file: {relative}")
    for relative in REQUIRED_DIRS:
        if not (root / relative).is_dir():
            errors.append(f"Missing required directory: {relative}/")
    if errors:
        print("\n".join(f"ERROR: {item}" for item in errors))
        return 1

    manifest = load_json(root / "build-manifest.json", errors, "build-manifest.json")
    version = manifest.get("schemaVersion")
    if manifest.get("artifactType") != "presentation-build":
        errors.append("artifactType must be 'presentation-build'")
    if version == "1.1":
        if manifest.get("contract") != "presentation-build/1.1":
            errors.append("legacy build contract must be presentation-build/1.1")
        warnings.append("Legacy Presentation Build 1.1: upgrade to presentation-build/1.2 for new course materials")
    elif version == "1.2":
        if manifest.get("contract") != "presentation-build/1.2":
            errors.append("contract must be presentation-build/1.2")
    else:
        errors.append("schemaVersion must be '1.2' (or legacy '1.1')")

    status = manifest.get("status")
    if status not in {"draft", "review", "approved"}:
        errors.append("invalid build status")
    try:
        datetime.fromisoformat(str(manifest.get("createdAt", "")).replace("Z", "+00:00"))
    except ValueError:
        errors.append("createdAt must be an ISO date-time")
    inputs = manifest.get("inputs")
    if not isinstance(inputs, list) or len(inputs) < 2:
        errors.append("at least two inputs are required")
        inputs = []
    input_types: list[str] = []
    blueprint: dict = {}
    for index, item in enumerate(inputs):
        if not isinstance(item, dict):
            errors.append(f"input {index} must be an object")
            continue
        input_type = item.get("type")
        input_types.append(str(input_type))
        location = item.get("location")
        declared_hash = item.get("sha256")
        if not isinstance(location, str) or not location.strip():
            errors.append(f"input {index} requires location")
            continue
        input_path = (root / location).resolve()
        if not input_path.is_file():
            errors.append(f"input does not exist: {location}")
            continue
        if not isinstance(declared_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", declared_hash):
            if version == "1.2":
                errors.append(f"input {location} requires lowercase SHA-256")
        elif hashlib.sha256(input_path.read_bytes()).hexdigest() != declared_hash:
            errors.append(f"input SHA-256 does not match: {location}")
        if input_type in EXPECTED_INPUTS:
            upstream = load_json(input_path, errors, location)
            if input_type == "presentation-blueprint":
                blueprint = upstream
            artifact, contract = EXPECTED_INPUTS[input_type]
            if upstream.get("artifactType") != artifact:
                errors.append(f"input {location}: artifactType does not match type {input_type}")
            if version == "1.2":
                if item.get("contract") != contract or item.get("schemaVersion") != "1.2":
                    errors.append(f"input descriptor {location} must declare {contract} schema 1.2")
                if upstream.get("contract") != contract or upstream.get("schemaVersion") != "1.2":
                    errors.append(f"input file {location} must use {contract} schema 1.2")
                if upstream.get("status") != "approved":
                    errors.append(f"pipeline input {location} must be approved")
    if len(input_types) != len(set(input_types)):
        errors.append("input types must be unique")
    if "presentation-blueprint" not in input_types:
        errors.append("presentation-blueprint input is required")
    if version == "1.2":
        if not isinstance(manifest.get("builderVersion"), str) or not manifest["builderVersion"].strip():
            errors.append("builderVersion is required")
        if not isinstance(manifest.get("targetFormats"), list) or not manifest["targetFormats"]:
            errors.append("targetFormats must be a non-empty array")
        build_mode = manifest.get("buildMode")
        if build_mode == "pipeline":
            if "visual-dna" not in input_types or manifest.get("withoutReusableDna") is not False:
                errors.append("pipeline mode requires visual-dna and withoutReusableDna=false")
        elif build_mode == "one-off":
            if "visual-style-brief" not in input_types or manifest.get("withoutReusableDna") is not True:
                errors.append("one-off mode requires visual-style-brief and withoutReusableDna=true")
        else:
            errors.append("buildMode must be pipeline or one-off")

    outputs = manifest.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        errors.append("outputs must be a non-empty array")
    else:
        for relative in outputs:
            if not isinstance(relative, str):
                errors.append("each output must be a string path")
                continue
            output_path = (root / relative).resolve()
            if not output_path.is_file() or root not in output_path.parents:
                errors.append(f"Output does not exist inside build directory: {relative}")
    qa = manifest.get("qa", {})
    for section in ("semantic", "visual", "technical"):
        if not isinstance(qa, dict) or qa.get(section) not in {"pass", "fail", "warning"}:
            errors.append(f"invalid qa.{section}")
    charts = manifest.get("charts", [])
    if not isinstance(charts, list):
        errors.append("charts must be an array")
        charts = []
    if charts:
        if not isinstance(qa, dict) or qa.get("data") not in {"pass", "fail", "warning"}:
            errors.append("qa.data is required when the build contains charts")
        slide_ids = {s.get("slideId") for s in blueprint.get("slides", []) if isinstance(s, dict)}
        claim_ids = {c.get("claimId") for c in blueprint.get("claims", []) if isinstance(c, dict)}
        seen: set[str] = set()
        for item in charts:
            if not isinstance(item, dict):
                errors.append("each chart must be an object")
                continue
            location = item.get("location")
            spec_path = (root / location).resolve() if isinstance(location, str) and location.strip() else None
            if spec_path is None or not spec_path.is_file() or root not in spec_path.parents:
                errors.append(f"chart spec does not exist inside build directory: {location!r}")
                continue
            if item.get("contract") != CHART_CONTRACT:
                errors.append(f"chart {location} must declare {CHART_CONTRACT}")
            if hashlib.sha256(spec_path.read_bytes()).hexdigest() != item.get("sha256"):
                errors.append(f"chart spec SHA-256 does not match: {location}")
            spec = load_json(spec_path, errors, location)
            if spec.get("chartId") != item.get("chartId"):
                errors.append(f"chart {location}: chartId does not match manifest")
            if item.get("chartId") in seen:
                errors.append(f"duplicate chartId {item.get('chartId')}")
            seen.add(str(item.get("chartId")))
            for message in validate_chart(spec_path, spec_path.parent.parent)[0]:
                errors.append(f"chart {location}: {message}")
            if blueprint:
                if spec.get("slideId") not in slide_ids:
                    errors.append(f"chart {location}: slideId {spec.get('slideId')!r} is not in the Blueprint")
                unknown = set(spec.get("claimIds", [])) - claim_ids
                if unknown:
                    errors.append(f"chart {location}: claimIds {sorted(unknown)} are not in the Blueprint")
            if spec.get("dataStatus") in {"synthetic", "modelled"} and not manifest.get("syntheticData"):
                warnings.append(f"chart {location} uses {spec.get('dataStatus')} data: list it in syntheticData")
    blockers = manifest.get("reviewBlockers", [])
    if version == "1.2" and not isinstance(blockers, list):
        errors.append("reviewBlockers must be an array")
    if status == "approved" and version == "1.2":
        if any(qa.get(section) != "pass" for section in ("semantic", "visual", "technical")):
            errors.append("approved build requires pass in all QA sections")
        if charts and qa.get("data") != "pass":
            errors.append("approved build with charts requires qa.data = pass")
        if blockers:
            errors.append("approved build cannot contain reviewBlockers")
        approval = manifest.get("approval")
        if not isinstance(approval, dict) or not approval.get("approvedBy") or approval.get("criteriaPassed") is not True:
            errors.append("approved build requires approval metadata")
        else:
            try:
                datetime.fromisoformat(str(approval.get("approvedAt", "")).replace("Z", "+00:00"))
            except ValueError:
                errors.append("approval.approvedAt must be an ISO date-time")
    if not any(path.is_file() for path in (root / "renders").rglob("*")):
        errors.append("renders/ must contain at least one rendered verification artifact")

    for message in warnings:
        print(f"WARNING: {message}")
    if errors:
        print("\n".join(f"ERROR: {item}" for item in errors))
        return 1
    print(f"Presentation build {version} and pipeline inputs are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
