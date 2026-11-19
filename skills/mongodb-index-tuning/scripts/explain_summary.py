#!/usr/bin/env python3
"""Summarise a MongoDB explain("executionStats") JSON file and give a verdict.

Usage:
    python explain_summary.py explain.json

Get the JSON with mongosh, for example:
    mongosh "$MONGODB_URI" --quiet --eval \
      'EJSON.stringify(db.orders.find({status: "paid"}).sort({created_at: -1}).explain("executionStats"))' \
      > explain.json

Works with find and aggregate explain output, classic and slot-based (SBE)
engines, and canonical or relaxed Extended JSON. Standard library only; it only
reads the file you pass it.
"""
from __future__ import annotations

import json
import sys

NUMBER_WRAPPERS = ("$numberInt", "$numberLong", "$numberDouble", "$numberDecimal")


def num(value) -> float:
    """Turn a number or an Extended JSON number wrapper into a float."""
    if isinstance(value, dict):
        for key in NUMBER_WRAPPERS:
            if key in value:
                return float(value[key])
        return 0.0
    return float(value or 0)


def find_key(node, key):
    """Depth-first search for the first dict value stored under `key`."""
    if isinstance(node, dict):
        if key in node:
            return node[key]
        for child in node.values():
            found = find_key(child, key)
            if found is not None:
                return found
    elif isinstance(node, list):
        for child in node:
            found = find_key(child, key)
            if found is not None:
                return found
    return None


def plan_stages(plan) -> list[str]:
    """Flatten a winning plan into stage names, top to bottom."""
    stages: list[str] = []

    def walk(p):
        if not isinstance(p, dict):
            return
        if "queryPlan" in p:  # SBE wraps the classic-looking tree in queryPlan
            walk(p["queryPlan"])
            return
        if "stage" in p:
            label = p["stage"]
            if "indexName" in p:
                label += f"({p['indexName']})"
            stages.append(label)
        if "inputStage" in p:
            walk(p["inputStage"])
        for child in p.get("inputStages", []):
            walk(child)

    walk(plan)
    return stages


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    with open(sys.argv[1], encoding="utf-8") as fh:
        data = json.load(fh)

    stats = find_key(data, "executionStats")
    plan = find_key(data, "winningPlan")
    if stats is None or plan is None:
        print("No executionStats/winningPlan found. Use explain(\"executionStats\").")
        return 2

    returned = num(stats.get("nReturned"))
    keys = num(stats.get("totalKeysExamined"))
    docs = num(stats.get("totalDocsExamined"))
    millis = num(stats.get("executionTimeMillis"))
    stages = plan_stages(plan)
    ratio = docs / returned if returned else (float("inf") if docs else 0.0)

    print(f"plan:          {' -> '.join(stages) or '(unknown)'}")
    print(f"nReturned:     {returned:.0f}")
    print(f"keysExamined:  {keys:.0f}")
    print(f"docsExamined:  {docs:.0f}")
    print(f"timeMillis:    {millis:.0f}")
    print(f"docs/returned: {ratio:.1f}" if ratio != float("inf") else "docs/returned: inf (0 returned)")

    problems = []
    if any(s.startswith("COLLSCAN") for s in stages):
        problems.append("COLLSCAN: no usable index, every document is read")
    if any(s == "SORT" or s.startswith("SORT(") for s in stages):
        problems.append("in-memory SORT: index does not provide the sort order (check ESR order)")
    if ratio > 10:
        problems.append(f"examines {ratio:.0f}x more documents than it returns: index is not selective enough")
    if returned and keys / returned > 10 and docs <= returned * 2:
        problems.append("many keys per result: range field may sit before an equality/sort field")

    if problems:
        print("verdict:       NEEDS INDEX WORK")
        for p in problems:
            print(f"  - {p}")
        return 1
    covered = docs == 0 and returned > 0
    print("verdict:       OK" + (" (covered query)" if covered else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
