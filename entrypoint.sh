#!/bin/sh
set -e

DB="${DATABASE_PATH:-/archive/data/archive.db}"
EXPORT="${EXPORT_DIR:-/archive/telegram_export}"

mkdir -p "$(dirname "$DB")"

if [ "${AUTO_IMPORT:-true}" = "true" ] && [ ! -s "$DB" ]; then
  echo "Database is empty. Importing Telegram export..."
  python -m app.importer --export-dir "$EXPORT" --database "$DB"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
