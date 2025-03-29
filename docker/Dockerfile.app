FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir "poetry==2.1.0"

COPY backend/pyproject.toml backend/poetry.lock ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-root --only main --no-interaction --no-ansi

COPY backend/app/ ./app
COPY backend/entrypoint.sh ./entrypoint.sh

RUN chmod +x ./entrypoint.sh

EXPOSE 5000

CMD ["./entrypoint.sh"]
