# Daily skill routine: instructions

You are adding **exactly one** new Claude Code skill to this repository today, then opening a pull request.

1. **Pick the skill.**
   - Read `ROADMAP.md`. Find the category of the most recently added skill (newest `metadata.added` in `CATALOG.md`).
   - Pick the first unchecked `- [ ]` item from a **different** category, rotating in this order: ai-llm → security → backend-devops → dev-workflow → ai-llm.
   - If an open PR already adds that skill (`gh pr list --state open`), take the next item instead.

2. **Write the skill.**
   - Create `skills/<name>/SKILL.md` from `templates/SKILL.template.md`, following every rule in `CONTRIBUTING.md`.
   - Set `metadata.category` and `metadata.added` to today's date (UTC, YYYY-MM-DD).
   - Make it genuinely detailed: concrete commands and code that work as written, decision rules, at least two realistic examples, real pitfalls, and verification steps with expected output. Look at the existing skills in `skills/` for the quality bar.
   - Add `reference.md` or `scripts/` only if they clearly help. Scripts must be small, readable, standard-library where possible, and must not make network calls unless the skill is explicitly about that.
   - Never include secrets, real customer data, `.vscode/tasks.json`, GitHub workflow files or anything that runs automatically.

3. **Validate.** Run `python tools/validate_skills.py`. Fix every error and re-run until it prints `OK`. This also regenerates `CATALOG.md`.

4. **Update the roadmap.** Tick the item (`- [x]`). If fewer than 10 unchecked items remain in total, append 10 new, specific, non-duplicate ideas spread across the four categories.

5. **Open the PR.**
   - Branch: `skill/<YYYY-MM-DD>-<name>`
   - Commit message: `Add skill: <name>`
   - PR title: `Add skill: <name>`
   - PR body: what the skill does, when it triggers, the category, a short list of the sections, and the validator output.
   - Do **not** push to `main`, merge, or change any other skill.
   - Do **not** add `Co-Authored-By` trailers or "Generated with Claude Code" lines to commits or the PR body.

If anything blocks you (validation can't pass, or there's no roadmap item left), open the PR anyway as a draft and explain the problem in the body.
