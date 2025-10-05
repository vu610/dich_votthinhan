import re
from typing import List


CHINESE_SEQUENCE_PATTERN = re.compile(
    r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002EBEF]+"
)


def extract_chinese_sequences(text: str) -> List[str]:
    """Trích xuất các chuỗi tiếng Trung liên tiếp, giữ nguyên thứ tự và bỏ trùng."""
    raw_sequences = CHINESE_SEQUENCE_PATTERN.findall(text)
    unique: List[str] = []
    seen: set[str] = set()
    for sequence in raw_sequences:
        if sequence not in seen:
            seen.add(sequence)
            unique.append(sequence)
    return unique


def test_extract_chinese_sequences_contiguous_group():
    sequences = extract_chinese_sequences("Các bác cũng纷纷附和, 大家都听了。")
    assert sequences == ["纷纷附和", "大家都听了"]


def test_extract_chinese_sequences_deduplicate_order():
    sequences = extract_chinese_sequences("纷纷附和 rồi lại 纷纷附和")
    assert sequences == ["纷纷附和"]


def test_extract_chinese_sequences_no_chinese():
    sequences = extract_chinese_sequences("Hello world, no Chinese here.")
    assert sequences == []