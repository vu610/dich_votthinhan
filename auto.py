# File: dich_truyen_final_v18.py
# Phiên b?n s?a l?i logic c?p nh?t glossary, ??m b?o ??ng b? hóa nh?t quán.

import os
import re
import time
from typing import Dict, List, Optional, Sequence, Tuple

from playwright.sync_api import Error, TimeoutError, sync_playwright

from context_builder import build_context_sections
from prompt_builder import build_initialisation_prompt, build_translation_prompt
from response_parser import ParseError, parse_initialisation_response, split_translation_and_updates
from story_db import (
    connect,
    initialise_database,
    insert_glossary_entries,
    insert_relationship_entries,
    purge_placeholder_entries,
    write_metadata,
)

# ======================= CONFIG =======================
INPUT_FOLDER = "truyen"
OUTPUT_FOLDER = "dich_votthinhan"
SYSTEM_PROMPT_FILE = "system_prompt.md"
WEBSITE_URL = "https://aistudio.google.com/prompts/new_chat"
TEXT_INPUT_SELECTOR = 'textarea[aria-label="Type something or tab to choose an example prompt"], textarea[aria-label="Start typing a prompt"]'
RESPONSE_TURN_SELECTOR = "ms-chat-turn"
RESPONSE_CONTENT_SELECTOR = "ms-text-chunk"
SEND_BUTTON_SELECTOR = ".run-button"
NEW_CHAT_BUTTON_SELECTOR = "button[aria-label='New chat']"
STOP_BUTTON_SELECTOR = "button:has-text('Stop')"
CONTENT_BLOCKED_SELECTOR = 'button:has-text("Content blocked")'
SYSTEM_INSTRUCTIONS_BUTTON_SELECTOR = "button[aria-label='System instructions']"
SYSTEM_INSTRUCTIONS_TEXTAREA_SELECTOR = 'textarea[placeholder*="Optional tone and style instructions"]'
MAX_RETRIES = 3
STABILITY_CHECKS_REQUIRED = 3
STABILITY_CHECK_INTERVAL = 1
STABILITY_TIMEOUT = 30
ACTION_DELAY_SECONDS = 2
DB_FILENAME = "story_data.sqlite"
# ======================================================

CHINESE_SEQUENCE_PATTERN = re.compile(
    r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002EBEF]+"
)

PUNCTUATION_MAP: Dict[str, str] = {
    "，": ",",
    "。": ".",
    "！": "!",
    "？": "?",
    "：": ":",
    "；": ";",
    "（": "(",
    "）": ")",
    "【": "[",
    "】": "]",
    "「": "“",
    "」": "”",
    "『": "“",
    "』": "”",
    "《": "“",
    "》": "”",
    "、": ",",
    "．": ".",
    "～": "~",
    "〜": "~",
    "｡": ".",
    "､": ",",
    "－": "-",
}

MAX_CHINESE_FIX_ROUNDS = 3


def wait_between_actions(seconds=ACTION_DELAY_SECONDS, note: Optional[str] = None, indent: str = "    "):
    try:
        delay = float(seconds)
    except (TypeError, ValueError):
        delay = ACTION_DELAY_SECONDS
    if delay < 0:
        delay = ACTION_DELAY_SECONDS
    if note:
        print(f"{indent}- {note} (chờ {delay:.1f}s)...")
    time.sleep(delay)


def safe_click(locator, description: str = "nút", max_attempts: int = 3) -> bool:
    for attempt in range(1, max_attempts + 1):
        try:
            locator.wait_for(state="visible", timeout=10000)
            locator.scroll_into_view_if_needed(timeout=5000)
            wait_between_actions(note=f"Chuẩn bị click {description}")
            locator.click(timeout=10000)
            wait_between_actions(note=f"Hoàn tất click {description}")
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"    - Cảnh báo: Click {description} thất bại (lần {attempt}/{max_attempts}). Lỗi: {exc}")
            wait_between_actions(note="Tạm nghỉ trước khi thử lại")
            try:
                locator.click(timeout=10000, force=True)
                wait_between_actions(note=f"Hoàn tất click force {description}")
                return True
            except Exception as force_error:  # noqa: BLE001
                print(f"      -> Thử click force thất bại: {force_error}")
            try:
                locator.dispatch_event("click")
                wait_between_actions(note=f"Hoàn tất dispatch click {description}")
                return True
            except Exception as dispatch_error:  # noqa: BLE001
                print(f"      -> Thử dispatch click thất bại: {dispatch_error}")
            try:
                locator.page.keyboard.press("Escape")
            except Exception:  # noqa: BLE001
                pass
            wait_between_actions(note="Giải phóng các hộp thoại che khuất")
            if attempt == max_attempts:
                print(f"    - [X] Không thể click {description} sau {max_attempts} lần thử.")
                return False
    return False


