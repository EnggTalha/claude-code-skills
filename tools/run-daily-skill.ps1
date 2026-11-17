# Runs Claude Code headless to add one new skill and open a PR.
# Started daily by the Windows scheduled task "daily-claude-skill" (see README).
# Uses the Claude Code binary bundled with the VS Code extension, so no separate install is needed.

# 'Continue': git and gh write normal progress to stderr, which PowerShell 5.1 would otherwise treat as fatal
$ErrorActionPreference = 'Continue'
$repo   = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path (Split-Path -Parent $repo) 'claude-code-skills-logs'
New-Item -ItemType Directory -Force $logDir | Out-Null
$log    = Join-Path $logDir ("{0:yyyy-MM-dd_HHmm}.log" -f (Get-Date))
Start-Transcript -Path $log | Out-Null

try {
    # Newest Claude Code binary: standalone install first, then the VS Code extension's bundled copy
    $claude = (Get-Command claude -ErrorAction SilentlyContinue).Source
    if (-not $claude) {
        $claude = Get-ChildItem "$env:USERPROFILE\.vscode\extensions\anthropic.claude-code-*\resources\native-binary\claude.exe" -ErrorAction SilentlyContinue |
            Sort-Object { [version](($_.FullName -split 'claude-code-')[1] -split '-')[0] } -Descending |
            Select-Object -First 1 -ExpandProperty FullName
    }
    if (-not $claude) { throw "Claude Code binary not found" }
    Write-Output "Using $claude"

    Set-Location $repo
    git checkout main 2>&1 | Out-Null
    git pull --ff-only 2>&1 | Write-Output
    if ($LASTEXITCODE -ne 0) { throw "git pull failed" }

    # Skip if a skill PR is already open today (e.g. the laptop woke up twice)
    $today = Get-Date -Format 'yyyy-MM-dd'
    $branches = gh pr list --state all --limit 20 --json headRefName | ConvertFrom-Json | ForEach-Object { $_.headRefName }
    if ($branches | Where-Object { $_ -like "skill/$today-*" }) { Write-Output "A skill PR for $today already exists, skipping."; return }

    $prompt = @'
You maintain this repository (EnggTalha/claude-code-skills), a library of detailed Claude Code skills.
Follow tools/daily-skill-prompt.md exactly: add exactly ONE new detailed skill (next unchecked ROADMAP.md item, rotating categories), write it to the CONTRIBUTING.md standard using templates/SKILL.template.md and the existing skills as the quality bar, run `python tools/validate_skills.py` until it prints OK, tick the item in ROADMAP.md, commit on a new branch skill/<YYYY-MM-DD>-<name>, push that branch, and open a PR with `gh pr create` titled "Add skill: <name>".
Never add Co-Authored-By or Generated-with lines to commits or PRs. Never push to main, never merge, never edit other skills, never add secrets, .vscode/tasks.json or workflow files. End by printing the PR URL.
'@

    # Prompt goes in via stdin: PowerShell 5.1 mangles double quotes inside native-command arguments
    $prompt | & $claude -p `
        --allowedTools "Read" "Write" "Edit" "Glob" "Grep" "Bash(git:*)" "Bash(gh pr:*)" "Bash(python:*)" "Bash(python3:*)" "Bash(ls:*)" "Bash(mkdir:*)" "Bash(date:*)" `
        --max-turns 60
}
finally {
    Set-Location $repo
    git checkout main 2>&1 | Out-Null
    Stop-Transcript | Out-Null
}
