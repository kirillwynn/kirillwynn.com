# docker/Dockerfile.app
#
# FAANG-ish goals:
# - Small, secure runtime image (no Node/npm in runtime layer)
# - Deterministic Tailwind build during image build (no CDN Tailwind in prod)
# - Fast CI rebuilds via Docker layer caching
#
# Tailwind "source of truth" (committed):
#   backend/package.json
#   backend/package-lock.json              <-- required for `npm ci`
#   backend/tailwind.config.js
#   backend/app/static/css/tailwind.input.css  <-- ONLY Tailwind input (canonical)
#
# Tailwind build artifact (generated during build):
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

# 1) Install node deps deterministically.
#    `npm ci` requires a committed package-lock.json.
#    Copying only manifests first maximizes cache hits.
COPY backend/package.json backend/package-lock.json ./
RUN npm ci --no-audit --no-fund

# 2) Copy Tailwind config.
COPY backend/tailwind.config.js ./

# 3) Copy ONLY what Tailwind needs:
#    - templates + JS to scan for class usage
#    - static/css to include tailwind.input.css (the build input)
COPY backend/app/templates   ./app/templates
COPY backend/app/static/js   ./app/static/js
COPY backend/app/static/css  ./app/static/css

# 4) Defensive sanity check:
#    If tailwind.input.css is missing, fail the build early with a clear error.
RUN test -f ./app/static/css/tailwind.input.css

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
# - curl: useful for quick debug/health checks inside the container.
#   (Optional, but practical. Remove if you want an even smaller image.)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry (used only to install Python deps during image build).
RUN pip install --no-cache-dir "poetry==2.1.0"

# Copy dependency manifests first for caching
COPY backend/pyproject.toml backend/poetry.lock ./

# Install ONLY production dependencies into system site-packages (no venv).
# NOTE:
# - We do NOT run `poetry lock` here; locking should happen outside Docker and be committed.
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
