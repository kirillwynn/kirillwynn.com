FROM python:3.12.13-slim AS dependencies

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

COPY backend/django/requirements.lock ./
RUN python -m pip install \
    --no-cache-dir \
    --no-compile \
    --target /opt/python \
    --requirement requirements.lock

FROM python:3.12.13-slim AS static-builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/python

WORKDIR /app

COPY --from=dependencies /opt/python /opt/python
COPY backend/django/ ./
RUN DJANGO_SETTINGS_MODULE=config.settings.build \
    python manage.py collectstatic --noinput --clear

FROM python:3.12.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/python \
    PATH=/opt/python/bin:${PATH}

WORKDIR /app

RUN addgroup --system --gid 10001 django \
    && adduser --system --uid 10001 --ingroup django --home /nonexistent django

COPY --from=dependencies /opt/python /opt/python
COPY --from=static-builder --chown=django:django /opt/kirillwynn/staticfiles /opt/kirillwynn/staticfiles
COPY --chown=django:django backend/django/ ./

RUN find /app /opt/python /opt/kirillwynn -type d -exec chmod 0555 {} + \
    && find /app /opt/python /opt/kirillwynn -type f -exec chmod 0444 {} +

USER django

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/api/health/', timeout=3); raise SystemExit(0 if r.status == 200 else 1)"]

CMD ["gunicorn", "--bind=0.0.0.0:8000", "--workers=2", "--access-logfile=-", "--error-logfile=-", "--capture-output", "config.wsgi:application"]
