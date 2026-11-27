#!/usr/bin/env python3
"""Validate Presentation Visual DNA 1.2; accept 1.1 as legacy with warnings."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path


REQUIRED_FILES = (
    "README.md", "visual-dna-manifest.json", "principles.md", "tokens.css", "tokens.json",
    "typography.md", "composition.md", "imagery.md", "motion.md", "do-dont.md", "prompts.md",
    "references-manifest.md", "examples/README.md",
)
REQUIRED_COLORS = ("background", "surface", "text", "text-muted", "accent", "border")
REQUIRED_FONTS = ("display", "body", "technical", "fallback")
DATAVIZ_COLORS = ("focus", "focus-soft", "context", "context-strong", "negative", "negative-soft", "grid", "axis")
DATAVIZ_OPTIONAL_COLORS = ("band-poor", "band-ok", "band-good")
DATAVIZ_SIZES = ("title", "subtitle", "axis", "data-label", "annotation", "metric", "source", "meta")
DATAVIZ_STROKES = ("line", "line-context", "grid")


def load_json(path: Path, errors: list[str]) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"Cannot read valid JSON {path.name}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path.name} must contain a JSON object")
        return {}
    return value


def safe_file(root: Path, relative: object) -> Path | None:
    if not isinstance(relative, str) or not relative.strip():
        return None
    path = (root / relative).resolve()
    return path if path == root or root in path.parents else None


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_css(value: object) -> str:
    text = str(value).strip().lower().replace('"', "").replace("'", "")
    return re.sub(r"\s+", " ", text)


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
        print("Usage: validate_visual_dna.py <visual-dna-directory>")
        return 2
    root = Path(sys.argv[1]).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            errors.append(f"Missing required file: {relative}")
    if errors:
        print("\n".join(f"ERROR: {item}" for item in errors))
        return 1

    manifest = load_json(root / "visual-dna-manifest.json", errors)
    tokens = load_json(root / "tokens.json", errors)
    version = manifest.get("schemaVersion")
    if manifest.get("artifactType") != "visual-dna":
        errors.append("visual-dna-manifest.json: artifactType must be 'visual-dna'")
    if version == "1.1":
        if manifest.get("contract") != "presentation-visual-dna/1.1":
            errors.append("legacy manifest contract must be presentation-visual-dna/1.1")
        warnings.append("Legacy Visual DNA 1.1: upgrade to presentation-visual-dna/1.2 for new course materials")
    elif version == "1.2":
        if manifest.get("contract") != "presentation-visual-dna/1.2":
            errors.append("manifest contract must be presentation-visual-dna/1.2")
    else:
        errors.append("manifest schemaVersion must be '1.2' (or legacy '1.1')")

    status = manifest.get("status")
    if status not in {"draft", "review", "approved"}:
        errors.append("visual-dna-manifest.json: invalid status")
    if version == "1.2":
        if not valid_date(manifest.get("createdAt")):
            errors.append("manifest createdAt must be an ISO date")
        if not isinstance(manifest.get("owner"), str) or not manifest["owner"].strip():
            errors.append("manifest owner is required")
        if not isinstance(manifest.get("targetFormats"), list) or not manifest["targetFormats"]:
            errors.append("manifest targetFormats must be non-empty")
        if not isinstance(manifest.get("scope"), str) or not manifest["scope"].strip():
            errors.append("manifest scope is required")
        if not isinstance(manifest.get("openIssues"), list):
            errors.append("manifest openIssues must be an array")
        source = manifest.get("sourceBrief")
        if not isinstance(source, dict):
            errors.append("manifest sourceBrief must be an object")
        else:
            location = source.get("location")
            source_path = (root / location).resolve() if isinstance(location, str) and location.strip() else None
            if source_path is None or not source_path.is_file():
                errors.append(f"sourceBrief does not exist: {location!r}")
            elif digest(source_path) != source.get("sha256"):
                errors.append("sourceBrief SHA-256 does not match")
            if source.get("contract") != "visual-style-brief/1.2" or source.get("schemaVersion") != "1.2":
                errors.append("sourceBrief must use visual-style-brief/1.2")

    examples = manifest.get("examples", [])
    if not isinstance(examples, list):
        errors.append("visual-dna-manifest.json: examples must be an array")
        examples = []
    approved_examples = []
    for index, item in enumerate(examples):
        if not isinstance(item, dict):
            errors.append(f"example {index} must be an object")
            continue
        if item.get("status") == "approved":
            approved_examples.append(item)
        if version == "1.2":
            example_path = safe_file(root, item.get("path"))
            if example_path is None or not example_path.is_file():
                errors.append(f"example path does not exist or escapes package root: {item.get('path')!r}")
            elif digest(example_path) != item.get("sha256"):
                errors.append(f"example SHA-256 does not match: {item.get('path')}")
            if not isinstance(item.get("provenance"), str) or not item["provenance"].strip():
                errors.append(f"example {index} requires provenance")
            if not isinstance(item.get("allowedUsage"), str) or not item["allowedUsage"].strip():
                errors.append(f"example {index} requires allowedUsage")
            if item.get("type") not in {"title", "content", "data", "cta", "quote", "product-demo", "other"}:
                errors.append(f"example {index} has invalid type")
            if item.get("status") not in {"pending", "review", "approved"}:
                errors.append(f"example {index} has invalid status")
    if status == "approved" and len(approved_examples) < 3:
        errors.append("Approved package requires at least three approved examples")
    if status == "approved" and version == "1.2":
        source = manifest.get("sourceBrief", {})
        if not isinstance(source, dict) or source.get("status") != "approved":
            errors.append("Approved package requires approved sourceBrief")
        if manifest.get("openIssues"):
            errors.append("Approved package cannot contain openIssues")
        approval = manifest.get("approval")
        if not isinstance(approval, dict) or not approval.get("approvedBy") or not valid_date(approval.get("approvedAt"), with_time=True) or approval.get("criteriaPassed") is not True:
            errors.append("Approved package requires approval metadata")

    token_version = tokens.get("schemaVersion")
    if version == "1.2":
        if token_version != "1.2" or tokens.get("artifactType") != "visual-dna-tokens" or tokens.get("contract") != "presentation-visual-dna-tokens/1.2":
            errors.append("tokens.json must use presentation-visual-dna-tokens/1.2")
    elif token_version != "1.1":
        errors.append("legacy tokens.json schemaVersion must be '1.1'")
    colors = tokens.get("colors", {})
    fonts = tokens.get("typography", {})
    for role in REQUIRED_COLORS:
        if not isinstance(colors, dict) or not colors.get(role):
            errors.append(f"tokens.json: missing color role {role}")
    for role in REQUIRED_FONTS:
        if not isinstance(fonts, dict) or not fonts.get(role):
            errors.append(f"tokens.json: missing typography role {role}")
    for key in ("fontSizes", "spacing", "geometry", "formats"):
        if not isinstance(tokens.get(key), dict) or not tokens[key]:
            errors.append(f"tokens.json: {key} must be a non-empty object")
    if version == "1.2":
        for key in ("fontSizes", "spacing"):
            group = tokens.get(key, {})
            if not isinstance(group, dict) or len(group) < 3 or any(not isinstance(value, str) or not value.strip() for value in group.values()):
                errors.append(f"tokens.json: {key} requires at least three non-empty string values")
        geometry = tokens.get("geometry", {})
        for key in ("radius", "borderWidth", "shadow"):
            group = geometry.get(key) if isinstance(geometry, dict) else None
            if not isinstance(group, dict) or not group or any(not isinstance(value, str) or not value.strip() for value in group.values()):
                errors.append(f"tokens.json: geometry.{key} must be a non-empty string map")

    dataviz = tokens.get("dataviz")
    dataviz_colors: dict = {}
    if dataviz is not None:
        if not isinstance(dataviz, dict):
            errors.append("tokens.json: dataviz must be an object")
        else:
            dataviz_colors = dataviz.get("colors") if isinstance(dataviz.get("colors"), dict) else {}
            for role in DATAVIZ_COLORS:
                if role not in dataviz_colors:
                    errors.append(f"tokens.json: missing dataviz color role {role}")
            for role, value in dataviz_colors.items():
                if role not in DATAVIZ_COLORS + DATAVIZ_OPTIONAL_COLORS:
                    errors.append(f"tokens.json: unknown dataviz color role {role}")
                elif not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                    errors.append(f"tokens.json: dataviz color {role} must be #RRGGBB (PPTX charts need plain hex)")
            for key, roles in (("sizesPt", DATAVIZ_SIZES), ("strokePt", DATAVIZ_STROKES)):
                group = dataviz.get(key)
                for role in roles:
                    value = group.get(role) if isinstance(group, dict) else None
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                        errors.append(f"tokens.json: dataviz.{key}.{role} must be a positive number")
            number_format = dataviz.get("numberFormat")
            for key in ("locale", "thousandsSeparator", "decimalSeparator", "minusSign"):
                if not isinstance(number_format, dict) or not isinstance(number_format.get(key), str):
                    errors.append(f"tokens.json: dataviz.numberFormat.{key} is required")
            if isinstance(number_format, dict) and number_format.get("thousandsSeparator") == number_format.get("decimalSeparator"):
                errors.append("tokens.json: dataviz thousands and decimal separators must differ")

    css = (root / "tokens.css").read_text(encoding="utf-8")
    css_values = {match.group(1): match.group(2).strip() for match in re.finditer(r"--([a-z0-9-]+)\s*:\s*([^;]+);", css, re.I)}
    expected: dict[str, object] = {}
    if isinstance(colors, dict):
        selected = colors.items() if version == "1.2" else ((key, colors.get(key)) for key in REQUIRED_COLORS)
        expected.update({f"color-{key}": value for key, value in selected})
    if isinstance(fonts, dict):
        selected = fonts.items() if version == "1.2" else ((key, fonts.get(key)) for key in REQUIRED_FONTS)
        expected.update({f"font-{key}": value for key, value in selected})
    if version == "1.2":
        for json_key, prefix in (("fontSizes", "font-size"), ("spacing", "space")):
            group = tokens.get(json_key, {})
            if isinstance(group, dict):
                expected.update({f"{prefix}-{key}": value for key, value in group.items()})
        geometry = tokens.get("geometry", {})
        if isinstance(geometry, dict):
            for json_key, prefix in (("radius", "radius"), ("borderWidth", "border-width"), ("shadow", "shadow")):
                group = geometry.get(json_key, {})
                if isinstance(group, dict):
                    expected.update({f"{prefix}-{key}": value for key, value in group.items()})
    expected.update({f"dataviz-{key}": value for key, value in dataviz_colors.items()})
    for variable, value in expected.items():
        if variable not in css_values:
            errors.append(f"tokens.css: missing --{variable}")
        elif normalize_css(css_values[variable]) != normalize_css(value):
            errors.append(f"CSS/JSON token mismatch: --{variable}")

    for message in warnings:
        print(f"WARNING: {message}")
    if errors:
        print("\n".join(f"ERROR: {item}" for item in errors))
        return 1
    print(f"Visual DNA package {version} is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
