FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Kyiv

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot
COPY knowledge ./knowledge

RUN useradd --create-home appuser && mkdir -p /app/data && chown -R appuser /app
USER appuser

CMD ["python", "-m", "bot"]
