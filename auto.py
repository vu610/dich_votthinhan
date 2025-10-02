# File: dich_truyen_final_v9.py
# Phiên bản tự động cập nhật bảng tên nhân vật.

import os
import time
import re
from playwright.sync_api import sync_playwright, TimeoutError, Error

# ======================= CONFIG =======================
# 1. ĐƯỜNG DẪN
INPUT_FOLDER = "truyen"
OUTPUT_FOLDER = "dich_votthinhan"
PROMPT_FILE = "system_prompt.md"
GLOSSARY_FILE = "character_glossary.md"

# 2. URL VÀ SELECTORS
WEBSITE_URL = "https://aistudio.google.com/prompts/new_chat"
TEXT_INPUT_SELECTOR = 'textarea[aria-label="Type something or tab to choose an example prompt"], textarea[aria-label="Start typing a prompt"]'
RESPONSE_TURN_SELECTOR = "ms-chat-turn"
RESPONSE_CONTENT_SELECTOR = "ms-text-chunk"
SEND_BUTTON_SELECTOR = ".run-button"
NEW_CHAT_BUTTON_SELECTOR = "button[aria-label='New chat']"
STOP_BUTTON_SELECTOR = "button:has-text('Stop')"
SYSTEM_INSTRUCTIONS_BUTTON_SELECTOR = "button[aria-label='System instructions']"
SYSTEM_INSTRUCTIONS_TEXTAREA_SELECTOR = 'textarea[placeholder*="Optional tone and style instructions"]'

# 3. CẤU HÌNH KHÁC
CHAPTERS_PER_CHAT = 4
# >> CẤU HÌNH MỚI: Số lần thử lại tối đa cho mỗi chương <<
MAX_RETRIES = 3
# ====================================================================================


def load_and_assemble_prompt():
    """Đọc prompt và glossary từ file, sau đó ghép chúng lại."""
    try:
        with open(PROMPT_FILE, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
        with open(GLOSSARY_FILE, 'r', encoding='utf-8') as f:
            glossary_content = f.read()
        return prompt_template.replace("[CHARACTER_GLOSSARY_PLACEHOLDER]", glossary_content)
    except FileNotFoundError as e:
        print(f"[X] Lỗi: Không tìm thấy file prompt hoặc glossary: {e}")
        return None


def update_system_instructions(page, full_prompt):
    """Hàm chung để mở, điền và đóng System Instructions."""
    print("    - Đang đồng bộ hóa System Instructions trên web...")
    try:
        page.locator(SYSTEM_INSTRUCTIONS_BUTTON_SELECTOR).click()
        time.sleep(1)
        textarea = page.locator(SYSTEM_INSTRUCTIONS_TEXTAREA_SELECTOR)
        textarea.wait_for(timeout=10000)
        textarea.fill(full_prompt)
        time.sleep(1)
        page.keyboard.press("Escape")
        print("    - Đồng bộ hóa thành công.")
        time.sleep(2)
    except Exception as e:
        print(f"    - Lỗi khi đồng bộ hóa System Instructions. Bỏ qua. Lỗi: {e}")
        page.keyboard.press("Escape")


def extract_and_process_updates(response_text):
    """
    Tách phần truyện dịch và phần cập nhật glossary.
    Trả về (story_text, update_occurred_boolean).
    """
    update_marker = "[UPDATE_GLOSSARY]"
    update_occurred = False
    
    if update_marker in response_text:
        parts = response_text.split(update_marker, 1)
        story_text = parts[0].strip()
        update_data = parts[1].strip()
        
        print("    - Phát hiện khối [UPDATE_GLOSSARY]. Đang xử lý...")
        new_entries = []
        for line in update_data.split('\n'):
            line = line.strip()
            if not line: continue
            
            char_info = {}
            try:
                parts = line.split('|')
                for part in parts:
                    key, value = part.split('=', 1)
                    char_info[key.strip()] = value.strip()
                
                ten_goc = char_info.get("Tên Gốc", "N/A")
                ten_dich = char_info.get("Tên Dịch", "N/A")
                ghi_chu = char_info.get("Ghi Chú", "N/A")
                
                if ten_dich == "N/A": continue
                new_md_row = f"| {ten_goc} | N/A | **{ten_dich}** | {ghi_chu} |"
                new_entries.append(new_md_row)
            except Exception as e:
                print(f"      - Lỗi khi phân tích dòng cập nhật: '{line}'. Lỗi: {e}")

        if new_entries:
            with open(GLOSSARY_FILE, 'a', encoding='utf-8') as f:
                f.write("\n" + "\n".join(new_entries))
            print(f"    - Đã thêm {len(new_entries)} nhân vật mới vào '{GLOSSARY_FILE}'.")
            update_occurred = True
            
        return story_text, update_occurred
    else:
        return response_text.strip(), update_occurred


def process_single_file(page, input_path, output_path):
    filename = os.path.basename(input_path)
    print(f"\n[*] Bắt đầu xử lý file: {filename}")
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()

        page.locator(TEXT_INPUT_SELECTOR).fill(content)
        time.sleep(1)
        page.locator(SEND_BUTTON_SELECTOR).click()
        
        print("    - Đang chờ AI phản hồi (chờ nút 'Stop' biến mất)...")
        page.locator(STOP_BUTTON_SELECTOR).wait_for(state="hidden", timeout=300000)
        print("    - AI đã phản hồi xong.")
        time.sleep(2) 

        all_turns = page.locator(RESPONSE_TURN_SELECTOR).all()
        if not all_turns: return False, False
        
        last_turn = all_turns[-1]
        content_container = last_turn.locator(RESPONSE_CONTENT_SELECTOR)
        if content_container.count() == 0: return False, False
            
        full_response_text = content_container.inner_text()
        final_text, glossary_updated = extract_and_process_updates(full_response_text)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_text)
        print(f"[✔] Đã dịch và lưu thành công: {output_path}")
        # Trả về (Thành công, Có cập nhật glossary không)
        return True, glossary_updated
    except TimeoutError:
        print(f"[X] Lỗi: Hết thời gian chờ phản hồi cho file {filename}.")
        return False, False
    except Exception as e:
        print(f"[X] Lỗi nghiêm trọng khi xử lý file {filename}: {e}")
        return False, False


