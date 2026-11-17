---
name: repo-safety-check
description: Inspect an untrusted or unfamiliar repository for code that runs automatically (VS Code tasks, npm lifecycle scripts, git hooks, CI workflows, disguised payload files) before anyone opens it in an editor or installs it. Use when the user is about to clone, open, install or review a repo they did not write, such as a job take-home task, a shared "portfolio" or a client handover.
metadata:
  category: security
  added: "2026-11-18"
---

# Repo safety check

Some attacks don't need you to run anything yourself. Opening a folder in VS Code, Cursor or Windsurf can run `.vscode/tasks.json`. `npm install` runs `preinstall` and `postinstall` scripts. A GitHub Actions workflow can send your secrets to an outside server. This skill reviews all of those **without executing anything** and gives a clear verdict: safe, suspicious or malicious.

Real campaign this catches: `.vscode/tasks.json` with `"runOn": "folderOpen"` runs `node public/fonts/fa-solid-400.woff2`. That "font" is JavaScript that steals `~/.ssh`, `.env`, cloud and AI tokens, then installs a cron job ending in `#ghc2`.

## When to use

- "Is this repo safe?", "check this repo before I open it", "I got a take-home assignment repo"
- Before `npm install`, `pip install -e .`, `make` or `docker compose up` on code from someone else
- After a security alert about a repo or account, to find the malicious files
- **Not for:** auditing dependency CVEs (use a dependency-audit skill) or a full code review

## Steps

1. **Never open the folder in an editor first.** If the repo is still remote, read it through the API without cloning:
   ```bash
   gh api repos/OWNER/REPO/git/trees/HEAD?recursive=1 --jq '.tree[].path' > /tmp/paths.txt
   gh api repos/OWNER/REPO/contents/.vscode/tasks.json --jq .content | base64 -d
   ```
   If it is already cloned, read files with `cat` or the Read tool only. Do not run scripts, builds or installs.

2. **Check every auto-run entry point:**
   | Where | What to look for |
   |---|---|
   | `.vscode/tasks.json` | `"runOn": "folderOpen"`, `"hide": true`, `"reveal": "never"`, commands that call `node`, `python`, `curl`, `powershell` |
   | `.vscode/settings.json`, `*.code-workspace` | `terminal.integrated.*` overrides, `python.defaultInterpreterPath` pointing into the repo |
   | `package.json` | `preinstall`, `install`, `postinstall`, `prepare` scripts |
   | `setup.py`, `pyproject.toml` build hooks | code that runs at install time (network, subprocess, base64) |
   | `.github/workflows/*.yml` | `secrets.*` or `github.token` sent to external URLs, `curl ... \| sh`, Telegram/Discord webhooks, `actions/github-script` that writes `ACTIONS_RUNTIME_TOKEN` to `GITHUB_ENV` |
   | `.husky/`, `.githooks/`, `.pre-commit-config.yaml` | hooks that download or execute remote code |
   | `Makefile`, `docker-compose.yml`, `Dockerfile` | `curl \| bash`, mounting `~` or `~/.ssh` |
   | `.devcontainer/` | `postCreateCommand`, `postStartCommand` |

3. **Look for disguised payloads.** Files whose content doesn't match their extension are the strongest signal:
   ```bash
   # Fonts, images or archives that are really text or script
   find . -type f \( -name '*.woff*' -o -name '*.ttf' -o -name '*.png' -o -name '*.jpg' -o -name '*.ico' \) \
     -not -path '*/node_modules/*' -exec file {} + | grep -viE 'font|image|data$'
   # Obfuscation markers
   grep -rnE 'eval\(|Function\(|atob\(|Buffer\.from\([^)]*base64|child_process|\\x[0-9a-f]{2}.{0,4}\\x' \
     --include='*.js' --include='*.cjs' --include='*.mjs' --include='*.woff2' . | grep -v node_modules | head -50
   ```

4. **Check the git history for signs of tampering.** Look for bursts of commits in identical pairs (`ci: refresh build cache` / `ci: restore`), commits that only touch `.vscode` or workflows, and branches nobody mentions (for example `wfx-docs`):
   ```bash
   git log --all --format='%h %ad %an %s' --date=iso -- .vscode .github public/fonts | head -40
   git branch -a
   ```

5. **Give a verdict** using this format:
   ```
   VERDICT: MALICIOUS | SUSPICIOUS | NO AUTO-RUN FOUND
   Findings:
   - <file>:<line> what it does and why it matters
   Safe next step: <e.g. delete these files on a clean machine, or open in a VM, or proceed>
   ```

## Examples

### Example 1: take-home assignment repo

User: "A recruiter sent me `acme/ai-engineer-task`, can you check it before I open it?"
→ Read the tree through the API. `.vscode/tasks.json` has `runOn: folderOpen` running `node public/fonts/fa-solid-400.woff2`, and `file` reports that "font" as `ASCII text`. Verdict: **MALICIOUS**. Tell the user not to open it, report it to GitHub, and that their machine is fine as long as it was never opened.

### Example 2: npm package with a postinstall

`package.json` has `"postinstall": "node scripts/setup.js"`, and `setup.js` only copies a config file. Verdict: **NO AUTO-RUN FOUND that is harmful**. Mention the postinstall anyway and suggest `npm install --ignore-scripts` if in doubt.

### Example 3: workflow that sends secrets out

`.github/workflows/audit.yml` contains a step that `curl`s `${{ secrets.OPENAI_API_KEY }}` to an external host. Verdict: **MALICIOUS**. The user should rotate that key and disable Actions on the repo.

## Pitfalls

- **Never** run `npm install`, `pip install`, `make`, tests or the payload "to see what it does".
- Don't trust commit authors or dates. Both can be forged, so judge by what the files actually do.
- The file `file` reports as "data" may still be a real binary font. Only flag files that turn out to be text or script.
- Don't stop at the first finding. Malicious repos usually have several entry points: a task, a workflow and a branch.
- If the user already opened a malicious repo, switch to incident response: take the machine offline, then rotate credentials from a **different** device.

## Verification

- Every row of the table in Step 2 was checked, and the report says "not present" for the ones that don't exist.
- The verdict lists file paths and quotes the exact line responsible.
- For a malicious verdict, the safe next step is concrete: which files to delete, and which credentials to rotate if the repo was opened.
