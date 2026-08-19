FROM python:3.12-slim

LABEL org.opencontainers.image.title="Telegram Archive Viewer" \
      org.opencontainers.image.description="A private, searchable web viewer for Telegram Desktop HTML exports" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /archive

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x /archive/entrypoint.sh \
    && mkdir -p /archive/data /archive/telegram_export

ENV PYTHONUNBUFFERED=1 \
    EXPORT_DIR=/archive/telegram_export \
    DATABASE_PATH=/archive/data/archive.db

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)" || exit 1

CMD ["/archive/entrypoint.sh"]
