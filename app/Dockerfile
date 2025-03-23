# Stage 1: Build the Flask application using Poetry
FROM python:3.12-slim AS builder

# Set environment variables for better Python performance
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=2.1.0

# Set the working directory
WORKDIR /app

# Install Poetry at the specified version
RUN pip install "poetry==$POETRY_VERSION"

# Copy dependency files (pyproject.toml and poetry.lock)
COPY pyproject.toml poetry.lock /app/

# Install only main dependencies without installing the current project as a package
RUN poetry config virtualenvs.create false \
    && poetry install --no-root --only main --no-interaction --no-ansi

# Copy the rest of the application source code
COPY . .

# Use the builder stage as the final image to preserve global installations
FROM builder AS final

EXPOSE 5000

# Use Gunicorn to serve the Flask app
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]