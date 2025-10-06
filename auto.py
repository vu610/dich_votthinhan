# File: dich_truyen_final_v18.py
# Phiên b?n s?a l?i logic c?p nh?t glossary, ??m b?o ??ng b? hóa nh?t quán.

import argparse
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
DEFAULT_ROOT_FOLDER = "truyen"
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

DEFAULT_PROFILE_PATHS = [
    os.path.expanduser(f"~/chrome-for-automation{idx}") for idx in range(0, 6)
]

RATE_LIMIT_KEYWORDS = (
    "you've reached your rate limit",
    "you have reached your rate limit",
    "rate limit",
)


class RateLimitError(RuntimeError):
    """Được ném ra khi AI Studio báo đã chạm giới hạn tần suất."""


class BrowserSessionManager:
    """Quản lý vòng quay profile Chrome khi làm việc với Playwright."""

    def __init__(
        self,
        playwright,
        profile_paths: Sequence[str],
        *,
        channel: str = "chrome",
        headless: bool = False,
    ) -> None:
        if not profile_paths:
            raise ValueError("Cần ít nhất một profile Chrome để chạy tool.")
        self._playwright = playwright
        self._profile_paths = [os.path.expanduser(path) for path in profile_paths]
        self._channel = channel
        self._headless = headless
        self._index = -1
        self._context = None
        self.page = None

    def launch_initial(self, system_prompt: Optional[str]) -> None:
        self._rotate_to(self._next_index(), system_prompt)

    def rotate(self, system_prompt: Optional[str]) -> None:
        print("\n[!] Phát hiện giới hạn tần suất. Đang chuyển sang profile Chrome kế tiếp...")
        self._rotate_to(self._next_index(), system_prompt)

    def close(self) -> None:
        if self._context is not None:
            try:
                self._context.close()
            except Exception as exc:  # noqa: BLE001
                print(f"[!] Cảnh báo: lỗi khi đóng context trình duyệt: {exc}")
        self._context = None
        self.page = None

    # --------------------------------------------------

    def _next_index(self) -> int:
        return (self._index + 1) % len(self._profile_paths)

    def _rotate_to(self, index: int, system_prompt: Optional[str]) -> None:
        self.close()
        self._index = index
        user_data_dir = self._profile_paths[self._index]
        os.makedirs(user_data_dir, exist_ok=True)
        print(f"[•] Đang khởi chạy Chrome profile: {user_data_dir}")
        try:
            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                channel=self._channel,
                headless=self._headless,
                args=[
                    "--no-sandbox",
                    "--disable-extensions",
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                ],
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"Không thể khởi chạy Chrome với profile '{user_data_dir}': {exc}"
            ) from exc

        if self._context.pages:
            self.page = self._context.pages[0]
        else:
            self.page = self._context.new_page()

        self.page.set_default_timeout(60000)
        self.page.goto(WEBSITE_URL, wait_until="domcontentloaded")
        wait_between_actions(note="Chờ trang AI Studio tải xong")
        try:
            self.page.wait_for_selector(TEXT_INPUT_SELECTOR, timeout=60000)
            print("[✓] Đã truy cập AI Studio và sẵn sàng làm việc.")
        except TimeoutError as exc:
            raise RuntimeError("Không tìm thấy ô chat sau 60 giây.") from exc

        print("[*] Đồng bộ System Instructions cho profile hiện tại...")
        update_system_instructions(self.page, system_prompt)


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


