# Writing a skill

Every skill lives in `skills/<skill-name>/SKILL.md`. Start from [`templates/SKILL.template.md`](templates/SKILL.template.md).

## The standard

A skill here must be **detailed enough that Claude can follow it without guessing**. That means:

| Requirement | Rule |
|---|---|
| Folder and `name` | kebab-case, at most 64 characters, identical to each other |
| `description` | 40–1024 characters. Says **what** it does **and when to use it** (include "Use when …"). This is what Claude reads to decide whether to load the skill, so name the trigger phrases and file types. |
| `metadata.category` | one of `ai-llm`, `security`, `backend-devops`, `dev-workflow` |
| `metadata.added` | the date in `YYYY-MM-DD` |
| Sections | `## When to use`, `## Steps`, `## Examples`, `## Pitfalls`, `## Verification` |
| Depth | 250+ words of body, real commands and code, at least two examples |
| Safety | no secrets, no auto-run on folder open, scripts only read files unless the skill is explicitly about changing them |

Optional extras in the skill folder:
- `reference.md`: long reference material. Link it from `SKILL.md` ("see reference.md") so it's only loaded when needed.
- `scripts/`: helper scripts the steps call. Keep them small, readable and dependency-light.

## Checklist before opening a PR

```bash
python tools/validate_skills.py      # must print OK and regenerate CATALOG.md
```

- [ ] The skill is ticked in `ROADMAP.md`
- [ ] `CATALOG.md` is regenerated (the validator does this)
- [ ] The examples are realistic, and the commands work as written
- [ ] One skill per PR, on a branch named `skill/<yyyy-mm-dd>-<name>`

## Writing tips

- Write the steps as instructions to Claude ("Read X, then …"), not as an essay.
- Prefer decision rules ("if hit rate < 80%, fix retrieval first") over vague advice.
- Put the most common mistake in **Pitfalls**. That's where most of a skill's value is.
- **Verification** must describe evidence: a command, an expected output, a test.
