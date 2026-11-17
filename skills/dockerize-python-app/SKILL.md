---
name: dockerize-python-app
description: Containerise a FastAPI or Flask app with a small multi-stage Dockerfile (slim base, cached dependency layer, non-root user, healthcheck), a strict .dockerignore and a docker-compose.yml for local development with a database. Use when the user asks to dockerize, containerise or "add Docker" to a Python web app, when an image is too large or slow to rebuild, or when a Dockerfile, compose.yaml or docker-compose.yml needs review.
metadata:
  category: backend-devops
  added: "2026-11-18"
---

# Dockerize a Python web app

The goal is an image that builds fast on code-only changes, stays small (typically 150–250 MB for a FastAPI app on `python:3.12-slim`), runs as a non-root user, holds no secrets, and starts the same way locally (via compose) and in production. Match the project's existing dependency tooling instead of introducing a new one.

## When to use

- "Dockerize this API", "add a Dockerfile and compose", "run this with Postgres/Mongo locally in Docker"
- An existing image is 1 GB+, rebuilds all dependencies on every code change, or runs as root
- Reviewing a Dockerfile or compose file in a PR
- **Not for:** deep hardening of an image for production (use `docker-image-hardening`), deploying to a specific host (`deploy-fly-io`), or Kubernetes manifests

## Steps

1. **Inspect the project first.** Read and note:
   - Dependency source: `requirements.txt`, `pyproject.toml` + `uv.lock` / `poetry.lock`. Pin versions if they aren't pinned (`pip freeze` is a last resort, prefer `pip-compile` or `uv pip compile`).
   - Entry point: `grep -rn "FastAPI(\|Flask(\|create_app" --include=*.py` → the import path, e.g. `app.main:app`.
   - Python version: `requires-python` in `pyproject.toml`, `.python-version`, or CI config. Use the same minor version in the base image.
   - Native dependencies: `psycopg2` (not `-binary`), `mysqlclient`, `lxml` built from source, `cryptography` on old pip. These need build tools in the builder stage only.
   - Config: which env vars the app reads (`grep -rn "os.environ\|getenv\|BaseSettings" --include=*.py`). They go in compose `environment`/`env_file`, never in the image.
   - Existing `Dockerfile`, `.dockerignore`, `docker-compose.yml`/`compose.yaml`. Edit them rather than adding a second set.

2. **Decide the base image and server.**
   - Base: `python:3.X-slim` (Debian, glibc). Avoid `alpine` for Python: musl breaks many manylinux wheels and forces slow source builds.
   - Server: FastAPI → `uvicorn` (or `gunicorn -k uvicorn.workers.UvicornWorker` for multiple workers). Flask → `gunicorn`. Never ship `flask run` or `uvicorn --reload` as the production command.
   - Workers: start with 1 worker per container and scale containers; if you must run several, `2 × CPU + 1` for sync gunicorn, `CPU` count for uvicorn workers.

3. **Write `.dockerignore` before the Dockerfile.** Without it, `COPY . .` drags in `.git`, `.venv` and `.env` (a secret leak and a cache-buster):
   ```gitignore
   .git
   .gitignore
   .venv
   venv
   __pycache__/
   *.py[cod]
   .pytest_cache/
   .mypy_cache/
   .ruff_cache/
   .coverage
   htmlcov/
   .env
   .env.*
   !.env.example
   *.log
   node_modules/
   Dockerfile*
   docker-compose*.yml
   compose*.yaml
   .vscode/
   .idea/
   tests/
   ```
   Drop `tests/` from the list if you plan to run tests inside the image.