def detect_rate_limit(page, response_text: Optional[str]) -> bool:
    lowered_text = response_text.lower() if response_text else ""
    if lowered_text and any(keyword in lowered_text for keyword in RATE_LIMIT_KEYWORDS):
        return True
    try:
        locator = page.locator("text=/rate limit/i")
        if locator.count() and locator.first.is_visible():
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


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
    if detect_rate_limit(page, full_response_text):
        print("    - [!] Hệ thống báo đã đạt giới hạn tần suất.")
        raise RateLimitError("AI Studio trả về thông báo giới hạn tần suất.")
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
            reload_success = False
            try:
                page.reload(wait_until="domcontentloaded", timeout=90000)
                reload_success = True
            except (TimeoutError, Error) as exc:
                print(f"    -> Cảnh báo: Reload thất bại ({exc}). Thử mở lại URL.")
                try:
                    page.goto(WEBSITE_URL, wait_until="domcontentloaded", timeout=120000)
                    reload_success = True
                    print("    -> Đã mở lại trang thành công sau lỗi reload.")
                except (TimeoutError, Error) as goto_exc:
                    print(f"    -> Lỗi: Không thể mở lại trang sau khi reload lỗi ({goto_exc}).")
            if not reload_success:
                if attempt == MAX_RETRIES:
                    print("    -> Hết lượt thử reload trong giai đoạn khởi tạo. Dừng lại.")
                    return False
                wait_between_actions(seconds=5, note="Bỏ qua lần thử này vì reload thất bại")
                continue
            wait_between_actions(seconds=5, note="Chờ trang tải lại hoàn tất")
            update_system_instructions(page, system_prompt)
        try:
            success, response_text, blocked = submit_prompt_and_get_response(page, prompt)
        except RateLimitError:
            print("    -> Tạm dừng khởi tạo do giới hạn tần suất.")
            raise
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
            reload_success = False
            try:
                page.reload(wait_until="domcontentloaded", timeout=90000)
                reload_success = True
            except (TimeoutError, Error) as exc:
                print(f"    -> Cảnh báo: Reload thất bại ({exc}). Thử mở lại URL.")
                try:
                    page.goto(WEBSITE_URL, wait_until="domcontentloaded", timeout=120000)
                    reload_success = True
                    print("    -> Đã mở lại trang thành công sau lỗi reload.")
                except (TimeoutError, Error) as goto_exc:
                    print(f"    -> Lỗi: Không thể mở lại trang sau khi reload lỗi ({goto_exc}).")
            if not reload_success:
                if attempt == MAX_RETRIES:
                    print("    -> Hết lượt thử reload trong quá trình dịch. Dừng xử lý chương này.")
                    return False, False
                wait_between_actions(seconds=5, note="Bỏ qua lần thử này vì reload thất bại")
                continue
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
        try:
            success, response_text, blocked = submit_prompt_and_get_response(page, prompt)
        except RateLimitError:
            print("    -> Dừng dịch tạm thời vì giới hạn tần suất.")
            raise
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

        # Kiểm tra số ký tự tiếng Trung trong bản dịch
        chinese_chars = sum(len(seq) for seq in CHINESE_SEQUENCE_PATTERN.findall(translation_text))
        if chinese_chars > 30:
            print(f"    -> Phát hiện {chinese_chars} ký tự tiếng Trung (>30), tạo phiên chat mới và dịch lại...")
            if not reset_chat_session(page, system_prompt):
                print("    -> Không thể tạo phiên chat mới, bỏ qua retry.")
            else:
                # Dịch lại với cùng prompt
                try:
                    success_retry, response_text_retry, blocked_retry = submit_prompt_and_get_response(page, prompt)
                except RateLimitError:
                    print("    -> Retry bị dừng do giới hạn tần suất, giữ bản dịch gốc.")
                    raise
                if blocked_retry:
                    print("    -> Retry bị chặn, giữ bản dịch gốc.")
                elif success_retry and response_text_retry:
                    try:
                        translation_text, glossary_updates, relationship_updates = split_translation_and_updates(
                            response_text_retry
                        )
                        print("    -> Đã retry thành công.")
                    except Exception as exc:  # noqa: BLE001
                        print(f"    -> Lỗi parse retry: {exc}, giữ bản dịch gốc.")
                else:
                    print("    -> Retry thất bại, giữ bản dịch gốc.")

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
        try:
            translation_text = fix_chinese_in_translation(page, translation_text)
        except RateLimitError:
            print("    -> Dừng xử lý bản dịch do giới hạn tần suất trong bước làm sạch tiếng Trung.")
            raise
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

        try:
            success, response_text, blocked = submit_prompt_and_get_response(page, prompt)
        except RateLimitError:
            print("    -> Bị giới hạn tần suất khi yêu cầu AI sửa chuỗi tiếng Trung.")
            raise
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


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tool dịch truyện tự động với AI Studio.")
    parser.add_argument(
        "--root",
        default=DEFAULT_ROOT_FOLDER,
        help="Thư mục gốc chứa các bộ truyện (mặc định: ./truyen)",
    )
    parser.add_argument(
        "--profiles",
        help=(
            "Danh sách profile Chrome (phân tách bởi dấu phẩy). "
            "Nếu không truyền, tool dùng ~/chrome-for-automation1..5."
        ),
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Chạy Chrome ở chế độ headless (ít được khuyến nghị).",
    )
    return parser.parse_args()


def resolve_profile_paths(args: argparse.Namespace) -> List[str]:
    if args.profiles:
        profiles = [path.strip() for path in args.profiles.split(",") if path.strip()]
    else:
        profiles = DEFAULT_PROFILE_PATHS
    unique_profiles: List[str] = []
    seen = set()
    for path in profiles:
        if path not in seen:
            unique_profiles.append(path)
            seen.add(path)
    return unique_profiles


def iter_novel_directories(root_folder: str) -> List[str]:
    if not os.path.isdir(root_folder):
        return []
    entries = []
    for name in sorted(os.listdir(root_folder)):
        candidate = os.path.join(root_folder, name)
        if os.path.isdir(candidate):
            entries.append(candidate)
    return entries


