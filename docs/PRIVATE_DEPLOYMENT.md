# Private self-contained deployment

This document describes the special deployment mode where your Telegram export and prebuilt SQLite database are baked into one Docker image.

This is convenient for moving your personal archive from a laptop to a private VPS, but the resulting image contains private data.

## Warning

**Never push a private image to Docker Hub, GHCR, or another public registry.**

## Prerequisites

Your local project should contain:

```text
telegram_export/
  messages.html
  messages2.html
  ...
data/
  archive.db
```

The SQLite database should already be fully imported.

## Build for a typical x86-64 VPS

```bash
docker build \
  --platform linux/amd64 \
  -f Dockerfile.private \
  -t telegram-archive-private:1.0.0 .
```

## Test locally

```bash
docker run -d \
  --name telegram-archive-test \
  -p 8000:8000 \
  -e ARCHIVE_USERNAME=admin \
  -e ARCHIVE_PASSWORD='strong-password' \
  -e SESSION_SECRET='long-random-secret' \
  -e COOKIE_HTTPS_ONLY=false \
  telegram-archive-private:1.0.0
```

Open `http://localhost:8000`.

## Export the Docker image

```bash
docker save -o telegram-archive-private-1.0.0.tar telegram-archive-private:1.0.0
```

## Upload to the server

```bash
scp telegram-archive-private-1.0.0.tar root@SERVER_IP:/root/
```

## Load on the server

```bash
docker load -i /root/telegram-archive-private-1.0.0.tar
```

## Run behind a reverse proxy

Find the Docker network used by your reverse proxy:

```bash
docker network ls
```

Then run:

```bash
docker run -d \
  --name telegram-archive \
  --restart unless-stopped \
  --network YOUR_PROXY_NETWORK \
  -e ARCHIVE_USERNAME=admin \
  -e ARCHIVE_PASSWORD='strong-production-password' \
  -e SESSION_SECRET='long-random-production-secret' \
  -e COOKIE_HTTPS_ONLY=true \
  -e ARCHIVE_TITLE='Telegram Archive' \
  telegram-archive-private:1.0.0
```

Configure the reverse proxy to forward HTTP traffic to:

```text
telegram-archive:8000
```

Enable HTTPS and force HTTPS.
