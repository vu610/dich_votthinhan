import re
from typing import Dict, List, Optional, Sequence, Tuple

INIT_BLOCK_PATTERN = re.compile(
    r"\[START_DATA_BLOCK\](?P<content>.*)\[END_DATA_BLOCK\]",
    re.DOTALL,
)
SECTION_PATTERN = re.compile(
    r"\[SECTION:(?P<name>[A-Z_]+)\](?P<body>.*?)\[END_SECTION\]",
    re.DOTALL,
)

DB_UPDATES_PATTERN = re.compile(
    r"\[DATABASE_UPDATES\](?P<body>.*)\[/DATABASE_UPDATES\]",
    re.DOTALL,
)

SUBSECTION_PATTERN = re.compile(
    r"\[(?P<name>[A-Z_]+)\](?P<body>.*?)\[END_(?P=name)\]",
    re.DOTALL,
)


class ParseError(RuntimeError):
    pass


def _clean_lines(block: str) -> List[str]:
    return [line.strip() for line in block.strip().splitlines() if line.strip()]


def _parse_metadata_section(body: str) -> Dict[str, str]:
    metadata: Dict[str, str] = {}
    for line in _clean_lines(body):
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    return metadata


def _normalize_field(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if cleaned.upper() in {"N/A", "NA"}:
        return None
    return cleaned


def _parse_glossary_line(line: str) -> Optional[Dict[str, str]]:
    if line.startswith("#"):
        return None
    parts = [part.strip() for part in line.split("|") if part.strip()]
    data: Dict[str, str] = {}
    for part in parts:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        data[key.strip().lower()] = value.strip()

    def find_value(*candidates: str) -> Optional[str]:
        for key, value in data.items():
            for candidate in candidates:
                if candidate in key:
                    return value
        return None

    original_raw = _normalize_field(find_value("tên gốc", "ten goc"))
    vietnamese = _normalize_field(find_value("tên dịch", "ten dich"))
    notes = _normalize_field(find_value("ghi chú", "ghi chu"))

    if not data and parts:
        # Positional format: Original | Vietnamese | Notes
        original_raw = _normalize_field(parts[0] if len(parts) > 0 else None)
        vietnamese = _normalize_field(parts[1] if len(parts) > 1 else None)
        notes = _normalize_field(parts[2] if len(parts) > 2 else None)
    if not vietnamese:
        return None
    pinyin = None
    original_name = None
    if original_raw:
        match = re.match(r"^(?P<name>.+?)\s*\((?P<pinyin>[^()]+)\)$", original_raw)
        if match:
            original_name = _normalize_field(match.group("name"))
            pinyin = _normalize_field(match.group("pinyin"))
        else:
            original_name = original_raw
    if not original_name:
        original_name = None
    return {
        "original_name": original_name or None,
        "pinyin": pinyin or None,
        "vietnamese_name": vietnamese,
        "notes": notes or None,
    }


def _parse_relationship_line(line: str) -> Optional[Dict[str, str]]:
    if line.startswith("#"):
        return None
    parts = [part.strip() for part in line.split("|") if part.strip()]
    data: Dict[str, str] = {}
    for part in parts:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        data[key.strip().lower()] = value.strip()

    def find_value(*candidates: str) -> Optional[str]:
        for key, value in data.items():
            for candidate in candidates:
                if candidate in key:
                    return value
        return None

    char1 = _normalize_field(find_value("nhân vật 1", "nhan vat 1"))
    char2 = _normalize_field(find_value("nhân vật 2", "nhan vat 2"))
    rel_type = _normalize_field(find_value("loại quan hệ", "loai quan he"))
    if not data and parts:
        char1 = _normalize_field(parts[0] if len(parts) > 0 else None)
        char2 = _normalize_field(parts[1] if len(parts) > 1 else None)
        rel_type = _normalize_field(parts[2] if len(parts) > 2 else None)
    if not char1 or not char2 or not rel_type:
        return None
    return {
        "char1_vn_name": char1,
        "char2_vn_name": char2,
        "relationship_type": rel_type,
    }


def parse_initialisation_response(text: str) -> Tuple[Dict[str, str], List[Dict[str, str]], List[Dict[str, str]]]:
    match = INIT_BLOCK_PATTERN.search(text)
    if not match:
        raise ParseError("Không tìm thấy khối [START_DATA_BLOCK] trong phản hồi.")
    block = match.group("content")
    sections = {
        sec_match.group("name").upper(): sec_match.group("body")
        for sec_match in SECTION_PATTERN.finditer(block)
    }
    metadata = _parse_metadata_section(sections.get("METADATA", ""))
    glossary_lines = _clean_lines(sections.get("GLOSSARY", ""))
    glossary = [entry for line in glossary_lines if (entry := _parse_glossary_line(line))]
    # Deduplicate glossary by original_name or vietnamese_name
    seen_glossary = {}
    for entry in glossary:
        key = entry.get("original_name") or entry["vietnamese_name"]
        if key not in seen_glossary:
            seen_glossary[key] = entry
    glossary = list(seen_glossary.values())
    relationships_lines = _clean_lines(sections.get("RELATIONSHIPS", ""))
    relationships = [
        entry
        for line in relationships_lines
        if (entry := _parse_relationship_line(line))
    ]
    # Deduplicate relationships by (char1_vn_name, char2_vn_name) regardless of order
    seen_relationships = {}
    for entry in relationships:
        key = tuple(sorted([entry["char1_vn_name"], entry["char2_vn_name"]]))
        if key not in seen_relationships:
            seen_relationships[key] = entry
    relationships = list(seen_relationships.values())
    return metadata, glossary, relationships


def split_translation_and_updates(
    text: str,
) -> Tuple[str, List[Dict[str, str]], List[Dict[str, str]]]:
    updates_match = DB_UPDATES_PATTERN.search(text)
    if not updates_match:
        translation = text.strip()
        return translation, [], []
    translation = text[: updates_match.start()].strip()
    updates_block = updates_match.group("body")
    subsections = {
        sub_match.group("name").upper(): sub_match.group("body")
        for sub_match in SUBSECTION_PATTERN.finditer(updates_block)
    }
    glossary_additions = [
        entry
        for line in _clean_lines(subsections.get("GLOSSARY_ADDITIONS", ""))
        if (entry := _parse_glossary_line(line))
    ]
    # Deduplicate glossary by original_name or vietnamese_name
    seen_glossary = {}
    for entry in glossary_additions:
        key = entry.get("original_name") or entry["vietnamese_name"]
        if key not in seen_glossary:
            seen_glossary[key] = entry
    glossary_additions = list(seen_glossary.values())
    relationship_additions = [
        entry
        for line in _clean_lines(subsections.get("RELATIONSHIP_ADDITIONS", ""))
        if (entry := _parse_relationship_line(line))
    ]
    # Deduplicate relationships by (char1_vn_name, char2_vn_name) regardless of order
    seen_relationships = {}
    for entry in relationship_additions:
        key = tuple(sorted([entry["char1_vn_name"], entry["char2_vn_name"]]))
        if key not in seen_relationships:
            seen_relationships[key] = entry
    relationship_additions = list(seen_relationships.values())
    return translation, glossary_additions, relationship_additions


__all__ = [
    "ParseError",
    "parse_initialisation_response",
    "split_translation_and_updates",
]
