from typing import Dict, Iterable, List, Sequence, Tuple

from story_db import (
    fetch_glossary,
    fetch_metadata,
    fetch_relationships,
    list_glossary_entries,
)


def _is_meaningful(value: str) -> bool:
    if value is None:
        return False
    stripped = value.strip()
    if not stripped:
        return False
    return stripped.upper() not in {"N/A", "NA"}


def _format_metadata(metadata: Dict[str, str]) -> str:
    if not metadata:
        return "(Không có dữ liệu)"
    lines = [f"- {key}: {value}" for key, value in metadata.items()]
    return "\n".join(lines)


def _format_glossary_rows(rows: Sequence) -> str:
    if not rows:
        return "(Không có dữ liệu)"
    formatted: List[str] = []
    for row in rows:
        vietnamese = row["vietnamese_name"] or ""
        if not _is_meaningful(vietnamese):
            continue
        original = row["original_name"] or "N/A"
        pinyin = row["pinyin"] or "N/A"
        notes = row["notes"] or "N/A"
        formatted.append(
            f"- {original} ({pinyin}) => {vietnamese} | Ghi chú: {notes}"
        )
    return "\n".join(formatted) if formatted else "(Không có dữ liệu)"


def _format_relationship_rows(rows: Sequence) -> str:
    if not rows:
        return "(Không có dữ liệu)"
    formatted: List[str] = []
    for row in rows:
        char1 = row["char1_vn_name"] or ""
        char2 = row["char2_vn_name"] or ""
        rel_type = row["relationship_type"] or ""
        if not (_is_meaningful(char1) and _is_meaningful(char2) and _is_meaningful(rel_type)):
            continue
        formatted.append(f"- {char1} ↔ {char2} | Quan hệ: {rel_type}")
    return "\n".join(formatted) if formatted else "(Không có dữ liệu)"


def _deduplicate_preserve_order(items: Iterable[int]) -> List[int]:
    seen = set()
    ordered: List[int] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def detect_relevant_characters(conn, chapter_text: str) -> List[int]:
    normalized_text = chapter_text or ""
    if not normalized_text.strip():
        return []
    rows = list_glossary_entries(conn)
    matches: List[int] = []
    lowercase_text = normalized_text.lower()
    for row in rows:
        original = (row["original_name"] or "").strip()
        vietnamese = (row["vietnamese_name"] or "").strip()
        if original and _is_meaningful(original) and original in normalized_text:
            matches.append(row["id"])
            continue
        if vietnamese and _is_meaningful(vietnamese) and vietnamese.lower() in lowercase_text:
            matches.append(row["id"])
    return _deduplicate_preserve_order(matches)


def build_context_sections(conn, chapter_text: str) -> Tuple[str, str, str]:
    metadata = fetch_metadata(conn)
    relevant_ids = detect_relevant_characters(conn, chapter_text)
    if relevant_ids:
        glossary_rows = fetch_glossary(conn, ids=relevant_ids)
        vn_names = [
            row["vietnamese_name"]
            for row in glossary_rows
            if row["vietnamese_name"] and _is_meaningful(row["vietnamese_name"])
        ]
        vn_name_set = {name for name in vn_names if name}
        relationships_rows = [
            row
            for row in fetch_relationships(conn, involved_vn_names=vn_names)
            if row["char1_vn_name"] in vn_name_set and row["char2_vn_name"] in vn_name_set
        ]
    else:
        glossary_rows = fetch_glossary(conn)
        relationships_rows = fetch_relationships(conn)
    metadata_section = _format_metadata(metadata)
    glossary_section = _format_glossary_rows(glossary_rows)
    relationships_section = _format_relationship_rows(relationships_rows)
    return metadata_section, glossary_section, relationships_section


__all__ = [
    "build_context_sections",
    "detect_relevant_characters",
]
