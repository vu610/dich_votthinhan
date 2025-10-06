"""SQLite helper cho việc theo dõi tiểu thuyết và chương đã tải."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

DEFAULT_DB_FILE = "novel_index.sqlite"


NOVEL_COLUMNS = (
    "id",
    "title",
    "slug",
    "author",
    "description",
    "cover_url",
    "index_url",
    "root_path",
    "last_scan_at",
    "latest_index",
    "latest_chapter_title",
    "latest_chapter_url",
    "created_at",
    "updated_at",
)


CHAPTER_COLUMNS = (
    "id",
    "novel_id",
    "chapter_index",
    "title",
    "source_url",
    "file_path",
    "downloaded_at",
    "content_hash",
)


SCHEMA_STATEMENTS = (
    """
    PRAGMA foreign_keys = ON;
    """,
    """
    CREATE TABLE IF NOT EXISTS novels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        slug TEXT NOT NULL UNIQUE,
        author TEXT,
        description TEXT,
        cover_url TEXT,
        index_url TEXT NOT NULL UNIQUE,
        root_path TEXT NOT NULL,
        last_scan_at TEXT,
        latest_index INTEGER DEFAULT 0,
        latest_chapter_title TEXT,
        latest_chapter_url TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS chapters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        novel_id INTEGER NOT NULL,
        chapter_index INTEGER NOT NULL,
        title TEXT,
        source_url TEXT NOT NULL,
        file_path TEXT NOT NULL,
        downloaded_at TEXT NOT NULL,
        content_hash TEXT,
        UNIQUE(novel_id, chapter_index),
        UNIQUE(novel_id, source_url),
        FOREIGN KEY(novel_id) REFERENCES novels(id) ON DELETE CASCADE
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_chapters_novel_id ON chapters(novel_id);
    """,
)


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)


def _connect(path: str) -> sqlite3.Connection:
    _ensure_parent(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)
    return conn


@contextmanager
def connect(path: str = DEFAULT_DB_FILE) -> Iterator[sqlite3.Connection]:
    conn = _connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_database(path: str = DEFAULT_DB_FILE) -> None:
    with connect(path):
        pass


def upsert_novel(
    conn: sqlite3.Connection,
    *,
    title: str,
    slug: str,
    index_url: str,
    root_path: str,
    author: Optional[str] = None,
    description: Optional[str] = None,
    cover_url: Optional[str] = None,
) -> int:
    """Thêm mới hoặc cập nhật thông tin truyện. Trả về id của truyện."""

    now = _now_iso()
    payload = {
        "title": title.strip(),
        "slug": slug.strip(),
        "index_url": index_url.strip(),
        "root_path": root_path.strip(),
        "author": author.strip() if author else None,
        "description": description.strip() if description else None,
        "cover_url": cover_url.strip() if cover_url else None,
        "updated_at": now,
    }

    existing = conn.execute(
        "SELECT id FROM novels WHERE index_url = ?", (payload["index_url"],)
    ).fetchone()

    if existing:
        conn.execute(
            """
            UPDATE novels
            SET title = :title,
                slug = :slug,
                author = :author,
                description = :description,
                cover_url = :cover_url,
                root_path = :root_path,
                updated_at = :updated_at
            WHERE id = :id
            """,
            {**payload, "id": existing["id"]},
        )
        return int(existing["id"])

    conn.execute(
        """
        INSERT INTO novels (
            title, slug, author, description, cover_url,
            index_url, root_path, created_at, updated_at
        ) VALUES (
            :title, :slug, :author, :description, :cover_url,
            :index_url, :root_path, :created_at, :updated_at
        )
        """,
        {
            **payload,
            "created_at": now,
        },
    )
    cursor = conn.execute("SELECT last_insert_rowid() AS id")
    return int(cursor.fetchone()["id"])


def update_novel_scan(
    conn: sqlite3.Connection,
    novel_id: int,
    *,
    last_scan_at: Optional[str],
    latest_index: Optional[int] = None,
    latest_chapter_title: Optional[str] = None,
    latest_chapter_url: Optional[str] = None,
) -> None:
    """Cập nhật thông tin lần quét gần nhất và chương mới nhất."""

    fields: Dict[str, object] = {
        "updated_at": _now_iso(),
        "id": novel_id,
    }
    assignments = ["updated_at = :updated_at"]

    if last_scan_at:
        fields["last_scan_at"] = last_scan_at
        assignments.append("last_scan_at = :last_scan_at")
    if latest_index is not None:
        fields["latest_index"] = int(latest_index)
        assignments.append("latest_index = :latest_index")
    if latest_chapter_title is not None:
        fields["latest_chapter_title"] = latest_chapter_title
        assignments.append("latest_chapter_title = :latest_chapter_title")
    if latest_chapter_url is not None:
        fields["latest_chapter_url"] = latest_chapter_url
        assignments.append("latest_chapter_url = :latest_chapter_url")

    sql = "UPDATE novels SET " + ", ".join(assignments) + " WHERE id = :id"
    conn.execute(sql, fields)


def record_chapter(
    conn: sqlite3.Connection,
    *,
    novel_id: int,
    chapter_index: int,
    title: str,
    source_url: str,
    file_path: str,
    content_hash: Optional[str],
) -> None:
    conn.execute(
        """
        INSERT INTO chapters (
            novel_id, chapter_index, title, source_url,
            file_path, downloaded_at, content_hash
        ) VALUES (
            :novel_id, :chapter_index, :title, :source_url,
            :file_path, :downloaded_at, :content_hash
        )
        ON CONFLICT(novel_id, chapter_index) DO UPDATE SET
            title = excluded.title,
            source_url = excluded.source_url,
            file_path = excluded.file_path,
            downloaded_at = excluded.downloaded_at,
            content_hash = excluded.content_hash
        """,
        {
            "novel_id": novel_id,
            "chapter_index": int(chapter_index),
            "title": title,
            "source_url": source_url,
            "file_path": file_path,
            "downloaded_at": _now_iso(),
            "content_hash": content_hash,
        },
    )


def fetch_novels(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    return conn.execute("SELECT * FROM novels ORDER BY title COLLATE NOCASE").fetchall()


def fetch_novel_by_url(conn: sqlite3.Connection, index_url: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM novels WHERE index_url = ?", (index_url,)
    ).fetchone()


def fetch_chapter_map(conn: sqlite3.Connection, novel_id: int) -> Dict[int, sqlite3.Row]:
    rows = conn.execute(
        "SELECT * FROM chapters WHERE novel_id = ? ORDER BY chapter_index",
        (novel_id,),
    ).fetchall()
    return {int(row["chapter_index"]): row for row in rows}


def latest_chapter_index(conn: sqlite3.Connection, novel_id: int) -> int:
    row = conn.execute(
        "SELECT MAX(chapter_index) AS max_idx FROM chapters WHERE novel_id = ?",
        (novel_id,),
    ).fetchone()
    return int(row["max_idx"] or 0)


def remove_chapter(
    conn: sqlite3.Connection,
    novel_id: int,
    chapter_index: int,
) -> None:
    conn.execute(
        "DELETE FROM chapters WHERE novel_id = ? AND chapter_index = ?",
        (novel_id, int(chapter_index)),
    )


__all__ = [
    "DEFAULT_DB_FILE",
    "connect",
    "ensure_database",
    "fetch_chapter_map",
    "fetch_novel_by_url",
    "fetch_novels",
    "latest_chapter_index",
    "record_chapter",
    "remove_chapter",
    "update_novel_scan",
    "upsert_novel",
]
