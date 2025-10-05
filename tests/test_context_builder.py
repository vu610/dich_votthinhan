from context_builder import build_context_sections, detect_relevant_characters
from story_db import (
    connect,
    initialise_database,
    insert_glossary_entries,
    insert_relationship_entries,
    purge_placeholder_entries,
    write_metadata,
)


def setup_sample_db(db_path: str) -> None:
    initialise_database(db_path)
    with connect(db_path) as conn:
        write_metadata(
            conn,
            {
                "story_context": "Làng ven sông trong thập niên 80.",
                "narrative_perspective": "Ngôi thứ ba",
            },
        )
        insert_glossary_entries(
            conn,
            [
                {
                    "original_name": "張三",
                    "pinyin": "Zhāng Sān",
                    "vietnamese_name": "Trương Tam",
                    "notes": "Nhân vật chính",
                },
                {
                    "original_name": "李四",
                    "pinyin": "Lǐ Sì",
                    "vietnamese_name": "Lý Tứ",
                    "notes": "Bạn thân",
                },
            ],
        )
        insert_relationship_entries(
            conn,
            [
                {
                    "char1_vn_name": "Trương Tam",
                    "char2_vn_name": "Lý Tứ",
                    "relationship_type": "Bạn bè",
                    "notes": "Thể hiện trong chương 1",
                }
            ],
        )


def test_detect_relevant_characters(tmp_path):
    db_path = tmp_path / "story.sqlite"
    setup_sample_db(str(db_path))
    with connect(str(db_path)) as conn:
        matched_ids = detect_relevant_characters(conn, "張三 xuất hiện trong đoạn đầu")
    assert matched_ids, "Phải tìm được ít nhất một nhân vật"


def test_build_context_sections_filters_relationships(tmp_path):
    db_path = tmp_path / "story.sqlite"
    setup_sample_db(str(db_path))
    with connect(str(db_path)) as conn:
        metadata, glossary, relationships = build_context_sections(
            conn, "李四 bước vào căn phòng"
        )
    assert "Lý Tứ" in glossary
    assert "Trương Tam" not in glossary
    assert "Bạn bè" not in relationships
    assert relationships.strip() == "(Không có dữ liệu)"
    assert metadata.strip().startswith("-")
    assert "Làng ven sông" in metadata


def test_insert_helpers_skip_placeholder_values(tmp_path):
    db_path = tmp_path / "story.sqlite"
    initialise_database(str(db_path))
    with connect(str(db_path)) as conn:
        added = insert_glossary_entries(
            conn,
            [
                {
                    "original_name": "N/A",
                    "pinyin": "N/A",
                    "vietnamese_name": "N/A",
                    "notes": "N/A",
                },
                {
                    "original_name": "張三",
                    "pinyin": "Zhāng Sān",
                    "vietnamese_name": "Trương Tam",
                    "notes": "Nhân vật chính",
                },
            ],
        )
        assert added == 1
        rel_added = insert_relationship_entries(
            conn,
            [
                {
                    "char1_vn_name": "N/A",
                    "char2_vn_name": "N/A",
                    "relationship_type": "N/A",
                },
                {
                    "char1_vn_name": "Trương Tam",
                    "char2_vn_name": "Lý Tứ",
                    "relationship_type": "Bạn bè",
                },
            ],
        )
        assert rel_added == 1


    def test_purge_placeholder_entries(tmp_path):
        db_path = tmp_path / "story.sqlite"
        initialise_database(str(db_path))
        with connect(str(db_path)) as conn:
            insert_glossary_entries(
                conn,
                [
                    {"original_name": "N/A", "vietnamese_name": "N/A"},
                    {"original_name": "張三", "vietnamese_name": "Trương Tam"},
                ],
            )
            insert_relationship_entries(
                conn,
                [
                    {"char1_vn_name": "N/A", "char2_vn_name": "N/A", "relationship_type": "N/A"},
                    {
                        "char1_vn_name": "Trương Tam",
                        "char2_vn_name": "Lý Tứ",
                        "relationship_type": "Bạn bè",
                    },
                ],
            )
            deleted = purge_placeholder_entries(conn)
            assert deleted == (1, 1)
            remaining_glossary = conn.execute("SELECT COUNT(*) FROM Glossary").fetchone()[0]
            remaining_relationships = conn.execute("SELECT COUNT(*) FROM Relationships").fetchone()[0]
            assert remaining_glossary == 1
            assert remaining_relationships == 1


def test_build_context_sections_includes_relationship_when_both_characters_present(tmp_path):
    db_path = tmp_path / "story.sqlite"
    setup_sample_db(str(db_path))
    with connect(str(db_path)) as conn:
        _, _, relationships = build_context_sections(
            conn, "Trương Tam và Lý Tứ cùng xuất hiện trong chương"
        )
    assert "Bạn bè" in relationships
