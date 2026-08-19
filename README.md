# Telegram Archive Viewer

A private, self-hosted, searchable web viewer for **Telegram Desktop HTML exports**.

Telegram's built-in HTML export is useful as an archive, but it is not designed as a modern long-term viewer. Telegram Archive Viewer imports the exported messages into a local SQLite database and provides a responsive web interface with fast search, filters, media viewing, replies, reactions, and light/dark themes.

> This project is independent and is not affiliated with Telegram.

## Features

- Telegram Desktop **HTML export** importer
- SQLite database; no PostgreSQL, MySQL, or external database service required
- SQLite FTS5 full-text search
- Search across the complete archive
- Filter by sender, date, and content type
- Photos, videos, audio, voice messages, stickers, and files
- Reply navigation
- Reactions
- Responsive desktop/mobile interface
- Off-canvas mobile navigation
- Light and dark themes
- Password-protected access
- Original Telegram export mounted read-only by default
- Docker-first deployment
- GitHub Actions CI and tagged releases
- GHCR container publishing on releases

## Supported Telegram export format

The importer is designed for **Telegram Desktop → Export chat history → Human-readable HTML** exports.

Expected files typically look like:

```text
TelegramExport/
├── messages.html
├── messages2.html
├── messages3.html
├── ...
├── photos/
├── video_files/
├── voice_messages/
├── stickers/
└── files/
```

The project currently parses the HTML structures used for message IDs, senders, timestamps, text, replies, forwarded messages, media metadata, and reactions.

**Not currently supported:** Telegram JSON exports.

Telegram can change its export markup in future versions. If a newer export format breaks parsing, please open an issue and include a small **sanitized** HTML sample with all personal data removed.

See [docs/TELEGRAM_EXPORT.md](docs/TELEGRAM_EXPORT.md) for details.

## Quick start with Docker Compose

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/telegram-archive-viewer.git
cd telegram-archive-viewer
```

### 2. Copy your Telegram export

Copy the **contents** of the Telegram HTML export into:

```text
telegram_export/
```

Do not rename Telegram's `messages*.html` files or media directories.

### 3. Configure the app

```bash
cp .env.example .env
```

Generate a session secret:

```bash
openssl rand -hex 32
```

Edit `.env` and set at least:

```env
ARCHIVE_USERNAME=admin
ARCHIVE_PASSWORD=use-a-strong-password
SESSION_SECRET=your-generated-random-secret
ARCHIVE_TITLE=Telegram Archive
COOKIE_HTTPS_ONLY=false
```

For HTTPS production deployments, set:

```env
COOKIE_HTTPS_ONLY=true
```

### 4. Start

```bash
docker compose up -d --build
```

On the first start, the app creates:

```text
data/archive.db
```

and imports all detected `messages*.html` files. Later restarts reuse the existing SQLite database.

Watch the first import:

```bash
docker compose logs -f telegram-archive
```

Open:

```text
http://localhost:8000
```

## Updating or re-importing an archive

If you replace the Telegram export and want to rebuild the SQLite index:

```bash
docker compose down
rm -f data/archive.db
docker compose up -d
```

On Windows PowerShell:

```powershell
docker compose down
Remove-Item .\data\archive.db -ErrorAction SilentlyContinue
docker compose up -d
```

## Using the published container image

Tagged releases publish a generic image to GitHub Container Registry:

```text
ghcr.io/OWNER/telegram-archive-viewer:VERSION
```

The public image **does not contain anyone's Telegram data**. Mount your export and data directory at runtime:

```bash
docker run -d \
  --name telegram-archive \
  --restart unless-stopped \
  -p 8000:8000 \
  -v "$PWD/telegram_export:/archive/telegram_export:ro" \
  -v "$PWD/data:/archive/data" \
  -e ARCHIVE_USERNAME=admin \
  -e ARCHIVE_PASSWORD='change-this-password' \
  -e SESSION_SECRET='replace-with-a-long-random-secret' \
  -e COOKIE_HTTPS_ONLY=false \
  ghcr.io/OWNER/telegram-archive-viewer:latest
```

## Private self-contained image

If you specifically want a **single private Docker image containing your own export and SQLite database**, use `Dockerfile.private`.

> **Never push that image to a public registry. It contains your private Telegram archive.**

First make sure `data/archive.db` already exists, then:

```bash
docker build \
  --platform linux/amd64 \
  -f Dockerfile.private \
  -t telegram-archive-private:latest .
```

See [docs/PRIVATE_DEPLOYMENT.md](docs/PRIVATE_DEPLOYMENT.md).

## Security

This application is intended for private archives. Recommended production setup:

```text
Internet
   ↓
HTTPS reverse proxy
   ↓
Telegram Archive Viewer authentication
   ↓
SQLite + read-only Telegram export
```

Do not expose the raw Telegram export directory through your web server.

Read [SECURITY.md](SECURITY.md) before exposing an archive to the internet.

## Architecture

```text
Telegram Desktop HTML export
          │
          ▼
    Python importer
          │
          ▼
 SQLite + SQLite FTS5
          │
          ▼
       FastAPI
          │
          ▼
 HTML / CSS / JavaScript UI
```

More details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Development

Create a virtual environment and install development dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

Run tests:

```bash
pytest -q
```

Check the frontend JavaScript:

```bash
node --check app/static/app.js
```

## Releases

Push a semantic version tag:

```bash
git tag v1.0.0
git push origin v1.0.0
```

The release workflow will:

1. run from the version tag,
2. build the generic Docker image,
3. publish versioned and `latest` tags to GHCR,
4. create a GitHub Release with generated release notes.

See [docs/RELEASING.md](docs/RELEASING.md).

## Privacy

The repository intentionally ignores:

- `telegram_export/*`
- `data/*`
- `.env`

Before every public push, still check:

```bash
git status
git ls-files telegram_export data .env
```

No private archive file should appear in the tracked-file output.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Licensed under the [MIT License](LICENSE).
