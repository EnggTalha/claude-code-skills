#!/usr/bin/env python3
"""Validate every skill in skills/ and rebuild CATALOG.md.

Usage:
    python tools/validate_skills.py          # validate + rewrite CATALOG.md
    python tools/validate_skills.py --check  # validate only, fail if CATALOG.md is stale

Standard library only, so it runs anywhere Python 3.8+ is installed.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
CATALOG = ROOT / "CATALOG.md"

CATEGORIES = {
    "ai-llm": "AI / LLM engineering",
    "security": "Security",
    "backend-devops": "Backend / DevOps",
    "dev-workflow": "Dev workflow",
}
REQUIRED_SECTIONS = ["When to use", "Steps", "Examples", "Pitfalls", "Verification"]
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Things a skill must never contain (we learned this the hard way).
FORBIDDEN = [
    (re.compile(r'"runOn"\s*:\s*"folderOpen"'), "auto-run on folder open"),
    (re.compile(r"\bghp_[A-Za-z0-9]{30,}"), "GitHub token"),
    (re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{30,}"), "API key"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key"),
]


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse the small YAML subset skills use: scalars plus one nested `metadata:` map."""
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        raise ValueError("SKILL.md must start with a '---' frontmatter block")
    end = text.find("\n---", 4)
    if end == -1:
        raise ValueError("frontmatter block is not closed with '---'")
    block, body = text[4:end], text[end + 4:]
    data: dict = {}
    current: dict | None = None
    for raw in block.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indented = raw.startswith((" ", "\t"))
        key, sep, value = raw.strip().partition(":")
        if not sep:
            raise ValueError(f"bad frontmatter line: {raw!r}")
        value = value.strip().strip('"').strip("'")
        if indented:
            if current is None:
                raise ValueError(f"indented line outside a map: {raw!r}")
            current[key] = value
        elif value == "":
            current = data.setdefault(key, {})
        else:
            data[key] = value
            current = None
    return data, body


def validate(skill_dir: Path) -> tuple[list[str], dict]:
    errors: list[str] = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return [f"{skill_dir.name}: missing SKILL.md"], {}
    text = skill_md.read_text(encoding="utf-8")
    try:
        fm, body = parse_frontmatter(text)
    except ValueError as exc:
        return [f"{skill_dir.name}: {exc}"], {}

    name, desc = fm.get("name", ""), fm.get("description", "")
    meta = fm.get("metadata", {}) if isinstance(fm.get("metadata"), dict) else {}
    if name != skill_dir.name:
        errors.append(f"name '{name}' must match folder '{skill_dir.name}'")
    if not NAME_RE.match(name or "") or len(name) > 64:
        errors.append("name must be kebab-case, at most 64 chars")
    if not 40 <= len(desc) <= 1024:
        errors.append(f"description must be 40-1024 chars (is {len(desc)})")
    if "use when" not in desc.lower() and "use this" not in desc.lower():
        errors.append("description should say when to use it (include 'Use when ...')")
    if meta.get("category") not in CATEGORIES:
        errors.append(f"metadata.category must be one of {sorted(CATEGORIES)}")
    if not DATE_RE.match(meta.get("added", "")):
        errors.append("metadata.added must be YYYY-MM-DD")

    headings = [h.strip().lower() for h in re.findall(r"^##\s+(.+)$", body, re.M)]
    for section in REQUIRED_SECTIONS:
        if not any(h.startswith(section.lower()) for h in headings):
            errors.append(f"missing '## {section}' section")
    if len(body.split()) < 250:
        errors.append(f"body too thin ({len(body.split())} words, need 250+)")

    for path in skill_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".md", ".py", ".sh", ".json", ".js", ".ts", ".txt", ".yml", ".yaml", ".ps1"}:
            content = path.read_text(encoding="utf-8", errors="ignore")
            for pattern, label in FORBIDDEN:
                # Docs may *describe* the folder-open trick; only real config/script files may not use it.
                if label == "auto-run on folder open" and path.suffix.lower() == ".md":
                    continue
                if pattern.search(content):
                    errors.append(f"{path.relative_to(skill_dir)}: contains {label}")

    summary = desc.split(". ")[0].rstrip(".")
    return [f"{skill_dir.name}: {e}" for e in errors], {
        "name": name, "category": meta.get("category", ""), "added": meta.get("added", ""), "summary": summary,
    }


def build_catalog(rows: list[dict]) -> str:
    lines = [
        "# Skill catalog",
        "",
        "_Auto-generated by `tools/validate_skills.py`. Do not edit by hand._",
        "",
        f"**{len(rows)} skills** so far. Newest first.",
        "",
    ]
    for key, title in CATEGORIES.items():
        count = sum(r["category"] == key for r in rows)
        lines.append(f"- {title}: {count}")
    lines += ["", "| Skill | Category | Added | What it does |", "|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (r["added"], r["name"]), reverse=True):
        summary = r["summary"].replace("|", "\\|")
        lines.append(f"| [`{r['name']}`](skills/{r['name']}/SKILL.md) | {CATEGORIES.get(r['category'], r['category'])} | {r['added']} | {summary} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    check_only = "--check" in sys.argv
    dirs = sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir()) if SKILLS_DIR.is_dir() else []
    all_errors, rows = [], []
    for d in dirs:
        errs, row = validate(d)
        all_errors += errs
        if row:
            rows.append(row)
    if all_errors:
        print("Validation failed:")
        for e in all_errors:
            print(f"  - {e}")
        return 1

    catalog = build_catalog(rows)
    if check_only:
        if not CATALOG.is_file() or CATALOG.read_text(encoding="utf-8") != catalog:
            print("CATALOG.md is out of date. Run: python tools/validate_skills.py")
            return 1
    else:
        CATALOG.write_text(catalog, encoding="utf-8", newline="\n")
    print(f"OK: {len(rows)} skills valid" + ("" if check_only else ", CATALOG.md updated"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
