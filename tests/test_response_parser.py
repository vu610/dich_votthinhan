import textwrap

import pytest

from response_parser import ParseError, parse_initialisation_response, split_translation_and_updates


def test_parse_initialisation_response_success():
    sample = textwrap.dedent(
        """
        [START_DATA_BLOCK]

        [SECTION:METADATA]
        story_context: Bối cảnh mẫu.
        narrative_perspective: Ngôi thứ ba.
        main_char_pronouns: Tôi, anh.
        [END_SECTION]

    [SECTION:GLOSSARY]
    Tên Gốc (Pinyin)=Zhang San (Zhāng Sān) | Tên Dịch=Trương Tam | Ghi Chú=Nhân vật chính
        Li Si (Lǐ Sì) | Lý Tứ | Bạn thân
        [END_SECTION]

    [SECTION:RELATIONSHIPS]
    Nhân vật 1 (Tên dịch)=Trương Tam | Nhân vật 2 (Tên dịch)=Lý Tứ | Loại quan hệ=Bạn bè
    Trương Tam | Lý Tứ | Đồng đội
        [END_SECTION]

        [END_DATA_BLOCK]
        """
    )
    metadata, glossary, relationships = parse_initialisation_response(sample)
    assert metadata["story_context"] == "Bối cảnh mẫu."
    assert glossary[0]["original_name"] == "Zhang San"
    assert glossary[0]["pinyin"] == "Zhāng Sān"
    assert glossary[0]["vietnamese_name"] == "Trương Tam"
    assert glossary[1]["original_name"] == "Li Si"
    assert glossary[1]["pinyin"] == "Lǐ Sì"
    assert glossary[1]["vietnamese_name"] == "Lý Tứ"
    assert relationships[0]["relationship_type"] == "Bạn bè"


def test_parse_initialisation_response_missing_block():
    with pytest.raises(ParseError):
        parse_initialisation_response("Không có dữ liệu")


def test_split_translation_and_updates():
    sample = textwrap.dedent(
        """
        Chương 001 - Khởi đầu
        Đây là bản dịch.

        [DATABASE_UPDATES]
    [GLOSSARY_ADDITIONS]
    Tên Gốc (Pinyin)=Zhang San (Zhāng Sān) | Tên Dịch=Trương Tam | Ghi Chú=Nhân vật mới
        Li Si (Lǐ Sì) | Lý Tứ | Bạn thân
        [END_GLOSSARY_ADDITIONS]

    [RELATIONSHIP_ADDITIONS]
    Nhân vật 1 (Tên dịch)=Trương Tam | Nhân vật 2 (Tên dịch)=Lý Tứ | Loại quan hệ=Anh em
    Trương Tam | Lý Tứ | Đồng đội
        [END_RELATIONSHIP_ADDITIONS]
        [/DATABASE_UPDATES]
        """
    )
    translation, glossary_updates, relationship_updates = split_translation_and_updates(sample)
    assert "Khởi đầu" in translation
    assert glossary_updates[0]["vietnamese_name"] == "Trương Tam"
    assert glossary_updates[1]["vietnamese_name"] == "Lý Tứ"
    assert relationship_updates[0]["relationship_type"] == "Anh em"


def test_split_translation_without_updates():
    translation, glossary_updates, relationship_updates = split_translation_and_updates(
        "Chỉ có bản dịch"
    )
    assert translation == "Chỉ có bản dịch"
    assert not glossary_updates
    assert not relationship_updates


def test_parse_initialisation_response_skips_empty_rows():
    sample = textwrap.dedent(
        """
        [START_DATA_BLOCK]

        [SECTION:METADATA]
        story_context: Bối cảnh mẫu.
        [END_SECTION]

        [SECTION:GLOSSARY]
        Tên Gốc (Pinyin)=N/A | Tên Dịch=N/A | Ghi Chú=N/A
        [END_SECTION]

        [SECTION:RELATIONSHIPS]
    Nhân vật 1 (Tên dịch)=N/A | Nhân vật 2 (Tên dịch)=N/A | Loại quan hệ=N/A
        [END_SECTION]

        [END_DATA_BLOCK]
        """
    )
    metadata, glossary, relationships = parse_initialisation_response(sample)
    assert metadata["story_context"] == "Bối cảnh mẫu."
    assert glossary == []
    assert relationships == []