def safe_fill(locator, text: str, description: str = "ô nhập", max_attempts: int = 3) -> bool:
    for attempt in range(1, max_attempts + 1):
        try:
            locator.wait_for(state="visible", timeout=10000)
            locator.scroll_into_view_if_needed(timeout=5000)
            wait_between_actions(note=f"Chuẩn bị điền {description}")
            locator.fill(text)
            wait_between_actions(note=f"Hoàn tất điền {description}")
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"    - Cảnh báo: Không điền được {description} (lần {attempt}/{max_attempts}). Lỗi: {exc}")
            wait_between_actions(note="Tạm nghỉ trước khi thử lại")
            try:
                locator.clear()
            except Exception:  # noqa: BLE001
                pass
            if attempt == max_attempts:
                print(f"    - [X] Bỏ qua thao tác điền {description}.")
                return False
    return False


def load_system_prompt() -> Optional[str]:
    if not os.path.exists(SYSTEM_PROMPT_FILE):
        return None
    try:
        with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except Exception as exc:  # noqa: BLE001
        print(f"[!] Cảnh báo: Không đọc được system prompt ({exc}).")
        return None


def update_system_instructions(page, instructions: Optional[str]) -> None:
    if not instructions:
        return
    print("    - Đang đồng bộ System Instructions trên web...")
    try:
        button = page.locator(SYSTEM_INSTRUCTIONS_BUTTON_SELECTOR)
        if not safe_click(button, "nút System Instructions"):
            print("    - Bỏ qua update System Instructions vì không thao tác được.")
            return
        textarea = page.locator(SYSTEM_INSTRUCTIONS_TEXTAREA_SELECTOR)
        textarea.wait_for(timeout=10000)
        if not safe_fill(textarea, instructions, "System Instructions"):
            return
        page.keyboard.press("Escape")
        wait_between_actions(note="Đóng hộp System Instructions")
        print("    - Đồng bộ hóa thành công.")
        wait_between_actions(seconds=3, note="Đảm bảo System Instructions đóng lại")
    except Exception as exc:  # noqa: BLE001
        print(f"    - Lỗi khi đồng bộ hóa System Instructions. Bỏ qua. Lỗi: {exc}")
        page.keyboard.press("Escape")
        wait_between_actions(note="Thoát khỏi System Instructions sau lỗi")


def wait_for_and_get_stable_text(page) -> Optional[str]:
    print("    - Bắt đầu quan sát nội dung phản hồi cho đến khi ổn định...")
    all_turns = page.locator(RESPONSE_TURN_SELECTOR).all()
    if not all_turns:
        print("      - Lỗi: Không tìm thấy lượt chat nào.")
        return None
    last_turn = all_turns[-1]
    content_container = last_turn.locator(RESPONSE_CONTENT_SELECTOR)
    if content_container.count() == 0:
        print(f"      - Lỗi: Không tìm thấy 'hộp chứa text' ({RESPONSE_CONTENT_SELECTOR}).")
        return None
    previous_text = ""
    stable_checks = 0
    start_time = time.time()
    while time.time() - start_time < STABILITY_TIMEOUT:
        current_text = content_container.inner_text()
        if current_text == previous_text and current_text != "":
            stable_checks += 1
            print(
                f"      - Nội dung ổn định... ({stable_checks}/{STABILITY_CHECKS_REQUIRED})"
            )
        else:
            stable_checks = 0
        if stable_checks >= STABILITY_CHECKS_REQUIRED:
            print("    - [✓] Nội dung đã ổn định. Lấy kết quả cuối cùng.")
            return current_text
        previous_text = current_text
        time.sleep(STABILITY_CHECK_INTERVAL)
    print(
        f"    - [!] Cảnh báo: Hết {STABILITY_TIMEOUT} giây chờ. Lấy nội dung cuối cùng có thể thiếu."
    )
    return previous_text


