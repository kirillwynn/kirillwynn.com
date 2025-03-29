FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir "poetry==2.1.0"

COPY backend/pyproject.toml backend/poetry.lock ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-root --only main --no-interaction --no-ansi

COPY backend/app/ ./app

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
