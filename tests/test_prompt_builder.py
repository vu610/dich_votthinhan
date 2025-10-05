from prompt_builder import build_initialisation_prompt


def test_build_initialisation_prompt_multiple_chapters():
    prompt = build_initialisation_prompt(
        [
            ("chuong_001.txt", "Nội dung 1"),
            ("chuong_002.txt", "Nội dung 2"),
            ("chuong_003.txt", "Nội dung 3"),
        ]
    )
    assert "ba chương" in prompt.lower()
    assert "Chương 001 - chuong_001.txt" in prompt
    assert "Nội dung 2" in prompt
    assert prompt.count("Chương") >= 3
