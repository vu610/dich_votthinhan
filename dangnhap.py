# File: luu_trang_thai_dang_nhap.py
from playwright.sync_api import sync_playwright
import time

# URL trang đăng nhập hoặc trang chính đều được
WEBSITE_URL = "https://aistudio.google.com/prompts/new_chat"
AUTH_FILE = "auth.json"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=50)
    context = browser.new_context()
    page = context.new_page()
    page.goto(WEBSITE_URL)

    print("\n========================================================")
    print("VUI LÒNG ĐĂNG NHẬP VÀO TÀI KHOẢN GOOGLE CỦA BẠN.")
    print("Bao gồm cả bước xác thực 2 yếu tố nếu có.")
    print("Sau khi đăng nhập thành công và thấy giao diện AI Studio,")
    print("bạn có thể đóng trình duyệt lại.")
    print("Script sẽ tự động lưu trạng thái đăng nhập.")
    print("========================================================\n")

    # Giữ trình duyệt mở để người dùng tương tác
    # Bạn có thể tăng thời gian nếu cần
    try:
        # Đợi cho đến khi người dùng đóng trình duyệt
        # Hoặc đợi cho đến khi một selector cụ thể xuất hiện sau khi đăng nhập
        page.wait_for_selector(".run-button", timeout=0) # timeout=0 nghĩa là chờ vô hạn
    except Exception:
        print("Trình duyệt đã được đóng.")

    # Lưu trạng thái vào file
    context.storage_state(path=AUTH_FILE)
    print(f"[*] Đã lưu trạng thái đăng nhập thành công vào file '{AUTH_FILE}'!")
    browser.close()