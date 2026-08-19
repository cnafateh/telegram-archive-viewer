from pathlib import Path

from app.database import connect, init_db
from app.importer import import_archive, parse_file

FIXTURE = Path(__file__).parent / "fixtures" / "messages.html"


def test_parse_telegram_html_fixture():
    rows = list(parse_file(FIXTURE))
    chat_rows = [row for row in rows if not row["is_service"]]

    assert len(chat_rows) == 2
    assert chat_rows[0]["telegram_id"] == 1001
    assert chat_rows[0]["sender"] == "Alice"
    assert chat_rows[0]["text"] == "Hello archive"
    assert chat_rows[1]["telegram_id"] == 1002
    assert chat_rows[1]["sender"] == "Bob"
    assert chat_rows[1]["reply_to"] == 1001
    assert chat_rows[1]["media_type"] == "photo"
    assert chat_rows[1]["media_path"] == "photos/photo_1.jpg"
    assert "👍" in chat_rows[1]["reactions_json"]


def test_import_archive_creates_sqlite_database(tmp_path):
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    (export_dir / "messages.html").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")

    database = tmp_path / "archive.db"
    import_archive(export_dir, database, reset=True)

    conn = connect(str(database))
    init_db(conn)
    count = conn.execute("SELECT COUNT(*) FROM messages WHERE is_service=0").fetchone()[0]
    reply_to = conn.execute("SELECT reply_to FROM messages WHERE telegram_id=1002").fetchone()[0]
    conn.close()

    assert count == 2
    assert reply_to == 1001
