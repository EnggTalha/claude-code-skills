#!/usr/bin/env python3
"""Tiny prompt eval runner.

Usage: python run_eval.py evals/cases.jsonl prompts/v1.txt prompts/v2.txt

Reads cases (JSONL), runs each prompt file through `call_model`, scores the
outputs and prints a comparison table. Edit `call_model` for your provider.
The only network call is the one you put inside `call_model`.
"""
import json
import re
import sys
from pathlib import Path


def call_model(system_prompt: str, user_input: str) -> str:
    """Replace with your SDK call (temperature=0)."""
    raise NotImplementedError("wire up your model client here")


def score(case: dict, output: str) -> bool:
    kind = case["check"]
    if kind == "contains":
        return case["expected"].lower() in output.lower()
    if kind == "not_contains":
        return case["expected"].lower() not in output.lower()
    if kind == "regex":
        return re.search(case["expected"], output) is not None
    if kind == "json_field":
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return False
        return data.get(case["expected"]["field"]) == case["expected"]["value"]
    raise ValueError(f"unknown check: {kind}")


def main(cases_path: str, prompt_paths: list[str]) -> None:
    lines = Path(cases_path).read_text(encoding="utf-8").splitlines()
    cases = [json.loads(line) for line in lines if line.strip()]
    results = {}
    for p in prompt_paths:
        system = Path(p).read_text(encoding="utf-8")
        results[p] = {}
        for c in cases:
            try:
                results[p][c["id"]] = score(c, call_model(system, c["input"]))
            except Exception as exc:  # a crash counts as a failure, not a skip
                print(f"[{p}] {c['id']} errored: {exc}", file=sys.stderr)
                results[p][c["id"]] = False
    print(f"{'prompt':32} pass/total")
    for p, r in results.items():
        print(f"{p:32} {sum(r.values())}/{len(cases)}")
    if len(prompt_paths) == 2:
        a, b = (results[p] for p in prompt_paths)
        for cid in a:
            if a[cid] != b[cid]:
                print(f"  changed: {cid}: {'PASS' if a[cid] else 'FAIL'} -> {'PASS' if b[cid] else 'FAIL'}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2:])