def main():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    
    full_prompt = load_and_assemble_prompt()
    if not full_prompt: return

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            page = context.pages[0]
            print("[✔] Kết nối thành công!")
        except Error as e:
            print(f"\n[X] LỖI: KHÔNG THỂ KẾT NỐI VỚI TRÌNH DUYỆT.\n    Lỗi: {e}")
            return

        page.goto(WEBSITE_URL)
        try:
            page.wait_for_selector(TEXT_INPUT_SELECTOR, timeout=60000)
            print("[✔] Đã vào trang AI Studio và sẵn sàng hoạt động!")
        except TimeoutError:
            print("[X] Lỗi: Không tìm thấy ô chat sau 60 giây.")
            return
            
        print("\n[*] Thiết lập prompt ban đầu cho phiên làm việc...")
        update_system_instructions(page, full_prompt)

        translated_files = set(os.listdir(OUTPUT_FOLDER))
        files_to_process = sorted(os.listdir(INPUT_FOLDER))
        chapters_in_current_chat = 0

        for filename in files_to_process:
            if not filename.endswith(".txt"): continue
            if filename in translated_files:
                print(f"[-] Bỏ qua: '{filename}' đã được dịch.")
                continue

            if chapters_in_current_chat >= CHAPTERS_PER_CHAT:
                print("\n" + "="*56)
                print(f"Đã dịch {chapters_in_current_chat} chương. Tạo cuộc trò chuyện mới.")
                print("="*56 + "\n")
                try:
                    page.locator(NEW_CHAT_BUTTON_SELECTOR).click()
                    page.wait_for_selector(TEXT_INPUT_SELECTOR, timeout=30000)
                    full_prompt = load_and_assemble_prompt()
                    print("[*] Thiết lập prompt cho cuộc trò chuyện mới...")
                    update_system_instructions(page, full_prompt)
                    chapters_in_current_chat = 0
                    time.sleep(3)
                except Exception as e:
                    print(f"[X] Lỗi khi nhấn nút 'New Chat': {e}. Dừng script.")
                    break
            
            input_path = os.path.join(INPUT_FOLDER, filename)
            output_path = os.path.join(OUTPUT_FOLDER, filename)

            # >> LOGIC THỬ LẠI VÀ BỎ QUA <<
            success = False
            retry_count = 0
            while not success and retry_count < MAX_RETRIES:
                if retry_count > 0:
                    print(f"\n    -> Thử lại lần {retry_count}/{MAX_RETRIES} cho file '{filename}'...")
                    time.sleep(5)
                    print("    -> Tải lại trang để đảm bảo trạng thái sạch...")
                    page.reload(wait_until="domcontentloaded")
                    time.sleep(5)
                    full_prompt = load_and_assemble_prompt()
                    update_system_instructions(page, full_prompt)

                success, glossary_updated = process_single_file(page, input_path, output_path)
                
                if glossary_updated:
                    full_prompt = load_and_assemble_prompt()
                    update_system_instructions(page, full_prompt)

                if not success:
                    retry_count += 1
            
            # Sau vòng lặp, kiểm tra kết quả
            if success:
                chapters_in_current_chat += 1
                print("    - Tạm nghỉ 10 giây...")
                time.sleep(10)
            else:
                print(f"\n[X] LỖI NẶNG: Đã thử lại {MAX_RETRIES} lần nhưng vẫn thất bại với file '{filename}'.")
                print("    -> Bỏ qua chương này và chuyển sang chương tiếp theo.")
                # Vòng lặp for sẽ tự động chuyển sang file tiếp theo

        print("\n================ HOÀN TẤT ==================")
        print("Script đã xử lý xong. Bạn có thể đóng terminal này.")

if __name__ == "__main__":
    main()