def submit_prompt_and_get_response(page, prompt_text: str) -> Tuple[bool, Optional[str], bool]:
    try:
        page.wait_for_selector(TEXT_INPUT_SELECTOR, timeout=20000)
    except TimeoutError:
        print("    - Lỗi: Không tìm thấy ô nhập liệu sau 20 giây.")
        return False, None, False
    text_input = page.locator(TEXT_INPUT_SELECTOR)
    if not safe_fill(text_input, prompt_text, "ô chat"):
        return False, None, False
    if not safe_click(page.locator(SEND_BUTTON_SELECTOR), "nút Gửi"):
        return False, None, False
    print("    - Đang chờ AI phản hồi (chờ nút 'Stop' biến mất)...")
    try:
        page.locator(STOP_BUTTON_SELECTOR).wait_for(state="hidden", timeout=300000)
    except TimeoutError:
        print(
            "    - Cảnh báo: Nút 'Stop' vẫn xuất hiện sau 5 phút. Thử nhấn 'Stop' để chắc chắn kết thúc."
        )
        try:
            safe_click(page.locator(STOP_BUTTON_SELECTOR), "nút Stop")
        except Exception:  # noqa: BLE001
            pass
        return False, None, False
    print("    - AI đã phản hồi xong.")
    wait_between_actions(note="Chuẩn bị đọc kết quả phản hồi")
    if page.locator(CONTENT_BLOCKED_SELECTOR).is_visible():
        print("    - [!] PHÁT HIỆN LỖI: Nội dung bị chặn (Content Blocked).")
        wait_between_actions(note="Ghi nhận trạng thái Content Blocked")
        return False, None, True
    full_response_text = wait_for_and_get_stable_text(page)
    if full_response_text is None or full_response_text == "":
        print("[X] Lỗi: Không thể lấy được nội dung phản hồi sau khi chờ.")
        return False, None, False
    return True, full_response_text.strip(), False


def run_initialisation(
    page,
    db_path: str,
    chapter_paths: Sequence[str],
    system_prompt: Optional[str],
) -> bool:
    if not chapter_paths:
        print("[X] Không có chương nào để khởi tạo database.")
        return False
    print(
        f"\n[☆] Bắt đầu khởi tạo database từ {len(chapter_paths)} chương đầu tiên..."
    )
    chapter_texts = []
    for path in chapter_paths:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                chapter_texts.append((os.path.basename(path), handle.read()))
        except Exception as exc:  # noqa: BLE001
            print(f"    -> Lỗi khi đọc '{path}': {exc}")
            return False
    prompt = build_initialisation_prompt(chapter_texts)
    for attempt in range(1, MAX_RETRIES + 1):
        if attempt > 1:
            print(f"    -> Thử lại khởi tạo (lần {attempt}/{MAX_RETRIES})...")
            wait_between_actions(seconds=5, note="Nghỉ giữa các lần thử")
            print("    -> Tải lại trang để đảm bảo trạng thái sạch...")
            page.reload(wait_until="domcontentloaded")
            wait_between_actions(seconds=5, note="Chờ trang tải lại hoàn tất")
            update_system_instructions(page, system_prompt)
        success, response_text, blocked = submit_prompt_and_get_response(page, prompt)
        if blocked:
            print("    -> Nội dung bị chính sách an toàn chặn. Không thể khởi tạo.")
            return False
        if not success or not response_text:
            continue
        try:
            metadata, glossary, relationships = parse_initialisation_response(response_text)
        except ParseError as exc:
            print(f"    -> Lỗi phân tích phản hồi khởi tạo: {exc}")
            if attempt == MAX_RETRIES:
                return False
            continue
        initialise_database(db_path)
        with connect(db_path) as conn:
            write_metadata(conn, metadata)
            new_chars = insert_glossary_entries(conn, glossary)
            new_rels = insert_relationship_entries(conn, relationships)
        print(
            f"    - Đã khởi tạo database: {len(metadata)} metadata, "
            f"{new_chars} nhân vật, {new_rels} quan hệ."
        )
        return True
    print("    -> Khởi tạo database thất bại sau nhiều lần thử.")
    return False


