#!/usr/bin/env python3
"""
Script để dọn dẹp database tự động.
Loại bỏ các entry placeholder, duplicates, và entries không hợp lệ.
"""

import os
import sqlite3
from typing import Tuple

from story_db import connect, purge_placeholder_entries


def remove_duplicate_glossary(conn: sqlite3.Connection) -> int:
    """Loại bỏ duplicates trong Glossary dựa trên original_name (nếu có) hoặc vietnamese_name."""
    # Tìm duplicates
    cursor = conn.execute("""
        SELECT vietnamese_name, COUNT(*) as cnt
        FROM Glossary
        WHERE vietnamese_name IS NOT NULL
        GROUP BY vietnamese_name
        HAVING cnt > 1
    """)
    duplicates = cursor.fetchall()
    removed = 0
    for row in duplicates:
        vn_name = row["vietnamese_name"]
        # Giữ lại entry đầu tiên (id nhỏ nhất), xóa các entry khác
        conn.execute("""
            DELETE FROM Glossary
            WHERE vietnamese_name = ? AND id NOT IN (
                SELECT MIN(id) FROM Glossary WHERE vietnamese_name = ?
            )
        """, (vn_name, vn_name))
        removed += conn.execute("SELECT changes()").fetchone()[0]
    return removed


def remove_duplicate_relationships(conn: sqlite3.Connection) -> int:
    """Loại bỏ duplicates trong Relationships dựa trên (char1, char2) sorted."""
    # Tìm duplicates
    cursor = conn.execute("""
        SELECT
            CASE WHEN char1_vn_name <= char2_vn_name THEN char1_vn_name ELSE char2_vn_name END as a,
            CASE WHEN char1_vn_name <= char2_vn_name THEN char2_vn_name ELSE char1_vn_name END as b,
            COUNT(*) as cnt
        FROM Relationships
        GROUP BY a, b
        HAVING cnt > 1
    """)
    duplicates = cursor.fetchall()
    removed = 0
    for row in duplicates:
        a, b = row["a"], row["b"]
        # Giữ lại entry đầu tiên, xóa các entry khác
        conn.execute("""
            DELETE FROM Relationships
            WHERE (char1_vn_name = ? AND char2_vn_name = ?) OR (char1_vn_name = ? AND char2_vn_name = ?)
            AND id NOT IN (
                SELECT MIN(id) FROM Relationships
                WHERE (char1_vn_name = ? AND char2_vn_name = ?) OR (char1_vn_name = ? AND char2_vn_name = ?)
            )
        """, (a, b, b, a, a, b, b, a))
        removed += conn.execute("SELECT changes()").fetchone()[0]
    return removed


def remove_orphaned_relationships(conn: sqlite3.Connection) -> int:
    """Loại bỏ relationships nếu một trong hai char không tồn tại trong Glossary."""
    removed = conn.execute("""
        DELETE FROM Relationships
        WHERE char1_vn_name NOT IN (SELECT vietnamese_name FROM Glossary)
        OR char2_vn_name NOT IN (SELECT vietnamese_name FROM Glossary)
    """).rowcount
    return removed


def cleanup_database(db_path: str) -> Tuple[int, int, int, int, int]:
    """
    Dọn dẹp database: loại bỏ placeholders, duplicates, orphaned relationships.
    Trả về (placeholder_glossary, placeholder_relationships, dup_glossary, dup_relationships, orphaned)
    """
    if not os.path.exists(db_path):
        print(f"Database {db_path} không tồn tại.")
        return 0, 0, 0, 0, 0

    with connect(db_path) as conn:
        print("Đang dọn dẹp placeholders...")
        placeholder_glossary, placeholder_relationships = purge_placeholder_entries(conn)

        print("Đang loại bỏ duplicates trong Glossary...")
        dup_glossary = remove_duplicate_glossary(conn)

        print("Đang loại bỏ duplicates trong Relationships...")
        dup_relationships = remove_duplicate_relationships(conn)

        print("Đang loại bỏ orphaned relationships...")
        orphaned = remove_orphaned_relationships(conn)

        return placeholder_glossary, placeholder_relationships, dup_glossary, dup_relationships, orphaned


def main():
    db_path = os.path.join("truyen", "story_data.sqlite")
    print(f"Dọn dẹp database: {db_path}")
    placeholder_g, placeholder_r, dup_g, dup_r, orphaned = cleanup_database(db_path)
    print("Hoàn tất dọn dẹp:")
    print(f"  - Glossary: loại bỏ {placeholder_g + dup_g} entries (placeholders: {placeholder_g}, duplicates: {dup_g})")
    print(f"  - Relationships: loại bỏ {placeholder_r + dup_r + orphaned} entries (placeholders: {placeholder_r}, duplicates: {dup_r}, orphaned: {orphaned})")


if __name__ == "__main__":
    main()