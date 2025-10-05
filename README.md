# Dịch Truyện Tự Động – Kiến Trúc SQLite

Công cụ này tự động điều phối trình duyệt (thông qua Playwright) để gửi prompt cho Google AI Studio và dịch các chương truyện tiếng Trung sang tiếng Việt. Phiên bản hiện tại sử dụng cơ sở dữ liệu SQLite để lưu trữ ngữ cảnh, glossary và quan hệ giữa các nhân vật, giúp bản dịch ổn định và dễ mở rộng.

## Luồng hoạt động

1. **Khởi tạo** – Nếu thư mục truyện (`truyen/`) chưa có file `story_data.sqlite`, chương đầu tiên sẽ được gửi với *Initialization Prompt*. Phản hồi có cấu trúc được phân tích và ghi vào 3 bảng: `Metadata`, `Glossary`, `Relationships`.
2. **Dịch chương** – Mỗi chương kế tiếp được dịch bằng *Translation Prompt* chứa ngữ cảnh đã lọc (metadata, nhân vật và quan hệ liên quan). Script lưu bản dịch vào `dich_votthinhan/chuong_xxx.txt`.
3. **Cập nhật DB** – Nếu AI trả về khối `[DATABASE_UPDATES]`, script tự động thêm nhân vật/mối quan hệ vào SQLite để phục vụ các chương sau.
4. **Dọn rác** – Mỗi lần khởi động, script tự động xoá các dòng placeholder (`N/A`) để prompt không bị nhiễu. Bạn cũng có thể gọi hàm `purge_placeholder_entries` khi cần.

## Cấu trúc cơ sở dữ liệu

- `Metadata(key TEXT PRIMARY KEY, value TEXT)`
- `Glossary(id INTEGER PK, original_name TEXT UNIQUE, pinyin TEXT, vietnamese_name TEXT, notes TEXT)`
- `Relationships(id INTEGER PK, char1_vn_name TEXT, char2_vn_name TEXT, relationship_type TEXT, UNIQUE(char1_vn_name, char2_vn_name, relationship_type))`

## Trước khi chạy

1. Mở Chrome với remote debugging (`--remote-debugging-port=9222`).
2. Cài Playwright và browser tương ứng nếu chưa có: `pip install playwright` rồi `playwright install`.
3. Kiểm tra thư mục `truyen/` chứa các chương nguồn (`*.txt`). Script sẽ tạo thư mục `dich_votthinhan/` nếu thiếu.

## Cách chạy script

Chạy file `auto.py` trong môi trường đã cấu hình Playwright:

```bash
python auto.py
```

Script sẽ tự động phát hiện chương đã dịch, tạo chat mới sau mỗi 4 lượt tương tác và tạm dừng khi gặp Content Blocked.

## Kiểm thử

Thiết lập môi trường thử nghiệm (khuyến nghị venv) và chạy:

```bash
python -m pytest
```

Các bài test tập trung vào bộ phân tích phản hồi (`response_parser`) và logic lọc ngữ cảnh (`context_builder`).

## Tùy biến

- **Prompts**: cập nhật trong `prompt_builder.py` nếu cần thay đổi định dạng.
- **System instructions**: chỉnh trong `system_prompt.md` (hiện rất tối giản, nhường quyền điều khiển cho prompt động).
- **Glossary xuất ra Markdown**: nếu cần file tổng hợp phục vụ ngoại vi, hãy bổ sung bước xuất từ SQLite sang `character_glossary.md`.
- **Làm sạch dữ liệu cũ**: nếu muốn tự dọn dẹp, bạn có thể chạy nhanh đoạn mã sau:

	```python
	from story_db import connect, purge_placeholder_entries

	with connect("truyen/story_data.sqlite") as conn:
			removed = purge_placeholder_entries(conn)
			print("Đã xoá", removed)
	```

---
Để mở rộng thêm (ví dụ: hỗ trợ nhiều truyện cùng lúc, sinh báo cáo thay đổi), hãy tạo thêm module mới và dựa vào lớp `story_db` sẵn có để đọc/ghi SQLite an toàn.
