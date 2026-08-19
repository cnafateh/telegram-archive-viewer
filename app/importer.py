from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

from bs4 import BeautifulSoup, Tag

from .database import connect, init_db, has_fts

MESSAGE_FILE_RE = re.compile(r"^messages(?:(\d+))?\.html$", re.I)
MESSAGE_ID_RE = re.compile(r"message-?(\d+)$")
REPLY_ID_RE = re.compile(r"(?:go_to_message|message)(\d+)")
DATE_FORMAT = "%d.%m.%Y %H:%M:%S UTC%z"


def natural_message_file_key(path: Path):
    m = MESSAGE_FILE_RE.match(path.name)
    if not m:
        return (10**9, path.name)
    return (1 if m.group(1) is None else int(m.group(1)), path.name)


def clean_text(node: Tag | None) -> str | None:
    if not node:
        return None
    text = node.get_text("\n", strip=True)
    return text if text else None


def parse_datetime(body: Tag) -> str | None:
    date_node = body.select_one(".date.details[title]")
    if not date_node:
        return None
    raw = (date_node.get("title") or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.strptime(raw, DATE_FORMAT)
        return dt.isoformat()
    except ValueError:
        # Preserve a useful sortable-ish value if Telegram changes the label format.
        return raw


def media_info(message: Tag) -> dict:
    result = {
        "media_type": None,
        "media_path": None,
        "media_thumb": None,
        "media_title": None,
        "media_status": None,
    }

    media = message.select_one(".media_wrap")
    if not media:
        return result

    classes = set()
    for tag in media.find_all(True):
        classes.update(tag.get("class") or [])

    type_map = [
        ("media_photo", "photo"),
        ("media_video", "video"),
        ("media_video_file", "video"),
        ("media_voice_message", "voice"),
        ("media_audio_file", "audio"),
        ("media_file", "file"),
        ("media_contact", "contact"),
        ("media_location", "location"),
        ("media_live_location", "location"),
        ("media_sticker", "sticker"),
    ]
    for cls, name in type_map:
        if cls in classes:
            result["media_type"] = name
            break

    # Telegram exports put the original media path in href/src.
    candidates = []
    for tag in media.find_all(["a", "img", "video", "audio", "source"]):
        for attr in ("href", "src"):
            value = tag.get(attr)
            if value:
                candidates.append((tag.name, attr, unquote(value)))

    ignored_prefixes = ("http://", "https://", "tg://", "javascript:")
    paths = [v for _, _, v in candidates if not v.lower().startswith(ignored_prefixes)]

    if paths:
        preferred = next(
            (p for p in paths if not any(x in p.lower() for x in ("thumb", "preview"))),
            paths[0],
        )
        result["media_path"] = preferred.lstrip("./")

        thumb = next(
            (p for p in paths if any(x in p.lower() for x in ("thumb", "preview"))),
            None,
        )
        result["media_thumb"] = thumb.lstrip("./") if thumb else None

    result["media_title"] = clean_text(media.select_one(".title"))
    result["media_status"] = clean_text(media.select_one(".status"))

    # A sticker is sometimes exported as a plain .webp image rather than a media_sticker class.
    if result["media_path"] and result["media_path"].lower().startswith("stickers/"):
        result["media_type"] = "sticker"

    return result


def parse_reactions(message: Tag) -> list[dict]:
    items = []
    for reaction in message.select(".reactions .reaction"):
        emoji = clean_text(reaction.select_one(".emoji"))
        count_node = reaction.select_one(".count")
        count = None
        if count_node:
            raw = clean_text(count_node)
            if raw:
                try:
                    count = int(raw)
                except ValueError:
                    count = raw

        users = []
        for pic in reaction.select(".userpic .initials[title]"):
            title = (pic.get("title") or "").strip()
            if title:
                users.append(title)

        if emoji:
            items.append({"emoji": emoji, "count": count, "users": users})
    return items


def parse_reply_to(message: Tag) -> int | None:
    link = message.select_one(".reply_to a")
    if not link:
        return None

    blob = " ".join([
        link.get("href") or "",
        link.get("onclick") or "",
    ])
    m = REPLY_ID_RE.search(blob)
    return int(m.group(1)) if m else None


def parse_forwarded_from(message: Tag) -> str | None:
    forwarded = message.select_one(".forwarded.body .from_name")
    if not forwarded:
        return None
    # Drop the appended date text if present.
    clone = BeautifulSoup(str(forwarded), "html.parser")
    for d in clone.select(".date.details"):
        d.decompose()
    return clean_text(clone)


def parse_file(path: Path):
    with path.open("r", encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f, "html.parser")

    current_date_label = None
    last_sender = None

    history = soup.select_one(".history") or soup
    for node in history.find_all("div", class_="message", recursive=True):
        classes = set(node.get("class") or [])
        is_service = "service" in classes

        if is_service:
            label = clean_text(node.select_one(".body.details"))
            if label:
                current_date_label = label

            node_id = node.get("id") or ""
            m = MESSAGE_ID_RE.search(node_id)
            telegram_id = int(m.group(1)) if m else None
            yield {
                "telegram_id": telegram_id,
                "source_file": path.name,
                "sender": None,
                "sent_at": None,
                "date_label": current_date_label,
                "text": label,
                "html_text": None,
                "reply_to": None,
                "forwarded_from": None,
                "media_type": None,
                "media_path": None,
                "media_thumb": None,
                "media_title": None,
                "media_status": None,
                "reactions_json": "[]",
                "is_service": 1,
            }
            continue

        node_id = node.get("id") or ""
        m = MESSAGE_ID_RE.search(node_id)
        if not m:
            continue
        telegram_id = int(m.group(1))

        body = node.select_one(":scope > .body") or node.select_one(".body")
        sender = clean_text(body.select_one(":scope > .from_name") if body else None)
        if sender:
            last_sender = sender
        else:
            sender = last_sender

        text_node = body.select_one(":scope > .text") if body else None
        text = clean_text(text_node)
        html_text = str(text_node.decode_contents()) if text_node else None

        media = media_info(node)
        reactions = parse_reactions(node)

        yield {
            "telegram_id": telegram_id,
            "source_file": path.name,
            "sender": sender,
            "sent_at": parse_datetime(body or node),
            "date_label": current_date_label,
            "text": text,
            "html_text": html_text,
            "reply_to": parse_reply_to(node),
            "forwarded_from": parse_forwarded_from(node),
            **media,
            "reactions_json": json.dumps(reactions, ensure_ascii=False),
            "is_service": 0,
        }


def import_archive(export_dir: Path, database: Path, reset: bool = False):
    export_dir = export_dir.resolve()
    database = database.resolve()

    if not export_dir.exists():
        raise SystemExit(f"Export directory not found: {export_dir}")

    message_files = sorted(
        [p for p in export_dir.iterdir() if p.is_file() and MESSAGE_FILE_RE.match(p.name)],
        key=natural_message_file_key,
    )
    if not message_files:
        raise SystemExit(
            f"No messages*.html files found in {export_dir}. "
            "Copy the Telegram export into telegram_export/."
        )

    if reset and database.exists():
        database.unlink()

    conn = connect(str(database))
    init_db(conn)

    columns = [
        "telegram_id", "source_file", "sender", "sent_at", "date_label", "text",
        "html_text", "reply_to", "forwarded_from", "media_type", "media_path",
        "media_thumb", "media_title", "media_status", "reactions_json", "is_service"
    ]
    placeholders = ",".join("?" for _ in columns)
    insert_sql = f"""
        INSERT INTO messages ({",".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT(telegram_id) DO UPDATE SET
        source_file=excluded.source_file,
        sender=excluded.sender,
        sent_at=excluded.sent_at,
        date_label=excluded.date_label,
        text=excluded.text,
        html_text=excluded.html_text,
        reply_to=excluded.reply_to,
        forwarded_from=excluded.forwarded_from,
        media_type=excluded.media_type,
        media_path=excluded.media_path,
        media_thumb=excluded.media_thumb,
        media_title=excluded.media_title,
        media_status=excluded.media_status,
        reactions_json=excluded.reactions_json,
        is_service=excluded.is_service
    """

    imported = 0
    for index, html_file in enumerate(message_files, 1):
        batch = []
        for row in parse_file(html_file):
            # Service-message IDs can collide across files; keep only dated separators that have no usable ID.
            if row["is_service"] and row["telegram_id"] is not None:
                row["telegram_id"] = -(index * 1_000_000 + row["telegram_id"])
            batch.append(tuple(row[c] for c in columns))

        conn.executemany(insert_sql, batch)
        conn.commit()
        imported += len(batch)
        print(f"[{index}/{len(message_files)}] {html_file.name}: {len(batch)} records")

    # Rebuild FTS so updates made through UPSERT are always reflected correctly.
    if has_fts(conn):
        try:
            conn.execute("INSERT INTO messages_fts(messages_fts) VALUES('rebuild')")
            conn.commit()
        except Exception:
            pass

    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES('imported_files', ?)",
        (str(len(message_files)),)
    )
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES('imported_records', ?)",
        (str(imported),)
    )
    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM messages WHERE is_service=0").fetchone()[0]
    print(f"Done. {total} chat messages are available in {database}")


def main():
    parser = argparse.ArgumentParser(description="Import Telegram HTML export into SQLite")
    parser.add_argument("--export-dir", default="/archive/telegram_export")
    parser.add_argument("--database", default="/archive/data/archive.db")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    import_archive(Path(args.export_dir), Path(args.database), args.reset)


if __name__ == "__main__":
    main()