def process_translation_file(
    page,
    db_path: str,
    input_path: str,
    output_path: str,
    system_prompt: Optional[str],
) -> Tuple[bool, bool]:
    filename = os.path.basename(input_path)
    print(f"\n[*] Bắt đầu xử lý file: {filename}")
    with open(input_path, "r", encoding="utf-8") as handle:
        chapter_text = handle.read()
    for attempt in range(1, MAX_RETRIES + 1):
        if attempt > 1:
            print(f"    -> Thử lại lần {attempt}/{MAX_RETRIES} cho file '{filename}'...")
            wait_between_actions(seconds=5, note="Nghỉ giữa các lần thử")
            print("    -> Tải lại trang để đảm bảo trạng thái sạch...")
            page.reload(wait_until="domcontentloaded")
            wait_between_actions(seconds=5, note="Chờ trang tải lại hoàn tất")
            update_system_instructions(page, system_prompt)
        with connect(db_path) as conn:
            metadata_section, glossary_section, relationships_section = build_context_sections(
                conn, chapter_text
            )
        prompt = build_translation_prompt(
            metadata_section=metadata_section,
            glossary_section=glossary_section,
            relationships_section=relationships_section,
            source_text=chapter_text,
        )
        success, response_text, blocked = submit_prompt_and_get_response(page, prompt)
        if blocked:
            print("    -> Nội dung bị chính sách an toàn chặn. Không thể tiếp tục với chương này.")
            return False, True
        if not success or not response_text:
            continue
        try:
            translation_text, glossary_updates, relationship_updates = split_translation_and_updates(
                response_text
            )
        except Exception as exc:  # noqa: BLE001
            print(f"    -> Lỗi trong khi phân tách phản hồi: {exc}")
            if attempt == MAX_RETRIES:
                return False, False
            continue
        glossary_added = 0
        relationships_added = 0
        if glossary_updates or relationship_updates:
            with connect(db_path) as conn:
                if glossary_updates:
                    glossary_added = insert_glossary_entries(conn, glossary_updates)
                if relationship_updates:
                    relationships_added = insert_relationship_entries(
                        conn, relationship_updates
                    )
            print(
                f"    - Cập nhật database: +{glossary_added} nhân vật, +{relationships_added} quan hệ."
            )
        # Sửa ký tự tiếng Trung nếu có
        translation_text = fix_chinese_in_translation(page, translation_text)
        try:
            with open(output_path, "w", encoding="utf-8") as out_handle:
                out_handle.write(translation_text)
        except Exception as exc:  # noqa: BLE001
            print(f"    -> Lỗi khi ghi file '{output_path}': {exc}")
            return False, False
        wait_between_actions(note="Lưu bản dịch xuống đĩa")
        print(f"    - Đã dịch và lưu thành công: {output_path}")
        return True, False
    print(
        f"[X] LỖI NẶNG: Đã thử {MAX_RETRIES} lần nhưng vẫn thất bại với file '{filename}'."
    )
    return False, False


def reset_chat_session(page, system_prompt: Optional[str]) -> bool:
    print("    -> Đang tạo cuộc trò chuyện mới...")
    for attempt in range(1, 4):
        success = safe_click(page.locator(NEW_CHAT_BUTTON_SELECTOR), "nút New Chat")
        if not success:
            print(f"    -> Không thể click nút New Chat (lần {attempt}/3).")
        else:
            try:
                page.wait_for_selector(TEXT_INPUT_SELECTOR, timeout=30000)
                wait_between_actions(note="Chờ ô chat sẵn sàng")
                update_system_instructions(page, system_prompt)
                return True
            except TimeoutError as exc:
                print(f"    -> Lỗi: Ô chat không xuất hiện sau khi tạo chat mới: {exc}")
        wait_between_actions(note="Chuẩn bị thử lại tạo chat mới")
        try:
            page.keyboard.press("Escape")
        except Exception:  # noqa: BLE001
            pass
    print("    - [X] Thất bại: Không thể tạo cuộc trò chuyện mới sau nhiều lần thử.")
    return False


