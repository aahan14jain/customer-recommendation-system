# Django backend — Python image, deps from requirements.txt, runserver on 0.0.0.0:8001
# (Port 8001 avoids clashes with other stacks using 8000; map host with -p 8001:8001.)
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install Python dependencies first (better layer caching when only app code changes)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

# Application code (manage.py package root, inner customer_prediction_system/, predictor app, static assets)
COPY customer_prediction_system/ /app/customer_prediction_system/

# Repo-root `services/` (e.g. offer_fetcher) — on sys.path as /app (see predictor/pipeline.py)
COPY services/ /app/services/

WORKDIR /app/customer_prediction_system

EXPOSE 8001

# PostgreSQL: set POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT (see settings.py)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8001"]