4. **Write a multi-stage `Dockerfile`.** Dependencies first (cached), code last:
   ```dockerfile
   # syntax=docker/dockerfile:1
   ARG PYTHON_VERSION=3.12

   FROM python:${PYTHON_VERSION}-slim AS builder
   ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
   # Build tools only exist in this stage. Remove the apt line if all deps ship wheels.
   RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev \
       && rm -rf /var/lib/apt/lists/*
   RUN python -m venv /opt/venv
   ENV PATH="/opt/venv/bin:$PATH"
   COPY requirements.txt .
   RUN pip install -r requirements.txt

   FROM python:${PYTHON_VERSION}-slim AS runtime
   ENV PYTHONDONTWRITEBYTECODE=1 \
       PYTHONUNBUFFERED=1 \
       PATH="/opt/venv/bin:$PATH"
   # Runtime libs only (libpq5 for psycopg2). Remove if not needed.
   RUN apt-get update && apt-get install -y --no-install-recommends libpq5 \
       && rm -rf /var/lib/apt/lists/*
   RUN groupadd --system app && useradd --system --gid app --no-create-home app
   WORKDIR /app
   COPY --from=builder /opt/venv /opt/venv
   COPY --chown=app:app . .
   USER app
   EXPOSE 8000
   HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
     CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"
   CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
   ```
   Notes:
   - The healthcheck uses Python's `urllib` because `slim` has no `curl`. If the app has no `/health` route, add a trivial one (`@app.get("/health") def health(): return {"status": "ok"}`).
   - Use the exec (JSON array) form of `CMD` so the server is PID 1 and receives `SIGTERM` for graceful shutdown.
   - For `pyproject.toml` + `uv.lock`, replace the two pip lines in the builder with:
     ```dockerfile
     COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv
     ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_COMPILE_BYTECODE=1
     COPY pyproject.toml uv.lock ./
     RUN uv sync --frozen --no-dev --no-install-project
     ```
     and pin the `uv` image tag to the version the project uses.

5. **Write `docker-compose.yml` for local development** (app + database, healthy-before-start):
   ```yaml
   services:
     api:
       build: .
       ports:
         - "8000:8000"
       env_file: .env            # git-ignored; commit .env.example instead
       environment:
         DATABASE_URL: postgresql://app:app@db:5432/app
       depends_on:
         db:
           condition: service_healthy
       # Dev only: live reload with the source mounted. Remove both lines for prod-like runs.
       command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
       volumes:
         - ./app:/app/app

     db:
       image: postgres:16
       environment:
         POSTGRES_USER: app
         POSTGRES_PASSWORD: app     # local-only throwaway credential
         POSTGRES_DB: app
       volumes:
         - pgdata:/var/lib/postgresql/data
       healthcheck:
         test: ["CMD-SHELL", "pg_isready -U app -d app"]
         interval: 5s
         timeout: 3s
         retries: 10

   volumes:
     pgdata:
   ```
   Inside compose the app reaches the DB at hostname `db`, not `localhost`. For MongoDB use `image: mongo:7`, `MONGO_URL: mongodb://db:27017/app` and healthcheck `["CMD", "mongosh", "--quiet", "--eval", "db.adminCommand('ping')"]`.

6. **Build, measure and run.**
   ```bash
   docker build -t myapp:dev .
   docker image ls myapp:dev                # check SIZE
   docker run --rm -p 8000:8000 --env-file .env myapp:dev
   docker compose up --build -d
   docker compose ps                        # api and db should show "healthy"
   docker compose logs -f api
   ```

7. **Report** to the user: the files added or changed, final image size, how to start it (`docker compose up --build`), the env vars it expects (point to `.env.example`), and anything you could not verify (e.g. Docker not installed in this environment).

## Examples

### Example 1: FastAPI + MongoDB voice-agent backend, image is 1.4 GB

Situation: `Dockerfile` is `FROM python:3.12`, `COPY . .`, `RUN pip install -r requirements.txt`, `CMD uvicorn app.main:app --reload`. There's no `.dockerignore`, and the repo has a 600 MB `.venv` and a `.env` with the Atlas URI.