def normalize_cjk_punctuation(text: str) -> str:
    """Chuyển đổi dấu câu tiếng Trung/Full-width sang ASCII tương ứng."""
    for src, dest in PUNCTUATION_MAP.items():
        text = text.replace(src, dest)
    return text


def extract_chinese_sequences(text: str) -> List[str]:
    """Trích xuất các chuỗi tiếng Trung liên tiếp, giữ nguyên thứ tự và bỏ trùng lặp."""
    raw_sequences = CHINESE_SEQUENCE_PATTERN.findall(text)
    unique_sequences: List[str] = []
    seen: set[str] = set()
    for sequence in raw_sequences:
        if sequence not in seen:
            seen.add(sequence)
            unique_sequences.append(sequence)
    return unique_sequences


def fix_chinese_in_translation(page, translation_text: str) -> str:
    """Loại bỏ các chuỗi tiếng Trung còn sót lại bằng cách hỏi AI trong cùng phiên chat."""

    cleaned_text = normalize_cjk_punctuation(translation_text)
    processed_sequences: set[str] = set()

    for round_index in range(1, MAX_CHINESE_FIX_ROUNDS + 1):
        pending_sequences = [
            seq for seq in extract_chinese_sequences(cleaned_text) if seq not in processed_sequences
        ]
        if not pending_sequences:
            break

        print(
            f"    -> Phát hiện {len(pending_sequences)} cụm tiếng Trung (lượt {round_index}): "
            + ", ".join(pending_sequences)
        )

        prompt_header = (
            "Tôi đang hoàn thiện bản dịch tiếng Việt của một chương truyện. "
            "Các cụm tiếng Trung dưới đây vẫn còn sót lại trong bản dịch. "
            "Hãy dịch mỗi cụm sang tiếng Việt tự nhiên, mượt mà và phù hợp văn cảnh chung."
        )

        prompt_rules = (
            "\n\nYÊU CẦU BẮT BUỘC:\n"
            "- Giữ nguyên thứ tự các cụm như đã cung cấp.\n"
            "- Chỉ trả lời mỗi dòng theo định dạng `[tiếng Trung] --> [bản dịch tiếng Việt]`.\n"
            "- Không thêm ghi chú, giải thích hay ký tự dư thừa.\n"
            "- Nếu không chắc chắn, hãy đưa ra bản dịch tiếng Việt tự nhiên khả dĩ nhất."
        )

        prompt_sequences = "\n".join(pending_sequences)
        prompt = f"{prompt_header}{prompt_rules}\n\nCÁC CỤM CẦN DỊCH:\n{prompt_sequences}"

        success, response_text, blocked = submit_prompt_and_get_response(page, prompt)
        if blocked or not success or not response_text:
            print("    -> Không thể gọi AI để sửa chuỗi tiếng Trung. Giữ nguyên bản dịch hiện tại.")
            return cleaned_text

        translation_map: Dict[str, str] = {}
        for raw_line in response_text.strip().splitlines():
            line = raw_line.strip()
            if not line or "-->" not in line:
                continue
            source_raw, translated_raw = line.split("-->", 1)
            source = source_raw.strip().strip("[]")
            translated = translated_raw.strip().strip("[]")
            if not source or not translated:
                continue
            if source in pending_sequences and source not in translation_map:
                translation_map[source] = translated

        if not translation_map:
            print("    -> Phản hồi không cung cấp bản dịch hợp lệ, dừng sửa." )
            break

        replacements = 0
        for original, replacement in sorted(translation_map.items(), key=lambda item: len(item[0]), reverse=True):
            if original in cleaned_text:
                cleaned_text = cleaned_text.replace(original, replacement)
                replacements += 1

        processed_sequences.update(translation_map.keys())
        print(
            f"    -> Đã thay thế {replacements} / {len(pending_sequences)} cụm tiếng Trung trong lượt {round_index}."
        )

        if replacements == 0:
            break

    remaining_sequences = extract_chinese_sequences(cleaned_text)
    if remaining_sequences:
        print(
            "    -> [!] Cảnh báo: Vẫn còn cụm tiếng Trung chưa xử lý: "
            + ", ".join(remaining_sequences)
        )

    return cleaned_text



