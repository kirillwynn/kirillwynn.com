FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir "poetry==2.1.0"

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-root --only main --no-interaction --no-ansi

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
