from __future__ import annotations

import hmac
import json
import os
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from starlette.middleware.sessions import SessionMiddleware

from .database import connect, init_db, has_fts

BASE_DIR = Path(__file__).resolve().parent
EXPORT_DIR = Path(os.getenv("EXPORT_DIR", "/archive/telegram_export")).resolve()
DATABASE_PATH = os.getenv("DATABASE_PATH", "/archive/data/archive.db")
ARCHIVE_USERNAME = os.getenv("ARCHIVE_USERNAME", "admin")
ARCHIVE_PASSWORD = os.getenv("ARCHIVE_PASSWORD", "change-me")
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-this-secret")
ARCHIVE_TITLE = os.getenv("ARCHIVE_TITLE", "Telegram Archive")

app = FastAPI(title=ARCHIVE_TITLE)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=os.getenv("COOKIE_HTTPS_ONLY", "true").lower() == "true",
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Environment(
    loader=FileSystemLoader(BASE_DIR / "templates"),
    autoescape=select_autoescape(["html", "xml"]),
)

def render(name: str, **ctx):
    tpl = templates.get_template(name)
    return HTMLResponse(tpl.render(**ctx))

def authenticated(request: Request) -> bool:
    return request.session.get("authenticated") is True

def require_auth(request: Request):
    if not authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")

@app.on_event("startup")
def startup():
    conn = connect()
    init_db(conn)
    conn.close()


@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(BASE_DIR / "static" / "favicon.svg", media_type="image/svg+xml")

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if authenticated(request):
        return RedirectResponse("/", status_code=303)
    return render("login.html", title=ARCHIVE_TITLE, error=None)

@app.post("/login", response_class=HTMLResponse)
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    user_ok = hmac.compare_digest(username, ARCHIVE_USERNAME)
    pass_ok = hmac.compare_digest(password, ARCHIVE_PASSWORD)
    if user_ok and pass_ok:
        request.session.clear()
        request.session["authenticated"] = True
        return RedirectResponse("/", status_code=303)
    return render("login.html", title=ARCHIVE_TITLE, error="Incorrect username or password.")

@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    if not authenticated(request):
        return RedirectResponse("/login", status_code=303)
    return render("index.html", title=ARCHIVE_TITLE)

def row_to_message(row) -> dict[str, Any]:
    item = dict(row)
    try:
        item["reactions"] = json.loads(item.pop("reactions_json") or "[]")
    except json.JSONDecodeError:
        item["reactions"] = []
    if item.get("media_path"):
        item["media_url"] = "/media/" + item["media_path"].lstrip("/")
    else:
        item["media_url"] = None
    if item.get("media_thumb"):
        item["media_thumb_url"] = "/media/" + item["media_thumb"].lstrip("/")
    else:
        item["media_thumb_url"] = None
    return item

@app.get("/api/stats")
def stats(request: Request):
    require_auth(request)
    conn = connect()
    total = conn.execute("SELECT COUNT(*) FROM messages WHERE is_service=0").fetchone()[0]
    senders = [
        dict(r) for r in conn.execute(
            "SELECT sender, COUNT(*) count FROM messages "
            "WHERE is_service=0 AND sender IS NOT NULL "
            "GROUP BY sender ORDER BY count DESC"
        ).fetchall()
    ]
    media = {
        r["media_type"]: r["count"]
        for r in conn.execute(
            "SELECT media_type, COUNT(*) count FROM messages "
            "WHERE is_service=0 AND media_type IS NOT NULL GROUP BY media_type"
        ).fetchall()
    }
    first = conn.execute(
        "SELECT sent_at FROM messages WHERE is_service=0 AND sent_at IS NOT NULL "
        "ORDER BY sent_at ASC LIMIT 1"
    ).fetchone()
    last = conn.execute(
        "SELECT sent_at FROM messages WHERE is_service=0 AND sent_at IS NOT NULL "
        "ORDER BY sent_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return {
        "total": total,
        "senders": senders,
        "media": media,
        "first": first["sent_at"] if first else None,
        "last": last["sent_at"] if last else None,
    }

