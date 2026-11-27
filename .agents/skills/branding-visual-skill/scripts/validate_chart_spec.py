#!/usr/bin/env python3
"""Validate presentation-chart-spec/1.0 files against their data.

Checks structure, data hash, encoding columns, type-specific invariants
(waterfall balance, bullet ranges, panel limits) and that every number in the
title and annotation can be derived from the data. Exit code 1 on any error.

Usage:
  validate_chart_spec.py <spec.json | charts-dir> [--root DIR] [--write-hashes]

data.location is resolved against --root (default: parent of the charts dir).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from itertools import combinations
from pathlib import Path

CONTRACT = "presentation-chart-spec/1.0"
TYPES = {
    "ranked-bar": ["category", "value"],
    "waterfall": ["step", "kind", "value"],
    "variance": ["category", "plan", "actual"],
    "slope": ["category", "from", "to"],
    "dumbbell": ["category", "from", "to"],
    "small-multiples": ["x", "series", "value"],
    "bullet": ["metric", "actual", "target", "poor", "ok", "max"],
    "kpi-sparkline": ["metric", "x", "value"],
}
NUMERIC = {
    "ranked-bar": ["value"],
    "waterfall": ["value"],
    "variance": ["plan", "actual"],
    "slope": ["from", "to"],
    "dumbbell": ["from", "to"],
    "small-multiples": ["value"],
    "bullet": ["actual", "target", "poor", "ok", "max"],
    "kpi-sparkline": ["value"],
}
LIMITS = {"ranked-bar": 12, "waterfall": 8, "slope": 6, "dumbbell": 10, "small-multiples": 9, "bullet": 5, "kpi-sparkline": 4}
GROUP_KEY = {"ranked-bar": "category", "small-multiples": "series", "kpi-sparkline": "metric"}
NUMBER = re.compile(r"(?<![\w\d,])[+\-−±]?\d{1,3}(?:[   ]\d{3})+(?:,\d+)?(?![\d])|(?<![\w\d,])[+\-−±]?\d+(?:,\d+)?(?![\d])")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def series_facts(values: list[float]) -> list[float]:
    first, last = values[0], values[-1]
    out = [first, last, max(values), min(values), last - first, max(values) - min(values), sum(values) / len(values)]
    if first:
        out += [(last - first) / first * 100, last / first]
    return out


def pair_facts(a: float, b: float) -> list[float]:
    out = [a, b, b - a]
    if a:
        out += [(b - a) / a * 100, b / a, b / a * 100]
    if b:
        out += [a / b]
    return out


def data_facts(kind: str, enc: dict, rows: list[dict], num) -> list[float]:
    """Values a title or annotation may legitimately quote for this chart."""
    facts: list[float] = []
    for role in NUMERIC[kind]:
        facts += [num(r, role) for r in rows]
    if isinstance(enc.get("threshold"), (int, float)):
        facts.append(float(enc["threshold"]))
    if kind == "ranked-bar":
        totals: dict[str, float] = {}
        for r in rows:
            totals[r[enc["category"]]] = totals.get(r[enc["category"]], 0) + num(r, "value")
        total = sum(totals.values())
        ranked = sorted(totals.values(), reverse=True)
        facts += ranked + [total] + [v / total * 100 for v in ranked if total]
        facts += [a - b for a, b in zip(ranked, ranked[1:])]
        facts += [a / b for a, b in zip(ranked, ranked[1:]) if b]
    elif kind == "waterfall":
        start, end = num(rows[0], "value"), num(rows[-1], "value")
        deltas = [num(r, "value") for r in rows[1:-1]]
        change = end - start
        running = start
        for d in deltas:
            running += d
            facts.append(running)
        facts += [change, change / start * 100 if start else change]
        facts += [change - d for d in deltas]
        for size in range(2, len(deltas) + 1):
            facts += [sum(c) for c in combinations(deltas, size)]
    elif kind in {"variance", "slope", "dumbbell"}:
        a_role, b_role = ("plan", "actual") if kind == "variance" else ("from", "to")
        for r in rows:
            facts += pair_facts(num(r, a_role), num(r, b_role))
    elif kind == "bullet":
        for r in rows:
            a, t = num(r, "actual"), num(r, "target")
            facts += [t - a, a - t] + ([a / t * 100] if t else [])
    elif kind in {"small-multiples", "kpi-sparkline"}:
        groups: dict[str, list[float]] = {}
        for r in rows:
            groups.setdefault(r[enc[GROUP_KEY[kind]]], []).append(num(r, "value"))
        for dm in enc.get("derived", []):
            top, bottom = groups.get(dm.get("numerator")), groups.get(dm.get("denominator"))
            if top and bottom and all(bottom):
                groups[dm.get("name", "derived")] = [t / b for t, b in zip(top, bottom)]
        for values in groups.values():
            facts += values + series_facts(values)
    return facts


def unmatched_numbers(text: str, facts: list[float], verified: set[str]) -> list[str]:
    missing = []
    for match in NUMBER.finditer(text):
        token = match.group(0)
        plain = token.replace(" ", " ").replace(" ", " ")
        if plain in verified or plain.lstrip("+-−±") in verified:
            continue
        digits = plain.lstrip("+-−±").replace(" ", "")
        if re.fullmatch(r"(19|20)\d\d", digits):
            continue  # a year, not a measured value
        value = float(digits.replace(",", "."))
        decimals = len(digits.split(",")[1]) if "," in digits else 0
        tolerance = 0.5 * 10 ** -decimals + 1e-9
        if not any(abs(abs(f) - value) <= tolerance for f in facts):
            missing.append(token)
    return missing


def validate(spec_path: Path, root: Path, write_hashes: bool = False) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read valid JSON: {exc}"], warnings
    if not isinstance(spec, dict):
        return ["chart spec must be a JSON object"], warnings

    for key in ["artifactType", "contract", "schemaVersion", "chartId", "slideId", "claimIds", "type", "title", "subtitle", "data", "units", "dataStatus"]:
        if key not in spec:
            errors.append(f"missing field: {key}")
    if errors:
        return errors, warnings
    if spec["artifactType"] != "presentation-chart-spec":
        errors.append("artifactType must be presentation-chart-spec")
    if spec["contract"] != CONTRACT or spec["schemaVersion"] != "1.0":
        errors.append(f"contract must be {CONTRACT} with schemaVersion 1.0")
    if not re.fullmatch(r"chart-[a-z0-9-]+", str(spec["chartId"])):
        errors.append("chartId must match chart-[a-z0-9-]+")
    if not re.fullmatch(r"slide-[a-z0-9-]+", str(spec["slideId"])):
        errors.append("slideId must match slide-[a-z0-9-]+")
    if not isinstance(spec["claimIds"], list) or not spec["claimIds"]:
        errors.append("claimIds must be a non-empty array")
    if spec["type"] not in TYPES:
        return errors + [f"unknown type: {spec['type']}"], warnings
    if spec["dataStatus"] not in {"actual", "modelled", "synthetic"}:
        errors.append("dataStatus must be actual | modelled | synthetic")
    if not re.search(r"\d", spec["title"]):
        warnings.append("title has no number: an action title usually states the measured conclusion")
    if spec["dataStatus"] != "actual" and not spec.get("sourceNote"):
        errors.append("non-actual data requires a visible sourceNote")
    verified_items = spec.get("verifiedNumbers", [])
    if not isinstance(verified_items, list) or any(not isinstance(v, dict) or not v.get("value") or not v.get("note") for v in verified_items):
        errors.append("verifiedNumbers items require value and note")
        verified_items = []

    data_path = root / spec["data"]["location"]
    if not data_path.is_file():
        return errors + [f"data file not found: {data_path}"], warnings
    digest = sha256(data_path)
    if spec["data"].get("sha256") != digest:
        if write_hashes:
            spec["data"]["sha256"] = digest
            spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            warnings.append("sha256 updated")
        else:
            errors.append(f"data sha256 mismatch: spec {spec['data'].get('sha256', '')[:12]}…, file {digest[:12]}…")

    enc = spec.get("encoding", {})
    rows = list(csv.DictReader(data_path.open(encoding="utf-8-sig")))
    if not rows:
        return errors + ["data file has no rows"], warnings
    columns = set(rows[0].keys())
    for role in TYPES[spec["type"]]:
        col = enc.get(role)
        if not col:
            errors.append(f"encoding.{role} is required for {spec['type']}")
        elif col not in columns:
            errors.append(f"encoding.{role} = '{col}' is not a column of {data_path.name}")
    if errors:
        return errors, warnings

    for role in NUMERIC[spec["type"]]:
        for i, row in enumerate(rows, start=2):
            try:
                float(row[enc[role]])
            except ValueError:
                errors.append(f"{data_path.name}:{i} column '{enc[role]}' is not numeric: {row[enc[role]]!r}")
    if errors:
        return errors, warnings

    def num(row: dict, role: str) -> float:
        return float(row[enc[role]])

    kind = spec["type"]
    group_key = GROUP_KEY.get(kind)
    categories = [r[enc[group_key]] for r in rows] if group_key else [r[enc.get("category") or enc.get("step") or enc.get("metric")] for r in rows]
    unique = list(dict.fromkeys(categories))
    if kind in LIMITS and len(unique) > LIMITS[kind]:
        errors.append(f"{kind} allows at most {LIMITS[kind]} items, got {len(unique)}")
    for h in spec.get("highlight", []):
        if h not in unique:
            errors.append(f"highlight '{h}' is not present in data")

    if kind == "ranked-bar":
        if enc.get("aggregate") not in (None, "sum"):
            errors.append("ranked-bar aggregate supports only 'sum'")
        if enc.get("aggregate") is None and len(unique) != len(categories):
            errors.append("duplicate categories: set encoding.aggregate = 'sum'")
        if any(num(r, "value") < 0 for r in rows):
            errors.append("ranked-bar values must be non-negative (bars start at zero)")
    elif kind == "waterfall":
        kinds = [r[enc["kind"]] for r in rows]
        if kinds[0] != "start" or kinds[-1] != "end" or any(k != "delta" for k in kinds[1:-1]):
            errors.append("waterfall rows must be: start, delta…, end")
        else:
            running = num(rows[0], "value") + sum(num(r, "value") for r in rows[1:-1])
            end = num(rows[-1], "value")
            if abs(running - end) > 10 ** -(spec["units"]["decimals"] + 1):
                errors.append(f"waterfall does not balance: start + deltas = {running:.4f}, end = {end:.4f}")
    elif kind == "variance":
        if any(num(r, "plan") == 0 for r in rows):
            errors.append("variance plan cannot be zero")
    elif kind == "bullet":
        for r in rows:
            a, t, p, o, m = (num(r, k) for k in ["actual", "target", "poor", "ok", "max"])
            if not (0 < p < o < m):
                errors.append(f"bullet '{r[enc['metric']]}': ranges must satisfy 0 < poor < ok < max")
            if not (0 <= a <= m and 0 <= t <= m):
                errors.append(f"bullet '{r[enc['metric']]}': actual and target must fit within 0..max")
    elif kind in {"small-multiples", "kpi-sparkline"}:
        lengths = {g: sum(1 for r in rows if r[enc[group_key]] == g) for g in unique}
        if len(set(lengths.values())) != 1:
            errors.append(f"every panel needs the same number of points: {lengths}")
        for dm in enc.get("derived", []):
            for part in ("numerator", "denominator"):
                if dm.get(part) not in unique:
                    errors.append(f"derived '{dm.get('name')}': {part} '{dm.get(part)}' is not a metric in data")
            if dm.get("denominator") in unique and any(
                num(r, "value") == 0 for r in rows if r[enc[group_key]] == dm["denominator"]
            ):
                errors.append(f"derived '{dm.get('name')}': denominator has zero values")
    if errors:
        return errors, warnings

    facts = data_facts(kind, enc, rows, num)
    verified = {re.sub(r"\s", " ", str(v["value"])).rstrip("%").strip() for v in verified_items}
    for field in ("title", "annotation"):
        for token in unmatched_numbers(spec.get(field, ""), facts, verified):
            errors.append(f"{field}: number '{token}' does not follow from the data; fix the text or add it to verifiedNumbers with a note")
    return errors, warnings


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    parser.add_argument("--root", default=None, help="directory that data.location is relative to (default: parent of the charts dir)")
    parser.add_argument("--write-hashes", action="store_true")
    args = parser.parse_args()
    target = Path(args.target)
    specs = sorted(target.glob("*.chart.json")) if target.is_dir() else [target]
    if not specs:
        print(f"no *.chart.json files in {target}")
        return 1
    root = Path(args.root) if args.root else (target if target.is_dir() else target.parent).parent
    failed = 0
    seen: dict[str, str] = {}
    for spec_path in specs:
        errors, warnings = validate(spec_path, root, args.write_hashes)
        try:
            chart_id = json.loads(spec_path.read_text(encoding="utf-8")).get("chartId")
        except (OSError, json.JSONDecodeError):
            chart_id = None
        if chart_id in seen:
            errors.append(f"chartId '{chart_id}' already used in {seen[chart_id]}")
        elif chart_id:
            seen[chart_id] = spec_path.name
        status = "FAIL" if errors else "ok"
        print(f"[{status}] {spec_path.name}")
        for e in errors:
            print(f"   error: {e}")
        for w in warnings:
            print(f"   warning: {w}")
        failed += bool(errors)
    print(f"\n{len(specs) - failed}/{len(specs)} chart specs valid")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