def cleanup_database(db_path: str) -> Tuple[int, int]:
    if not os.path.exists(db_path):
        return 0, 0
    with connect(db_path) as conn:
        removed = purge_placeholder_entries(conn)
    return removed


def main():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    system_prompt = load_system_prompt()
    db_path = os.path.join(INPUT_FOLDER, DB_FILENAME)
    removed_glossary, removed_relationships = cleanup_database(db_path)
    if removed_glossary or removed_relationships:
        print(
            f"[!] Đã dọn dẹp database: xoá {removed_glossary} nhân vật placeholder, "
            f"{removed_relationships} quan hệ placeholder."
        )
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.connect_over_cdp("http://localhost:9222")
            if not browser.contexts:
                print("[X] Lỗi: Không tìm thấy context trình duyệt nào đang mở.")
                return
            context = browser.contexts[0]
            if not context.pages:
                print("[X] Lỗi: Không tìm thấy tab trình duyệt nào đang mở.")
                return
            page = context.pages[0]
            print("[✓] Kết nối thành công!")
        except Error as exc:
            print(
                f"\n[X] LỖI: KHÔNG THỂ KẾT NỐI VỚI TRÌNH DUYỆT.\n    Lỗi: {exc}"
            )
            return

        page.goto(WEBSITE_URL)
        wait_between_actions(note="Chờ trang AI Studio tải xong")
        try:
            page.wait_for_selector(TEXT_INPUT_SELECTOR, timeout=60000)
            print("[✓] Đã vào trang AI Studio và sẵn sàng hoạt động!")
        except TimeoutError:
            print("[X] Lỗi: Không tìm thấy ô chat sau 60 giây.")
            return

        print("\n[*] Thiết lập prompt ban đầu cho phiên làm việc...")
        update_system_instructions(page, system_prompt)

        files = sorted(
            filename for filename in os.listdir(INPUT_FOLDER) if filename.endswith(".txt")
        )
        translated_files = set(os.listdir(OUTPUT_FOLDER))

        if files and not os.path.exists(db_path):
            initial_paths = [
                os.path.join(INPUT_FOLDER, name)
                for name in files[:3]
                if name.endswith(".txt")
            ]
            if run_initialisation(page, db_path, initial_paths, system_prompt):
                wait_between_actions(seconds=5, note="Chuẩn bị dịch sau khi khởi tạo")
                if not reset_chat_session(page, system_prompt):
                    print("[X] Lỗi: Không thể tạo cuộc trò chuyện mới sau khởi tạo. Dừng script.")
                    return
                wait_between_actions(seconds=4, note="Sẵn sàng bắt đầu dịch chương đầu tiên")
            else:
                print("[X] Không thể khởi tạo database. Dừng script.")
                return

        for filename in files:
            if filename in translated_files:
                print(f"[-] Bỏ qua: '{filename}' đã được dịch.")
                continue

            input_path = os.path.join(INPUT_FOLDER, filename)
            output_path = os.path.join(OUTPUT_FOLDER, filename)
            success, blocked = process_translation_file(
                page, db_path, input_path, output_path, system_prompt
            )
            if success:
                translated_files.add(filename)
                wait_between_actions(seconds=10, note="Nghỉ trước khi chuyển sang chương tiếp theo")
            else:
                if blocked:
                    wait_between_actions(seconds=5, note="Chờ cuộc trò chuyện sẵn sàng sau Content Blocked")
                else:
                    wait_between_actions(seconds=5, note="Chuẩn bị cho chương tiếp theo")

            print("\n" + "=" * 56)
            print("Tạo cuộc trò chuyện mới sau chương vừa xử lý.")
            print("=" * 56 + "\n")
            if not reset_chat_session(page, system_prompt):
                print("[X] Lỗi khi tạo cuộc trò chuyện mới. Dừng script.")
                break
            wait_between_actions(seconds=4, note="Đảm bảo cuộc trò chuyện mới sẵn sàng")

        print("\n================ HOÀN TẤT ==================")
        print("Script đã xử lý xong. Bạn có thể đóng terminal này.")


if __name__ == "__main__":
    main()