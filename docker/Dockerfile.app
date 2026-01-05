# docker/Dockerfile.app
#
# FAANG-style goal:
# - Keep runtime image small and secure (no Node, no build tools in prod layer)
# - Build Tailwind CSS deterministically during image build (no CDN in prod)
# - Multi-stage build: "frontend-builder" -> "python-runtime"
#
# This assumes you add these files:
#   backend/package.json
#   backend/tailwind.config.js
#   backend/assets/tailwind.css
# and update base.html to load:
#   /static/css/tailwind.css and /static/css/style.css
#
# NOTE:
# We intentionally keep Poetry in the runtime build steps but do NOT ship Node there.

# --------------------------------------------------------------------
# Stage 1: Frontend build (Tailwind CSS)
# --------------------------------------------------------------------
FROM node:20-alpine AS frontend-builder

# Workdir for frontend build artifacts
WORKDIR /frontend

# 1) Install node deps (Tailwind CLI) in a clean, reproducible way.
# We copy ONLY package.json first to leverage Docker layer caching.
COPY backend/package.json ./
RUN npm ci

# 2) Copy Tailwind config + input CSS
COPY backend/tailwind.config.js ./
COPY backend/assets ./assets

# 3) Copy templates + JS so Tailwind can scan for used classes (purge/JIT).
# IMPORTANT: Tailwind must "see" templates/JS to generate correct CSS.
COPY backend/app/templates ./app/templates
COPY backend/app/static ./app/static

# 4) Build Tailwind into Flask static folder.
# Output path MUST match what base.html will load.
RUN npm run build:css


# --------------------------------------------------------------------
# Stage 2: Python runtime (Flask + Gunicorn)
# --------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# App working directory
WORKDIR /app

# Install Poetry to manage Python deps
RUN pip install --no-cache-dir "poetry==2.1.0"

# Copy dependency manifests first (better caching)
COPY backend/pyproject.toml backend/poetry.lock ./

# Install ONLY production deps into the system site-packages (no venv)
# NOTE:
# - You were running "poetry lock" inside Docker build. That can cause nondeterminism.
# - In a mature pipeline, lock file should be generated in CI locally and committed.
#   Here we keep it simple and just install from the existing lock.
RUN poetry config virtualenvs.create false \
    && poetry install --no-root --only main --no-interaction --no-ansi

# Copy backend source code
COPY backend/ ./

# Copy the compiled Tailwind CSS from the frontend stage into runtime static.
# This keeps runtime free from Node tooling while still serving the compiled CSS.
COPY --from=frontend-builder /frontend/app/static/css/tailwind.css /app/app/static/css/tailwind.css

# Ensure Python can import "app" package from /app
ENV PYTHONPATH=/app

# Entrypoint executes gunicorn (see backend/entrypoint.sh)
RUN chmod +x entrypoint.sh

EXPOSE 5000

CMD ["./entrypoint.sh"]
