"""Browser interaction utilities for Playwright automation."""

import os
import time
from typing import Optional

from playwright.sync_api import Locator, Page

from config import (
    ACTION_DELAY_SECONDS,
    SYSTEM_INSTRUCTIONS_BUTTON_SELECTOR,
    SYSTEM_INSTRUCTIONS_TEXTAREA_SELECTOR,
    SYSTEM_PROMPT_FILE,
)


def wait_between_actions(
    seconds: float = ACTION_DELAY_SECONDS,
    note: Optional[str] = None,
    indent: str = "    "
) -> None:
    """
    Wait for a specified duration with optional logging.

    Args:
        seconds: Duration to wait in seconds
        note: Optional message to display
        indent: String to use for indentation in output
    """
    try:
        delay = float(seconds)
    except (TypeError, ValueError):
        delay = ACTION_DELAY_SECONDS
    if delay < 0:
        delay = ACTION_DELAY_SECONDS
    if note:
        print(f"{indent}- {note} (chờ {delay:.1f}s)...")
    time.sleep(delay)


def safe_click(
    locator: Locator,
    description: str = "nút",
    max_attempts: int = 3
) -> bool:
    """
    Attempt to click an element with retries and fallback strategies.

    Args:
        locator: Playwright locator for the element
        description: Human-readable description for logging
        max_attempts: Maximum number of retry attempts

    Returns:
        True if click succeeded, False otherwise
    """
    for attempt in range(1, max_attempts + 1):
        try:
            locator.wait_for(state="visible", timeout=10000)
            locator.scroll_into_view_if_needed(timeout=5000)
            wait_between_actions(note=f"Chuẩn bị click {description}")
            locator.click(timeout=10000)
            wait_between_actions(note=f"Hoàn tất click {description}")
            return True
        except Exception as exc:
            print(f"    - Cảnh báo: Click {description} thất bại (lần {attempt}/{max_attempts}). Lỗi: {exc}")
            wait_between_actions(note="Tạm nghỉ trước khi thử lại")
            
            # Try force click
            try:
                locator.click(timeout=10000, force=True)
                wait_between_actions(note=f"Hoàn tất click force {description}")
                return True
            except Exception as force_error:
                print(f"      -> Thử click force thất bại: {force_error}")
            
            # Try dispatch event
            try:
                locator.dispatch_event("click")
                wait_between_actions(note=f"Hoàn tất dispatch click {description}")
                return True
            except Exception as dispatch_error:
                print(f"      -> Thử dispatch click thất bại: {dispatch_error}")
            
            # Try to clear any blocking dialogs
            try:
                locator.page.keyboard.press("Escape")
            except Exception:
                pass
            wait_between_actions(note="Giải phóng các hộp thoại che khuất")
            
            if attempt == max_attempts:
                print(f"    - [X] Không thể click {description} sau {max_attempts} lần thử.")
                return False
    return False


def safe_fill(
    locator: Locator,
    text: str,
    description: str = "ô nhập",
    max_attempts: int = 3
) -> bool:
    """
    Attempt to fill a text field with retries.

    Args:
        locator: Playwright locator for the element
        text: Text to fill
        description: Human-readable description for logging
        max_attempts: Maximum number of retry attempts

    Returns:
        True if fill succeeded, False otherwise
    """
    for attempt in range(1, max_attempts + 1):
        try:
            locator.wait_for(state="visible", timeout=10000)
            locator.scroll_into_view_if_needed(timeout=5000)
            wait_between_actions(note=f"Chuẩn bị điền {description}")
            locator.fill(text)
            wait_between_actions(note=f"Hoàn tất điền {description}")
            return True
        except Exception as exc:
            print(f"    - Cảnh báo: Không điền được {description} (lần {attempt}/{max_attempts}). Lỗi: {exc}")
            wait_between_actions(note="Tạm nghỉ trước khi thử lại")
            try:
                locator.clear()
            except Exception:
                pass
            if attempt == max_attempts:
                print(f"    - [X] Bỏ qua thao tác điền {description}.")
                return False
    return False


def load_system_prompt() -> Optional[str]:
    """
    Load system prompt from file if it exists.

    Returns:
        System prompt content or None if file doesn't exist or can't be read
    """
    if not os.path.exists(SYSTEM_PROMPT_FILE):
        return None
    try:
        with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except Exception as exc:
        print(f"[!] Cảnh báo: Không đọc được system prompt ({exc}).")
        return None


def update_system_instructions(page: Page, instructions: Optional[str]) -> None:
    """
    Update the system instructions on Google AI Studio.

    Args:
        page: Playwright page object
        instructions: System instructions text to set
    """
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
    except Exception as exc:
        print(f"    - Lỗi khi đồng bộ hóa System Instructions. Bỏ qua. Lỗi: {exc}")
        page.keyboard.press("Escape")
        wait_between_actions(note="Thoát khỏi System Instructions sau lỗi")


__all__ = [
    "wait_between_actions",
    "safe_click",
    "safe_fill",
    "load_system_prompt",
    "update_system_instructions",
]
