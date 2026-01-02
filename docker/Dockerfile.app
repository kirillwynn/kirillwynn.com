FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir "poetry==2.1.0"

COPY backend/pyproject.toml backend/poetry.lock ./

# Regenerate the lock file to ensure it matches pyproject dependencies added in the
# repository (network access is available during the image build stage).
RUN poetry config virtualenvs.create false \
    && poetry lock --no-interaction --no-ansi \
    && poetry install --no-root --only main --no-interaction --no-ansi

COPY backend/ ./

ENV PYTHONPATH=/app

RUN chmod +x entrypoint.sh

EXPOSE 5000

CMD ["./entrypoint.sh"]
