# Claude Code Skills

A growing library of **detailed, practical [Claude Code](https://docs.claude.com/en/docs/claude-code) skills** for AI/LLM engineering, security, backend/DevOps and everyday development. **One new skill is added every day.**

Each skill is a step-by-step playbook that Claude loads automatically when your request matches it. It has real commands, decision rules, examples, pitfalls and a way to verify the result.

📚 **[Browse all skills → CATALOG.md](CATALOG.md)** · 🗺️ **[What's coming → ROADMAP.md](ROADMAP.md)**

## Install

Inside Claude Code:

```
/plugin marketplace add EnggTalha/claude-code-skills
/plugin install talha-skills@talha-skills
```

Then just ask naturally. For example, *"check this repo before I open it"* loads `repo-safety-check`, and *"review my RAG bot, it keeps hallucinating"* loads `rag-pipeline-review`.

**Use a single skill without the plugin:** copy its folder into `~/.claude/skills/` (personal) or `.claude/skills/` in a project:

```bash
git clone https://github.com/EnggTalha/claude-code-skills
cp -r claude-code-skills/skills/repo-safety-check ~/.claude/skills/
```

## Categories

| Category | Focus |
|---|---|
| 🤖 **AI / LLM engineering** | RAG, agents, voice bots (LiveKit), prompt evals, cost, structured output |
| 🔐 **Security** | untrusted-repo checks, secret scanning and rotation, GitHub and CI hardening |
| ⚙️ **Backend / DevOps** | FastAPI, MongoDB, Docker, deployment, observability |
| 🛠️ **Dev workflow** | PR review, testing, debugging, refactoring, docs |

## What makes these skills "detailed"

Every skill follows the same structure, checked by [`tools/validate_skills.py`](tools/validate_skills.py):

- **When to use**: the trigger situations, and when *not* to use it
- **Steps**: numbered, concrete instructions with real commands and code
- **Examples**: at least two realistic scenarios
- **Pitfalls**: the mistakes that actually happen
- **Verification**: how to prove the result works

Skills never contain secrets or anything that runs automatically when a folder is opened. The validator rejects both.

## How the daily skill works

A Windows scheduled task runs Claude Code headless every morning ([`tools/run-daily-skill.ps1`](tools/run-daily-skill.ps1)). Claude picks the next idea from [ROADMAP.md](ROADMAP.md), writes the skill to the standard in [CONTRIBUTING.md](CONTRIBUTING.md), validates it, and opens a pull request. Every skill is reviewed by a human before it's merged. The instructions are versioned in [`tools/daily-skill-prompt.md`](tools/daily-skill-prompt.md).

To set up the same schedule on your own machine (PowerShell):

```powershell
$a = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"D:\claude-code-skills\tools\run-daily-skill.ps1`""
$t = New-ScheduledTaskTrigger -Daily -At 9am
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName "daily-claude-skill" -Action $a -Trigger $t -Settings $s
```

## Contributing

Ideas and fixes are welcome. Open an issue with a skill idea, or follow [CONTRIBUTING.md](CONTRIBUTING.md) and send a PR.

## License

[MIT](LICENSE) © Talha Ahmed