def process_novel(
    session_manager: BrowserSessionManager,
    novel_root: str,
    system_prompt: Optional[str],
) -> None:
    novel_name = os.path.basename(os.path.abspath(novel_root))
    input_folder = os.path.join(novel_root, "goc")
    output_folder = os.path.join(novel_root, "dich")
    db_path = os.path.join(novel_root, DB_FILENAME)

    if not os.path.isdir(input_folder):
        print(f"[-] Bỏ qua '{novel_name}': không tìm thấy thư mục 'goc'.")
        return

    os.makedirs(output_folder, exist_ok=True)
    removed_glossary, removed_relationships = cleanup_database(db_path)
    if removed_glossary or removed_relationships:
        print(
            f"[!] '{novel_name}': dọn database - xoá {removed_glossary} nhân vật placeholder, "
            f"{removed_relationships} quan hệ placeholder."
        )

    chapter_files = [
        name
        for name in sorted(os.listdir(input_folder))
        if name.endswith(".txt")
    ]
    if not chapter_files:
        print(f"[-] '{novel_name}': không tìm thấy chương .txt trong thư mục 'goc'.")
        return

    translated_files = {
        name for name in os.listdir(output_folder) if name.endswith(".txt")
    }

    page = session_manager.page

    if chapter_files and not os.path.exists(db_path):
        initial_paths = [
            os.path.join(input_folder, name)
            for name in chapter_files[:3]
        ]
        while True:
            try:
                initialised = run_initialisation(page, db_path, initial_paths, system_prompt)
            except RateLimitError:
                session_manager.rotate(system_prompt)
                page = session_manager.page
                continue
            if initialised:
                wait_between_actions(seconds=5, note="Chuẩn bị dịch sau khi khởi tạo")
                if not reset_chat_session(page, system_prompt):
                    print(f"[X] '{novel_name}': không thể tạo chat mới sau khởi tạo. Dừng bộ truyện này.")
                    return
                wait_between_actions(seconds=4, note="Sẵn sàng dịch chương đầu tiên")
            else:
                print(f"[X] '{novel_name}': khởi tạo database thất bại. Bỏ qua bộ truyện.")
                return
            break

    print("\n" + "=" * 64)
    print(f"[☆] BẮT ĐẦU DỊCH BỘ TRUYỆN: {novel_name}")
    print("=" * 64)

    for filename in chapter_files:
        if filename in translated_files:
            print(f"[-] '{novel_name}': bỏ qua '{filename}' vì đã có bản dịch.")
            continue

        input_path = os.path.join(input_folder, filename)
        output_path = os.path.join(output_folder, filename)

        while True:
            try:
                success, blocked = process_translation_file(
                    page, db_path, input_path, output_path, system_prompt
                )
            except RateLimitError:
                session_manager.rotate(system_prompt)
                page = session_manager.page
                continue
            break

        if success:
            translated_files.add(filename)
            wait_between_actions(seconds=10, note="Nghỉ trước khi sang chương tiếp theo")
        else:
            if blocked:
                wait_between_actions(seconds=5, note="Tạm nghỉ sau khi dính Content Blocked")
            else:
                wait_between_actions(seconds=5, note="Chuẩn bị thử chương tiếp theo")

        print("\n" + "-" * 56)
        print(f"Tạo cuộc trò chuyện mới sau chương '{filename}' của '{novel_name}'.")
        print("-" * 56 + "\n")

        if not reset_chat_session(page, system_prompt):
            print(f"[X] '{novel_name}': lỗi khi tạo chat mới. Tạm dừng bộ truyện.")
            break
        wait_between_actions(seconds=4, note="Đợi chat mới ổn định")

    print(f"\n[✓] Hoàn tất xử lý bộ truyện '{novel_name}'.")


def main():
    args = parse_arguments()
    root_folder = os.path.abspath(args.root)
    profile_paths = resolve_profile_paths(args)
    system_prompt = load_system_prompt()

    if not os.path.isdir(root_folder):
        print(f"[X] Không tìm thấy thư mục gốc '{root_folder}'.")
        return

    novel_directories = iter_novel_directories(root_folder)
    if not novel_directories:
        print(f"[!] Không tìm thấy bộ truyện nào trong '{root_folder}'.")
        return

    print(f"[•] Tìm thấy {len(novel_directories)} bộ truyện trong '{root_folder}'.")

    session_manager: Optional[BrowserSessionManager] = None
    try:
        with sync_playwright() as playwright:
            session_manager = BrowserSessionManager(
                playwright,
                profile_paths,
                headless=args.headless,
            )
            session_manager.launch_initial(system_prompt)

            for novel_root in novel_directories:
                process_novel(session_manager, novel_root, system_prompt)

    except RateLimitError:
        print("[X] Tool kết thúc do gặp giới hạn tần suất mà không thể xoay profile.")
    except Error as exc:
        print(f"[X] Lỗi Playwright: {exc}")
    finally:
        if session_manager is not None:
            try:
                session_manager.close()
            except Exception:
                pass

    print("\n================ HOÀN TẤT ==================")
    print("Bạn có thể đóng terminal này." )


if __name__ == "__main__":
    main()