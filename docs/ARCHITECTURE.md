# Architecture

Telegram Archive Viewer is intentionally small and self-contained.

## Components

### Importer

`app/importer.py` parses Telegram Desktop HTML pages and converts supported message information into normalized SQLite rows.

### Database

`app/database.py` manages SQLite initialization and optional FTS5 support.

The default database path is:

```text
/archive/data/archive.db
```

SQLite was chosen because an archive viewer is normally a single-instance application and should not require a separate database server.

### Web application

`app/main.py` provides:

- login/logout
- archive statistics API
- message pagination API
- search and filters
- reply-context lookup
- authenticated media serving
- health endpoint

### Frontend

The frontend is intentionally dependency-light:

```text
app/templates/index.html
app/templates/login.html
app/static/style.css
app/static/app.js
```

No frontend build pipeline is required.

## Data flow

```text
messages*.html
      │
      ▼
BeautifulSoup parser
      │
      ▼
SQLite messages table
      │
      ├── SQLite FTS5 index
      │
      ▼
FastAPI JSON endpoints
      │
      ▼
Browser UI
```

## Storage model

The normal Docker deployment uses two host-mounted directories:

```text
telegram_export/  → read-only source archive
data/             → persistent SQLite database
```

This keeps user data outside the generic application image.

## Security boundaries

Media paths are resolved against the configured export directory before being served. The application rejects resolved paths that escape that directory.

The raw export directory should never be directly exposed by Nginx, Apache, Caddy, or another public static file server.
