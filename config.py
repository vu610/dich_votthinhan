"""Configuration constants for the translation automation tool."""

import os
from typing import Dict, List

# ======================= SYSTEM PATHS =======================
DEFAULT_ROOT_FOLDER = "truyen"
SYSTEM_PROMPT_FILE = "system_prompt.md"
DB_FILENAME = "story_data.sqlite"

# ======================= WEB INTERFACE =======================
WEBSITE_URL = "https://aistudio.google.com/prompts/new_chat"

# Selectors for Google AI Studio interface
TEXT_INPUT_SELECTOR = (
    'textarea[aria-label="Type something or tab to choose an example prompt"], '
    'textarea[aria-label="Start typing a prompt"]'
)
RESPONSE_TURN_SELECTOR = "ms-chat-turn"
RESPONSE_CONTENT_SELECTOR = "ms-text-chunk"
SEND_BUTTON_SELECTOR = ".run-button"
NEW_CHAT_BUTTON_SELECTOR = "button[aria-label='New chat']"
STOP_BUTTON_SELECTOR = "button:has-text('Stop')"
CONTENT_BLOCKED_SELECTOR = 'button:has-text("Content blocked")'
SYSTEM_INSTRUCTIONS_BUTTON_SELECTOR = "button[aria-label='System instructions']"
SYSTEM_INSTRUCTIONS_TEXTAREA_SELECTOR = 'textarea[placeholder*="Optional tone and style instructions"]'

# ======================= TIMING & RETRIES =======================
MAX_RETRIES = 3
STABILITY_CHECKS_REQUIRED = 3
STABILITY_CHECK_INTERVAL = 1
STABILITY_TIMEOUT = 30
ACTION_DELAY_SECONDS = 2

# ======================= BROWSER PROFILES =======================
DEFAULT_PROFILE_PATHS: List[str] = [
    os.path.expanduser(f"~/chrome-for-automation{idx}") for idx in range(0, 6)
]

# ======================= RATE LIMITING =======================
RATE_LIMIT_KEYWORDS = (
    "you've reached your rate limit",
    "you have reached your rate limit",
    "rate limit",
)

# ======================= CHINESE TEXT PROCESSING =======================
MAX_CHINESE_FIX_ROUNDS = 3

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
    "「": """,
    "」": """,
    "『": """,
    "』": """,
    "《": """,
    "》": """,
    "、": ",",
    "．": ".",
    "～": "~",
    "〜": "~",
    "｡": ".",
    "､": ",",
    "－": "-",
}

__all__ = [
    "DEFAULT_ROOT_FOLDER",
    "SYSTEM_PROMPT_FILE",
    "DB_FILENAME",
    "WEBSITE_URL",
    "TEXT_INPUT_SELECTOR",
    "RESPONSE_TURN_SELECTOR",
    "RESPONSE_CONTENT_SELECTOR",
    "SEND_BUTTON_SELECTOR",
    "NEW_CHAT_BUTTON_SELECTOR",
    "STOP_BUTTON_SELECTOR",
    "CONTENT_BLOCKED_SELECTOR",
    "SYSTEM_INSTRUCTIONS_BUTTON_SELECTOR",
    "SYSTEM_INSTRUCTIONS_TEXTAREA_SELECTOR",
    "MAX_RETRIES",
    "STABILITY_CHECKS_REQUIRED",
    "STABILITY_CHECK_INTERVAL",
    "STABILITY_TIMEOUT",
    "ACTION_DELAY_SECONDS",
    "DEFAULT_PROFILE_PATHS",
    "RATE_LIMIT_KEYWORDS",
    "MAX_CHINESE_FIX_ROUNDS",
    "PUNCTUATION_MAP",
]
