---
name: secret-scan-and-rotate
description: Find secrets committed to a repository or its full git history (.env files, API keys, tokens, private keys), stop tracking them, and produce a prioritised rotation checklist per provider. Use when the user asks whether secrets are leaked, after a repo or account compromise, before making a private repo public, or when .env files are tracked by git.
metadata:
  category: security
  added: "2026-11-18"
---

# Secret scan and rotate

Deleting a leaked key from the latest commit does **not** un-leak it. It is still in git history, in forks, and in any copy an attacker already took. This skill finds every secret, separates "stop tracking" (git hygiene) from "rotate" (the actual fix), and hands the user an ordered checklist.

## When to use

- "Did I commit any secrets?", "my repo was hacked", "can I make this repo public?"
- `git ls-files` shows `.env`, `*.pem`, `credentials.json` or `service-account*.json`
- After any account or CI compromise, to scope which keys were exposed
- **Not for:** setting up a secrets manager from scratch (that's a separate skill)

## Steps

1. **List tracked secret files** (current tree, every branch):
   ```bash
   for b in $(git for-each-ref --format='%(refname:short)' refs/heads refs/remotes); do
     git ls-tree -r --name-only "$b" | grep -E '(^|/)(\.env(\..+)?|.*\.pem|.*\.key|id_rsa|id_ed25519|credentials(\.json)?|service[-_]?account.*\.json)$' \
       | grep -vE '\.env\.(example|sample|template)$' | sed "s|^|$b: |"
   done | sort -u
   ```

2. **Scan the full history for key patterns.** Prefer gitleaks if it's installed (`gitleaks git -v --redact`). Otherwise use a grep over every commit:
   ```bash
   git log -p --all | grep -nE 'ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{50,}|sk-(proj-|ant-)?[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|xox[baprs]-[A-Za-z0-9-]+|-----BEGIN [A-Z ]*PRIVATE KEY-----|mongodb(\+srv)?://[^ ]+:[^ ]+@' \
     | cut -c1-160 | head -100
   ```
   **Print variable names and providers, never full values.** Truncate or redact matches in what you show the user.

3. **Build the exposure inventory**: read each `.env` and list only the KEY names, grouped by provider:
   ```bash
   git show HEAD:path/to/.env | cut -d= -f1 | grep -v '^#'
   ```

4. **Stop tracking (hygiene, not the fix):**
   ```bash
   git rm --cached path/to/.env            # keeps the local file
   printf '\n# secrets\n.env\n.env.*\n!.env.example\n' >> .gitignore
   cp path/to/.env path/to/.env.example && sed -i 's/=.*/=/' path/to/.env.example   # names only
   git commit -m "Stop tracking .env files"
   ```
   Warn the user: when teammates `git pull` this commit, their local `.env` is deleted, so they need to back it up first.

5. **Produce the rotation checklist**, ordered by impact:
   1. Anything that can spend money or send messages: OpenAI/Anthropic/Groq/ElevenLabs/Deepgram, Twilio, SMTP/Gmail app passwords, WhatsApp/Meta tokens
   2. Data access: database URIs (MongoDB, Postgres), Pinecone, S3/cloud keys
   3. Code access: GitHub tokens and deploy keys, npm/PyPI tokens
   4. App secrets: `SECRET_KEY`, JWT secrets, webhook secrets, admin passwords (invalidates sessions)
   For each: *where to revoke* (provider dashboard), *create new*, *update `.env` and deployment env vars*, *confirm the old key returns 401*.

6. **Decide on history rewriting.** Only rewrite (`git filter-repo --path .env --invert-paths`) if the repo is about to go public **and** every collaborator can re-clone. Rotation is still mandatory: rewriting never brings back a key that's already exposed.

## Examples

### Example 1: compromised account, 20 repos with `.env`

Scan finds `OPENAI_API_KEY` in 16 files, `MONGODB_URI` in 11, and `TWILIO_AUTH_TOKEN` in 4. Output: a table of provider → variable → repos, then the checklist starting with OpenAI and Twilio (spend), then MongoDB (data). Git hygiene commit per repo.

### Example 2: "can I make this repo public?"

There's no `.env` in the tree, but the history scan finds `sk-proj-…` in a commit from March. Answer: **not yet**. Rotate that OpenAI key, then optionally run `git filter-repo`, then make the repo public.

## Pitfalls

- Never paste full secret values into chat, commits, PR descriptions or issues.
- `git rm` without `--cached` deletes the developer's working file.
- `.env.example` must contain names only. Check it isn't a copy with real values.
- Revoking a GitHub token that the user's own CLI is using logs them out. Tell them first.
- Don't call a key "safe" because the repo is private: private repos get stolen too.

## Verification

- Re-running Step 1 shows no secret files on any branch, and `git check-ignore -v .env` confirms it's ignored.
- The checklist lists every variable found in Step 3. Nothing is silently dropped.
- For each rotated key, a test call with the **old** key fails (401/403) and the app works with the new one.
