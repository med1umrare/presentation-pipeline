#!/usr/bin/env python3
"""Validate Presentation Blueprint 1.2; accept 1.1 as legacy with warnings."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

CHART_TYPES = {"ranked-bar", "waterfall", "variance", "slope", "dumbbell", "small-multiples", "bullet", "kpi-sparkline"}


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
    if len(sys.argv) != 2:
        print("Usage: validate_presentation_blueprint.py <presentation-blueprint.json>")
        return 2
    path = Path(sys.argv[1]).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: Cannot read valid JSON: {exc}")
        return 1
    if not isinstance(data, dict):
        print("ERROR: Blueprint must be a JSON object")
        return 1

    version = data.get("schemaVersion")
    if data.get("artifactType") != "presentation-blueprint":
        errors.append("artifactType must be 'presentation-blueprint'")
    if version == "1.1":
        warnings.append("Legacy Blueprint 1.1: upgrade to presentation-blueprint/1.2 for new course materials")
    elif version == "1.2":
        if data.get("contract") != "presentation-blueprint/1.2":
            errors.append("contract must be 'presentation-blueprint/1.2'")
    else:
        errors.append("schemaVersion must be '1.2' (or legacy '1.1')")

    status = data.get("status")
    if status not in {"draft", "review", "approved"}:
        errors.append("status must be draft, review or approved")
    if not valid_date(data.get("createdAt")):
        errors.append("createdAt must be an ISO date")
    if version == "1.2" and not nonempty(data.get("language")):
        errors.append("language is required")
    decision = data.get("decision")
    if not isinstance(decision, dict) or not isinstance(decision.get("presentationNeeded"), bool) or not nonempty(decision.get("reason")):
        errors.append("decision requires presentationNeeded:boolean and reason")
    context = data.get("context")
    for key in ("audience", "situation", "desiredOutcome", "owner", "constraints"):
        if not isinstance(context, dict) or not isinstance(context.get(key), str) or (key != "constraints" and not context[key].strip()):
            errors.append(f"context.{key} is required")
    fmt = data.get("format")
    for key in ("primary", "fallback", "reason"):
        if not isinstance(fmt, dict) or not isinstance(fmt.get(key), str) or (key != "fallback" and not fmt[key].strip()):
            errors.append(f"format.{key} is required")
    if not nonempty(data.get("centralThesis")):
        errors.append("centralThesis is required")
    if version == "1.2" and not nonempty(data.get("desiredAction")):
        errors.append("desiredAction is required")

    claims = data.get("claims")
    slides = data.get("slides")
    sources = data.get("sources")
    route = data.get("narrativeRoute")
    visual_map = data.get("visualizationMap")
    for key, value in (("claims", claims), ("slides", slides), ("narrativeRoute", route), ("visualizationMap", visual_map)):
        if not isinstance(value, list) or not value:
            errors.append(f"{key} must be a non-empty array")
    if not isinstance(sources, list):
        errors.append("sources must be an array")
        sources = []

    def ids(items: object, key: str, pattern: str) -> set[str]:
        found: list[str] = []
        if isinstance(items, list):
            for index, item in enumerate(items):
                value = item.get(key) if isinstance(item, dict) else None
                if not isinstance(value, str) or not re.fullmatch(pattern, value):
                    errors.append(f"{key} at index {index} is invalid")
                else:
                    found.append(value)
        if len(found) != len(set(found)):
            errors.append(f"{key} values must be unique")
        return set(found)

    claim_ids = ids(claims, "claimId", r"claim-[a-z0-9-]+")
    slide_ids = ids(slides, "slideId", r"slide-[a-z0-9-]+")
    source_ids = ids(sources, "sourceId", r"source-[a-z0-9-]+")
    datasets = data.get("datasets", [])
    if not isinstance(datasets, list):
        errors.append("datasets must be an array")
        datasets = []
    dataset_ids = ids(datasets, "datasetId", r"dataset-[a-z0-9-]+")
    charted: set[str] = set()
    if isinstance(claims, list):
        for item in claims:
            if not isinstance(item, dict):
                errors.append("each claim must be an object")
                continue
            refs = item.get("sourceIds")
            if not isinstance(refs, list):
                errors.append(f"{item.get('claimId', 'claim')}.sourceIds must be an array")
                continue
            missing = set(refs) - source_ids
            if missing:
                errors.append(f"{item.get('claimId')}: unknown sourceIds {sorted(missing)}")
            if item.get("status") == "confirmed" and not refs:
                errors.append(f"{item.get('claimId')}: confirmed claim requires a source")
            if version == "1.2":
                for key in ("statement", "audienceValue", "verificationOwner"):
                    if not nonempty(item.get(key)):
                        errors.append(f"{item.get('claimId')}.{key} is required")
                if not isinstance(item.get("evidence"), str):
                    errors.append(f"{item.get('claimId')}.evidence must be a string")
                if item.get("status") not in {"confirmed", "needs-verification", "working-hypothesis", "author-opinion"}:
                    errors.append(f"{item.get('claimId')}.status is invalid")
    if isinstance(slides, list):
        for item in slides:
            if not isinstance(item, dict):
                errors.append("each slide must be an object")
                continue
            missing = set(item.get("claimIds", [])) - claim_ids
            if missing:
                errors.append(f"{item.get('slideId')}: unknown claimIds {sorted(missing)}")
            if version == "1.2":
                if not isinstance(item.get("number"), int) or item["number"] < 1:
                    errors.append(f"{item.get('slideId')}.number must be a positive integer")
                for key in ("narrativeJob", "mainPoint", "visualForm"):
                    if not nonempty(item.get(key)):
                        errors.append(f"{item.get('slideId')}.{key} is required")
                if not isinstance(item.get("material"), str):
                    errors.append(f"{item.get('slideId')}.material must be a string")
    if version == "1.2" and isinstance(visual_map, list):
        for item in visual_map:
            if not isinstance(item, dict):
                errors.append("each visualizationMap item must be an object")
                continue
            if item.get("slideId") not in slide_ids:
                errors.append(f"visualizationMap references unknown slideId {item.get('slideId')!r}")
            for key in ("insight", "form"):
                if not nonempty(item.get(key)):
                    errors.append(f"visualizationMap.{key} is required")
            if not isinstance(item.get("assets"), list):
                errors.append("visualizationMap.assets must be an array")
            if "chartType" in item:
                if item["chartType"] not in CHART_TYPES:
                    errors.append(f"visualizationMap {item.get('slideId')}: chartType must be one of {sorted(CHART_TYPES)}")
                refs = item.get("datasetIds")
                if not isinstance(refs, list) or not refs:
                    errors.append(f"visualizationMap {item.get('slideId')}: chartType requires datasetIds")
                else:
                    missing = set(refs) - dataset_ids
                    if missing:
                        errors.append(f"visualizationMap {item.get('slideId')}: unknown datasetIds {sorted(missing)}")
                    charted.update(refs)

    for item in datasets:
        if not isinstance(item, dict):
            errors.append("each dataset must be an object")
            continue
        label = item.get("datasetId")
        for key in ("location", "description"):
            if not nonempty(item.get(key)):
                errors.append(f"{label}.{key} is required")
        if item.get("dataStatus") not in {"actual", "modelled", "synthetic", "pending"}:
            errors.append(f"{label}.dataStatus must be actual, modelled, synthetic or pending")
        refs = item.get("sourceIds")
        if not isinstance(refs, list):
            errors.append(f"{label}.sourceIds must be an array")
        elif set(refs) - source_ids:
            errors.append(f"{label}: unknown sourceIds {sorted(set(refs) - source_ids)}")
        location = item.get("location")
        dataset_path = path.parent / location if nonempty(location) else None
        if dataset_path is not None and dataset_path.is_file():
            declared = item.get("sha256")
            actual = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
            if declared and declared != actual:
                errors.append(f"{label}: SHA-256 does not match {location}")
            elif not declared:
                warnings.append(f"{label}: add sha256 {actual} to pin the data before approval")
        elif item.get("dataStatus") != "pending":
            warnings.append(f"{label}: file {location!r} not found next to the Blueprint")
        if status == "approved" and label in charted:
            if item.get("dataStatus") == "pending":
                errors.append(f"approved Blueprint cannot chart pending dataset {label}")
            elif dataset_path is None or not dataset_path.is_file() or not item.get("sha256"):
                errors.append(f"approved Blueprint requires an existing file and sha256 for charted dataset {label}")

    if version == "1.2":
        for item in sources:
            if not isinstance(item, dict):
                errors.append("each source must be an object")
                continue
            if not nonempty(item.get("location")):
                errors.append(f"{item.get('sourceId')}.location is required")
            if item.get("verificationStatus") not in {"verified", "unverified", "not-provided"}:
                errors.append(f"{item.get('sourceId')}.verificationStatus is invalid")

    open_issues = data.get("openIssues")
    if not isinstance(open_issues, list):
        errors.append("openIssues must be an array")
    if status == "approved":
        approval = data.get("approval")
        if version == "1.2" and (not isinstance(approval, dict) or not nonempty(approval.get("approvedBy")) or not valid_date(approval.get("approvedAt"), with_time=True) or approval.get("criteriaPassed") is not True):
            errors.append("approved Blueprint requires approval.approvedBy, approvedAt and criteriaPassed=true")
        if open_issues:
            errors.append("approved Blueprint cannot contain openIssues")

    for message in warnings:
        print(f"WARNING: {message}")
    if errors:
        print("\n".join(f"ERROR: {message}" for message in errors))
        return 1
    print(f"Presentation Blueprint {version} is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