Actions:
- Add the `.dockerignore` from Step 3. The build context drops from ~700 MB to a few MB and `.env` no longer lands in the image.
- Replace the Dockerfile with Step 4, removing both `apt-get` lines (Motor and PyMongo ship wheels). Swap the shell-form `CMD` with `--reload` for the exec-form production command.
- Compose: `db` is `mongo:7` with the `mongosh` ping healthcheck; `MONGO_URL: mongodb://db:27017/voice`.
- Tell the user the old image contained `.env`. If it was ever pushed to a registry, the Atlas password must be rotated (see `secret-scan-and-rotate`).

Result: `docker image ls` shows ~190 MB, and a code-only change rebuilds in seconds because the `pip install` layer is cached:
```
 => CACHED [builder 5/5] RUN pip install -r requirements.txt
 => [runtime 6/7] COPY --chown=app:app . .
```

### Example 2: Flask app with psycopg2 (source build) behind gunicorn

Situation: `requirements.txt` has `psycopg2==2.9.10` (not `-binary`), and the app factory is `create_app()` in `web/__init__.py`.

Actions:
- Keep `build-essential libpq-dev` in the builder and `libpq5` in the runtime stage, exactly as in Step 4.
- Set the command to:
  ```dockerfile
  CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-", "web:create_app()"]
  ```
- Add `@app.get("/health")` in the factory so the `HEALTHCHECK` passes.
- Verify the compiled extension loads without the build tools: `docker run --rm myapp:dev python -c "import psycopg2; print(psycopg2.__version__)"` prints `2.9.10 (dt dec pq3 ext lo64)`.

## Pitfalls

- **Missing `.dockerignore`** is the most common mistake. It bloats the context, busts the cache on every change, and bakes `.env` and `.git` (with history) into the image. Write it first.
- `COPY . .` before `pip install` invalidates the dependency layer on every code edit. Always copy the lock or requirements file and install first.
- Secrets in `ENV`, `ARG` or a copied `.env` stay in the image layers forever (`docker history` shows them). Pass them at runtime via `--env-file` / compose / the platform's secret store. If a build step needs a secret, use `RUN --mount=type=secret`.
- `alpine` base images cause slow, failing source builds for numpy, pandas, cryptography, grpcio. Use `slim`.
- Shell-form `CMD uvicorn ...` runs under `/bin/sh -c`, so `SIGTERM` doesn't reach the server and `docker stop` waits 10 s and then kills it. Use the exec form.
- Binding to `127.0.0.1` inside the container makes the app unreachable from the host. Bind `0.0.0.0` in the container and restrict exposure with the port mapping (`"127.0.0.1:8000:8000"`) if needed.
- `localhost` in `DATABASE_URL` inside compose points at the app container itself. Use the service name (`db`).
- `depends_on` without `condition: service_healthy` only waits for the DB container to *start*, not to accept connections, which causes flaky startup errors.
- Bind-mounting source (`volumes: ./app:/app/app`) and `--reload` are for development only. Don't leave them in a compose file used for deployment.
- Running as root: if the app writes files (uploads, SQLite), create that directory and `chown` it to `app` in the Dockerfile rather than dropping `USER app`.
- Don't add `.vscode/tasks.json`, CI workflow files or anything that auto-runs. This skill only adds `Dockerfile`, `.dockerignore`, compose and (optionally) `.env.example`.

## Verification

- `docker build -t myapp:dev .` succeeds, and a second build after editing only a `.py` file shows `CACHED` for the `pip install` (or `uv sync`) step.
- `docker image ls myapp:dev` shows a size in the expected range (roughly 150–300 MB for typical FastAPI/Flask apps on slim; investigate anything near 1 GB).
- `docker run --rm myapp:dev whoami` prints `app`, not `root`.
- `docker run --rm myapp:dev ls -a /app` lists no `.env`, `.git` or `.venv`.
- `docker history --no-trunc myapp:dev | grep -iE "secret|password|token|api_key"` returns nothing (apart from obviously placeholder names you set on purpose).
- `docker compose up --build -d` then `docker compose ps` shows both services `running (healthy)` within ~30 s.
- `curl -fsS http://localhost:8000/health` returns `{"status":"ok"}`, and `docker compose stop api` completes in about a second (graceful shutdown working), not after a 10 s kill.
