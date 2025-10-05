import os
import sqlite3
from contextlib import contextmanager
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

SCHEMA_STATEMENTS: Tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS Metadata (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS Glossary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_name TEXT UNIQUE,
        pinyin TEXT,
        vietnamese_name TEXT,
        notes TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS Relationships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        char1_vn_name TEXT,
        char2_vn_name TEXT,
        relationship_type TEXT,
        UNIQUE(char1_vn_name, char2_vn_name, relationship_type)
    )
    """,
)


def _ensure_parent_folder(db_path: str) -> None:
    parent = os.path.dirname(db_path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)


def initialise_database(db_path: str) -> None:
    """Create the SQLite database file with the required schema if missing."""
    _ensure_parent_folder(db_path)
    with sqlite3.connect(db_path) as conn:
        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)
        conn.commit()


@contextmanager
def connect(db_path: str):
    """Context manager returning a connection with row factory set to Row."""
    _ensure_parent_folder(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)
        yield conn
        conn.commit()
    finally:
        conn.close()


def write_metadata(conn: sqlite3.Connection, metadata: Dict[str, str]) -> None:
    if not metadata:
        return
    conn.executemany(
        "INSERT OR REPLACE INTO Metadata(key, value) VALUES(?, ?)",
        metadata.items(),
    )


def _normalize(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if stripped.upper() in {"N/A", "NA"}:
        return None
    return stripped


def insert_glossary_entries(
    conn: sqlite3.Connection,
    entries: Sequence[Dict[str, Optional[str]]],
) -> int:
    """Insert glossary entries, returning the number of new rows."""
    if not entries:
        return 0
    prepared = []
    for entry in entries:
        vietnamese = _normalize(entry.get("vietnamese_name"))
        if not vietnamese:
            continue
        prepared.append(
            (
                _normalize(entry.get("original_name")),
                _normalize(entry.get("pinyin")),
                vietnamese,
                _normalize(entry.get("notes")),
            )
        )
    if not prepared:
        return 0
    cursor = conn.executemany(
        """
        INSERT OR IGNORE INTO Glossary(original_name, pinyin, vietnamese_name, notes)
        VALUES(?, ?, ?, ?)
        """,
        prepared,
    )
    return cursor.rowcount or 0


def insert_relationship_entries(
    conn: sqlite3.Connection,
    entries: Sequence[Dict[str, Optional[str]]],
) -> int:
    if not entries:
        return 0
    prepared = []
    for entry in entries:
        char1 = _normalize(entry.get("char1_vn_name"))
        char2 = _normalize(entry.get("char2_vn_name"))
        rel_type = _normalize(entry.get("relationship_type"))
        if not (char1 and char2 and rel_type):
            continue
        prepared.append((char1, char2, rel_type))
    if not prepared:
        return 0
    cursor = conn.executemany(
        """
        INSERT OR IGNORE INTO Relationships(
            char1_vn_name,
            char2_vn_name,
            relationship_type
        ) VALUES(?, ?, ?)
        """,
        prepared,
    )
    return cursor.rowcount or 0


def fetch_metadata(conn: sqlite3.Connection) -> Dict[str, str]:
    rows = conn.execute("SELECT key, value FROM Metadata ORDER BY key").fetchall()
    return {row["key"]: row["value"] for row in rows}


def fetch_glossary(
    conn: sqlite3.Connection,
    *,
    ids: Optional[Iterable[int]] = None,
) -> List[sqlite3.Row]:
    if ids is None:
        query = "SELECT * FROM Glossary ORDER BY id"
        rows = conn.execute(query).fetchall()
    else:
        id_list = list(ids)
        if not id_list:
            return []
        placeholders = ",".join("?" for _ in id_list)
        query = f"SELECT * FROM Glossary WHERE id IN ({placeholders}) ORDER BY id"
        rows = conn.execute(query, id_list).fetchall()
    return rows


def fetch_glossary_by_original_names(
    conn: sqlite3.Connection,
    names: Sequence[str],
) -> List[sqlite3.Row]:
    if not names:
        return []
    placeholders = ",".join("?" for _ in names)
    query = (
        "SELECT * FROM Glossary WHERE original_name IN (%s) ORDER BY id" % placeholders
    )
    return conn.execute(query, list(names)).fetchall()


def list_glossary_entries(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    return conn.execute(
        "SELECT id, original_name, pinyin, vietnamese_name, notes FROM Glossary"
    ).fetchall()


def fetch_relationships(
    conn: sqlite3.Connection,
    *,
    involved_vn_names: Optional[Iterable[str]] = None,
) -> List[sqlite3.Row]:
    if involved_vn_names is None:
        query = "SELECT * FROM Relationships ORDER BY id"
        rows = conn.execute(query).fetchall()
    else:
        names = [name for name in involved_vn_names if name]
        if not names:
            return []
        placeholders = ",".join("?" for _ in names)
        query = (
            "SELECT * FROM Relationships WHERE char1_vn_name IN (%s) OR char2_vn_name IN (%s)"
            % (placeholders, placeholders)
        )
        rows = conn.execute(query, names * 2).fetchall()
    return rows


__all__ = [
    "connect",
    "fetch_glossary",
    "fetch_glossary_by_original_names",
    "fetch_metadata",
    "fetch_relationships",
    "initialise_database",
    "insert_glossary_entries",
    "insert_relationship_entries",
    "list_glossary_entries",
    "write_metadata",
    "purge_placeholder_entries",
]


def purge_placeholder_entries(conn: sqlite3.Connection) -> Tuple[int, int]:
    glossary_deleted = conn.execute(
        """
        DELETE FROM Glossary
        WHERE vietnamese_name IS NULL
        OR TRIM(vietnamese_name) = ''
        OR UPPER(TRIM(vietnamese_name)) IN ('N/A', 'NA')
        """
    ).rowcount
    relationships_deleted = conn.execute(
        """
        DELETE FROM Relationships
        WHERE char1_vn_name IS NULL
        OR char2_vn_name IS NULL
        OR relationship_type IS NULL
        OR TRIM(char1_vn_name) = ''
        OR TRIM(char2_vn_name) = ''
        OR TRIM(relationship_type) = ''
        OR UPPER(TRIM(char1_vn_name)) IN ('N/A', 'NA')
        OR UPPER(TRIM(char2_vn_name)) IN ('N/A', 'NA')
        OR UPPER(TRIM(relationship_type)) IN ('N/A', 'NA')
        """
    ).rowcount
    return glossary_deleted or 0, relationships_deleted or 0
