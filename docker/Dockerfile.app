# docker/Dockerfile.app
#
# FAANG-ish goals:
# - Small, secure runtime image
# - No Node/npm in the final (runtime) layer
# - Deterministic Tailwind build during image build (no CDN Tailwind in prod)
# - Good Docker layer caching for faster CI rebuilds
#
# Required repo files (committed):
#   backend/package.json
#   backend/package-lock.json   <-- IMPORTANT: needed for `npm ci`
#   backend/tailwind.config.js
#   backend/assets/tailwind.css
#
# Output artifact (generated during build):
#   backend/app/static/css/tailwind.css
#
# Templates should load both:
#   /static/css/tailwind.css  (generated)
#   /static/css/style.css     (your custom gruvbox, tiptap, etc.)

# --------------------------------------------------------------------
# Stage 1: Frontend build (Tailwind CSS)
# --------------------------------------------------------------------
FROM node:20-alpine AS frontend-builder

# Work directory for Tailwind build
WORKDIR /frontend

# 1) Install node deps (Tailwind CLI) deterministically.
#    `npm ci` requires *package-lock.json*.
#    Copying only manifests first maximizes layer cache hits.
COPY backend/package.json backend/package-lock.json ./
RUN npm ci --no-audit --no-fund

# 2) Copy Tailwind build inputs (config + input CSS).
COPY backend/tailwind.config.js ./
COPY backend/assets ./assets

# 3) Copy ONLY the files Tailwind needs to scan for class usage.
#    This keeps the build context smaller and improves caching.
COPY backend/app/templates ./app/templates
COPY backend/app/static/js ./app/static/js

# 4) Ensure output directory exists (defensive).
RUN mkdir -p ./app/static/css

# 5) Build Tailwind CSS into Flask static folder.
#    The npm script should write to: ./app/static/css/tailwind.css
RUN npm run build:css


# --------------------------------------------------------------------
# Stage 2: Python runtime (Flask + Gunicorn)
# --------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Good default Python runtime behavior in containers
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# App working directory inside container
WORKDIR /app

# System deps:
# - curl: useful for quick health/debug in container (optional but practical)
# - build-essential/libpq-dev: NOT needed if you use psycopg[binary] or psycopg2-binary
#   (We intentionally do NOT install heavy build toolchains in runtime.)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry (only used at build time to install deps).
RUN pip install --no-cache-dir "poetry==2.1.0"

# Copy dependency manifests first for caching
COPY backend/pyproject.toml backend/poetry.lock ./

# Install ONLY production dependencies into system site-packages (no venv).
# NOTE:
# - We do NOT run `poetry lock` here (locking should happen outside Docker and be committed).
RUN poetry config virtualenvs.create false \
    && poetry install --no-root --only main --no-interaction --no-ansi

# Copy backend source code (Flask app, templates, static, entrypoint, etc.)
COPY backend/ ./

# Copy the compiled Tailwind CSS from the frontend stage into runtime static.
# Runtime image does not include Node, but still serves the compiled CSS.
COPY --from=frontend-builder /frontend/app/static/css/tailwind.css /app/app/static/css/tailwind.css

# Ensure Python can import the "app" package from /app
ENV PYTHONPATH=/app

# Entrypoint executes gunicorn (see backend/entrypoint.sh)
RUN chmod +x entrypoint.sh

EXPOSE 5000

CMD ["./entrypoint.sh"]
