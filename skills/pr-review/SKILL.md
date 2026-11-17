---
name: pr-review
description: Review a pull request or local diff for correctness bugs, security issues, missing tests and maintainability, then report findings ranked by severity with exact file and line references and suggested fixes. Use when the user asks to review a PR, a branch, staged changes or "my changes before I push".
metadata:
  category: dev-workflow
  added: "2026-11-18"
---

# PR review

A useful review finds the few things that would actually break, explains why, and proposes the fix. Fifty style nits don't help. This skill keeps the review focused and backs every finding with evidence.

## When to use

- "Review PR #42", "review my branch", "check my changes before I push"
- Self-review before opening a PR
- **Not for:** formatting-only changes (run the formatter instead) or whole-repo audits

## Steps

1. **Get the diff and the context:**
   ```bash
   gh pr view 42 --json title,body,baseRefName,headRefName,files   # for a PR
   gh pr diff 42                                                    # or: git diff main...HEAD
   ```
   Read the PR description so you know the *intent*. A diff that does something other than what it claims is itself a finding.

2. **Read the surrounding code, not just the changed lines.** For each changed function, open the whole function and its callers (`grep -rn "function_name"`). Most real bugs sit at the boundary between new and existing code.

3. **Check against this list, in order:**
   1. **Correctness**: off-by-one errors, None/null handling, wrong conditions, missing `await`, exceptions swallowed, edge cases (empty list, unicode, timezone)
   2. **Security**: injection (SQL, shell, prompt), secrets in code, missing auth on new routes, unsafe deserialisation, new `.vscode/tasks.json` or workflow files (see the `repo-safety-check` skill)
   3. **Data and migrations**: schema changes without migration, backward compatibility, destructive operations
   4. **Concurrency and performance**: N+1 queries, blocking calls in async code, unbounded loops or memory
   5. **Tests**: is the new behaviour tested? Do the tests actually assert anything?
   6. **Maintainability**: duplication of an existing helper, unclear names. Only flag these when it matters.

4. **Verify each finding before reporting it.** Trace the actual code path. Run the tests or a quick snippet if possible (`pytest -q path`, `python -c ...`). Drop anything you can't back up, or label it "question" rather than "bug".

5. **Report** using this format:
   ```
   ## Summary
   One or two sentences: what the PR does and whether it's ready to merge.

   ## Findings
   1. 🔴 [bug] app/leads.py:42: `find_one` is not awaited, so the duplicate check always passes.
      Fix: `if await self.col.find_one(...)`
   2. 🟠 [security] routes/admin.py:10: new route has no auth dependency.
   3. 🟡 [tests] no test for the 409 path.

   ## Questions
   - Is `limit` meant to be unbounded?
   ```
   Severity: 🔴 must fix, 🟠 should fix, 🟡 nice to have. Put the most severe first.

6. **If asked to post the review**, use `gh pr review 42 --comment -b "..."`, or inline comments through `gh api`. Never approve or request changes on the user's behalf unless they ask.

## Examples

### Example 1: FastAPI PR adding a leads endpoint

Findings: missing `await` (🔴), no auth on the route (🟠), no 409 test (🟡). Verdict: not ready. Each finding has a one-line fix.

### Example 2: clean refactor

No bugs found after tracing the callers, and the tests pass. Report "Ready to merge" with one optional suggestion. Don't invent findings to look thorough.

## Pitfalls

- Don't review only the green lines. Missing changes (a caller not updated) are often the bug.
- Don't pad the report with style nits the linter would catch.
- Don't claim "this will crash" without tracing the path. Be precise about the condition.
- Watch for generated files, lockfiles and vendored code. Skim them for unexpected changes such as new install scripts or new dependencies, but don't line-review them.
- Never push commits or merge as part of a review unless explicitly asked.

## Verification

- Every finding has a file:line reference, the reason, and a concrete fix.
- Findings were checked against the real code path, or tests were run where possible.
- The summary says clearly whether the PR is ready to merge.