def safe_fts_query(q: str) -> str:
    words = [w.strip() for w in re.split(r"\s+", q) if w.strip()]
    # Quote each token so punctuation in Persian/emoji does not break MATCH syntax.
    return " AND ".join('"' + w.replace('"', '""') + '"' for w in words)

@app.get("/api/messages")
def messages(
    request: Request,
    q: str = "",
    sender: str = "",
    media: str = "",
    date: str = "",
    before_id: int | None = None,
    after_id: int | None = None,
    limit: int = Query(60, ge=1, le=200),
):
    require_auth(request)
    conn = connect()

    where = ["m.is_service=0"]
    params: list[Any] = []
    joins = ""
    order = "m.id DESC"

    if q.strip():
        if has_fts(conn):
            joins = "JOIN messages_fts f ON f.rowid=m.id"
            where.append("f.messages_fts MATCH ?")
            params.append(safe_fts_query(q))
        else:
            where.append("(m.text LIKE ? OR m.sender LIKE ? OR m.media_title LIKE ?)")
            like = f"%{q}%"
            params.extend([like, like, like])

    if sender:
        where.append("m.sender=?")
        params.append(sender)

    if media:
        where.append("m.media_type=?")
        params.append(media)

    if date:
        where.append("substr(m.sent_at,1,10)=?")
        params.append(date)

    if before_id is not None:
        where.append("m.id < ?")
        params.append(before_id)
        order = "m.id DESC"

    if after_id is not None:
        where.append("m.id > ?")
        params.append(after_id)
        order = "m.id ASC"

    sql = f"""
        SELECT m.*
        FROM messages m
        {joins}
        WHERE {' AND '.join(where)}
        ORDER BY {order}
        LIMIT ?
    """
    params.append(limit + 1)
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    has_more = len(rows) > limit
    rows = rows[:limit]
    if order.endswith("ASC"):
        rows = list(rows)

    return {"items": [row_to_message(r) for r in rows], "has_more": has_more}

@app.get("/api/messages/{telegram_id}")
def message_by_telegram_id(request: Request, telegram_id: int):
    require_auth(request)
    conn = connect()
    row = conn.execute(
        "SELECT * FROM messages WHERE telegram_id=? AND is_service=0",
        (telegram_id,),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Message not found")
    return row_to_message(row)

@app.get("/api/around/{telegram_id}")
def around_message(request: Request, telegram_id: int, radius: int = Query(25, ge=5, le=100)):
    require_auth(request)
    conn = connect()
    target = conn.execute(
        "SELECT id FROM messages WHERE telegram_id=? AND is_service=0",
        (telegram_id,),
    ).fetchone()
    if not target:
        conn.close()
        raise HTTPException(404, "Message not found")

    rows = conn.execute(
        """
        SELECT * FROM messages
        WHERE is_service=0 AND id BETWEEN ? AND ?
        ORDER BY id ASC
        """,
        (target["id"] - radius, target["id"] + radius),
    ).fetchall()
    conn.close()
    return {"items": [row_to_message(r) for r in rows], "target": telegram_id}

@app.get("/api/date/{iso_date}")
def around_date(request: Request, iso_date: str):
    require_auth(request)
    conn = connect()
    row = conn.execute(
        """
        SELECT * FROM messages
        WHERE is_service=0 AND sent_at IS NOT NULL AND substr(sent_at,1,10) >= ?
        ORDER BY sent_at ASC LIMIT 1
        """,
        (iso_date,),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "No message found for this date")
    return {"telegram_id": row["telegram_id"]}

@app.get("/media/{media_path:path}")
def media_file(request: Request, media_path: str):
    require_auth(request)

    # Resolve and enforce containment so /media/ cannot escape the export directory.
    candidate = (EXPORT_DIR / media_path).resolve()
    try:
        candidate.relative_to(EXPORT_DIR)
    except ValueError:
        raise HTTPException(403, "Invalid media path")

    if not candidate.is_file():
        raise HTTPException(404, "Media not found")

    return FileResponse(candidate)
