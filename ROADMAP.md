# Roadmap

The daily routine picks the **first unchecked item** from a category different from yesterday's skill, writes it, and ticks it here in the same PR. When fewer than 10 items are left unchecked, it adds 10 new ideas.

Format: `- [ ] skill-name: one-line idea`

## AI / LLM engineering (`ai-llm`)

- [x] rag-pipeline-review: review a RAG pipeline end to end and fix retrieval first
- [ ] prompt-eval-harness: build a small JSONL eval set and a scorer to compare prompts and models
- [ ] livekit-voice-agent: scaffold a LiveKit voice agent (STT → LLM → TTS) with SIP inbound/outbound
- [ ] langgraph-agent: build a tool-using LangGraph agent with state, retries and human-in-the-loop
- [ ] llm-cost-audit: find token waste (long prompts, no caching, wrong model) and estimate savings
- [ ] prompt-caching: restructure prompts for Anthropic/OpenAI prompt caching and measure hit rate
- [ ] structured-output: get reliable JSON from LLMs with schemas, validation and repair loops
- [ ] multilingual-bot-testing: test Urdu/Arabic/English bots for language switching and RTL issues
- [ ] tool-calling-debug: diagnose why an agent calls the wrong tool or loops
- [ ] embedding-model-migration: switch embedding models safely with dual-index and backfill
- [ ] chatbot-guardrails: add input/output guardrails, PII redaction and prompt-injection defences
- [ ] mcp-server-scaffold: build a small MCP server exposing a project's API to Claude
- [ ] ocr-document-pipeline: extract text and tables from scanned PDFs and images for RAG
- [ ] llm-observability: add tracing (latency, tokens, cost, errors) to LLM calls
- [ ] whatsapp-bot-flow: design and test a WhatsApp chatbot conversation flow with a fallback to a human agent

## Security (`security`)

- [x] repo-safety-check: inspect an untrusted repo for auto-run code before opening it
- [x] secret-scan-and-rotate: find committed secrets and produce a rotation checklist
- [ ] github-account-hardening: audit tokens, SSH keys, OAuth apps, 2FA and security log
- [ ] github-actions-hardening: pin actions, least-privilege `permissions`, no secrets in PR workflows
- [ ] dependency-audit: run pip-audit/npm audit, triage CVEs and plan upgrades
- [ ] incident-response-dev-machine: steps after a dev machine runs malware
- [ ] env-secrets-management: move from `.env` files to a secrets manager with rotation
- [ ] api-auth-review: review JWT/session handling, password hashing and rate limits
- [ ] prompt-injection-review: test an LLM app for prompt injection and data exfiltration
- [ ] docker-image-hardening: non-root user, minimal base image, no secrets in layers
- [ ] git-history-secret-purge: safely rewrite history with git filter-repo and coordinate re-clones
- [ ] webhook-security: verify signatures, replay protection and idempotency
- [ ] cors-and-headers: set CORS and security headers correctly for an API and frontend
- [ ] supply-chain-check: verify a new npm/PyPI package before adding it
- [ ] mongodb-security: auth, network access rules, least-privilege users, backup encryption

## Backend / DevOps (`backend-devops`)

- [x] fastapi-endpoint: add a validated, tested FastAPI endpoint
- [ ] dockerize-python-app: Dockerfile + compose for a FastAPI/Flask app, with a small image size
- [ ] mongodb-index-tuning: find slow queries with explain() and add the right indexes
- [ ] deploy-fly-io: deploy a Python API to Fly.io with secrets and health checks
- [ ] vercel-nextjs-deploy: deploy a Next.js frontend with env vars and preview deployments
- [ ] background-jobs: move slow work into Celery/RQ/arq with retries
- [ ] api-pagination-filtering: cursor pagination, filtering and sorting done right
- [ ] structured-logging: JSON logs with request ids, and no secrets or PII in logs
- [ ] healthchecks-and-readiness: liveness/readiness endpoints and graceful shutdown
- [ ] websocket-streaming: stream LLM tokens over WebSocket/SSE from FastAPI
- [ ] nginx-reverse-proxy: put an app behind nginx with TLS and websockets
- [ ] database-backup-restore: automate MongoDB/Postgres backups and test a restore
- [ ] rate-limiting: per-user and per-IP rate limits for an API
- [ ] config-with-pydantic-settings: typed settings from env with validation
- [ ] linux-server-setup: harden and set up a fresh VPS for deployments

## Dev workflow (`dev-workflow`)

- [x] pr-review: review a PR or diff and rank findings by severity
- [ ] write-tests-for-legacy-code: add characterization tests before refactoring
- [ ] debug-failing-test: a systematic loop to reproduce, isolate and fix
- [ ] git-branch-cleanup: find and safely delete merged and stale branches
- [ ] conventional-commits: write clear commit messages and changelogs
- [ ] refactor-safely: small steps, tests green, behaviour unchanged
- [ ] readme-writer: write a README a new developer can follow in 10 minutes
- [ ] python-project-setup: pyproject, ruff, mypy, pytest and pre-commit in one go
- [ ] performance-profiling: profile Python with cProfile/py-spy and fix hot spots
- [ ] code-onboarding-map: produce an architecture map of an unfamiliar codebase
- [ ] dependency-upgrade: upgrade a major dependency with a test-backed plan
- [ ] error-message-triage: turn a stack trace into root cause and fix
- [ ] notebook-to-module: turn a Jupyter notebook into a tested Python package
- [ ] api-client-generator: generate a typed client from an OpenAPI spec
- [ ] release-checklist: version bump, changelog, tag and release notes
