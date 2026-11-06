FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --disable-pip-version-check -r requirements.txt \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app

COPY --chown=10001:10001 app.py demos.py ./
COPY --chown=10001:10001 templates/ templates/
COPY --chown=10001:10001 static/ static/

USER 10001:10001
EXPOSE 8080

# Cloud Run terminates TLS and supplies trusted forwarding headers.
CMD ["sh", "-c", "exec python -m uvicorn app:app --host 0.0.0.0 --port \"${PORT:-8080}\" --proxy-headers --forwarded-allow-ips '*'"]
