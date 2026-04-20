# Django backend — production image (Gunicorn only; no runserver, no ENTRYPOINT override).
# Runtime: set DATABASE_URL to your Render Postgres *internal* URL (not localhost).
# Render sets PORT; bind gunicorn to 0.0.0.0:$PORT.
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

COPY customer_prediction_system/ /app/customer_prediction_system/
COPY services/ /app/services/

WORKDIR /app/customer_prediction_system

EXPOSE 10000

CMD ["sh", "-c", "python manage.py migrate && python manage.py collectstatic --noinput && python manage.py load_data --file predictor/data/dataset1.csv && python manage.py sync_customer_accounts --password 1234 --reset-password && exec gunicorn customer_prediction_system.wsgi:application --bind 0.0.0.0:$PORT"]
