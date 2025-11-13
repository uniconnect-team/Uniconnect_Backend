FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

ENV DJANGO_SETTINGS_MODULE=services.media.settings

CMD ["gunicorn", "services.media.wsgi:application", "--bind", "0.0.0.0:8000"]
