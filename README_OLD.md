# Dịch Truyện Tự Động – Kiến Trúc SQLite

Công cụ này tự động điều phối trình duyệt (thông qua Playwright) để gửi prompt cho Google AI Studio và dịch các chương truyện tiếng Trung sang tiếng Việt. Phiên bản hiện tại sử dụng cơ sở dữ liệu SQLite để lưu trữ ngữ cảnh, glossary và quan hệ giữa các nhân vật, giúp bản dịch ổn định và dễ mở rộng.

## Luồng hoạt động

1. **Khởi tạo** – Với mỗi bộ truyện con nằm trong `truyen/<ten_truyen>/`, nếu thư mục `goc/` chưa có database `story_data.sqlite`, tool sẽ gửi 3 chương đầu tiên bằng *Initialization Prompt*. Phản hồi có cấu trúc được phân tích và ghi vào 3 bảng: `Metadata`, `Glossary`, `Relationships`.
2. **Dịch chương** – Mỗi chương kế tiếp trong `goc/*.txt` được dịch bằng *Translation Prompt* chứa ngữ cảnh đã lọc (metadata, nhân vật và quan hệ liên quan). Bản dịch được lưu về `dich/*.txt` ngay trong thư mục bộ truyện tương ứng.
3. **Cập nhật DB** – Nếu AI trả về khối `[DATABASE_UPDATES]`, script tự động thêm nhân vật/mối quan hệ vào SQLite để phục vụ các chương sau.
4. **Dọn rác** – Mỗi lần khởi động, script tự động xoá các dòng placeholder (`N/A`) để prompt không bị nhiễu. Bạn cũng có thể gọi hàm `purge_placeholder_entries` khi cần.

## Tool lấy truyện và đồng bộ chương (`cralw.py`)

Script `cralw.py` đảm nhiệm việc tải toàn bộ chương từ uukanshu.cc, lưu vào cấu trúc thư mục chuẩn và theo dõi tiến độ bằng một database nhỏ (`novel_index.sqlite`).

### Tính năng chính

- Đọc danh sách URL (mỗi dòng một truyện) và tải toàn bộ chương về `truyen/<slug>/goc/chuong_XXX.txt`.
- Ghi nhận thông tin truyện (tên, tác giả, url, bìa…) vào SQLite để tái sử dụng.
- Mỗi lần chạy lại sẽ kiểm tra truyện đã lưu, đối chiếu mục lục và chỉ tải các chương mới.
- Tự động bỏ qua chương đã tải nếu file tồn tại và có dữ liệu, đồng thời phát hiện file rỗng để tải lại.
- Ghi `index.tsv` trong thư mục `goc/` để tiện tra cứu tên và url chương.
- Có thể gọi `auto.py` sau khi tải chương mới để dịch ngay.

### Cấu trúc database `novel_index.sqlite`

- `novels`: lưu thông tin cơ bản của truyện (slug, url, tác giả, đường dẫn thư mục, chương mới nhất…).
- `chapters`: lưu từng chương đã tải (số thứ tự, url, đường dẫn file, hash nội dung) giúp phát hiện cập nhật.

### Cách sử dụng

Chuẩn bị file `input.txt` liệt kê URL mục lục truyện (mỗi dòng một url). Sau đó chạy:

```bash
python cralw.py --input input.txt --run-auto
```

Các tuỳ chọn hữu ích:

- `--root`: thư mục gốc của các bộ truyện (mặc định `./truyen`).
- `--db`: đường dẫn file SQLite lưu danh sách truyện (mặc định `novel_index.sqlite`).
- `--min-length`: số ký tự tối thiểu của một chương hợp lệ (mặc định 400; tăng/giảm nếu trang nguồn thay đổi cấu trúc).
- `--skip-registered`: chỉ xử lý các URL trong `--input`, bỏ qua bước quét lại các truyện đã có trong DB.
- `--run-auto`: gọi `auto.py` ngay sau khi phát hiện chương mới.

Bạn có thể thiết lập cron (hoặc systemd timer) chạy `python cralw.py --run-auto` hằng ngày. Script sẽ tự động kiểm tra toàn bộ truyện đã lưu trong database và chỉ tải những chương mới.

## Cấu trúc cơ sở dữ liệu

- `Metadata(key TEXT PRIMARY KEY, value TEXT)`
- `Glossary(id INTEGER PK, original_name TEXT UNIQUE, pinyin TEXT, vietnamese_name TEXT, notes TEXT)`
- `Relationships(id INTEGER PK, char1_vn_name TEXT, char2_vn_name TEXT, relationship_type TEXT, UNIQUE(char1_vn_name, char2_vn_name, relationship_type))`

## Trước khi chạy

1. Cài Playwright và browser tương ứng nếu chưa có: `pip install playwright` rồi `playwright install`.
2. Đảm bảo máy có sẵn Google Chrome (tool sẽ tự khởi chạy mỗi profile riêng, không cần mở thủ công).
3. Tổ chức thư mục gốc `truyen/` theo cấu trúc:

	 ```
	 truyen/
		 bo_truyen_1/
			 goc/   # chứa các file .txt gốc
			 dich/  # tool sẽ tự tạo nếu thiếu
			 story_data.sqlite
		 bo_truyen_2/
			 goc/
			 dich/
			 story_data.sqlite
		 ...
	 ```

## Cách chạy script

Chạy file `auto.py` trong môi trường đã cấu hình Playwright:

```bash
python auto.py
```

Các tùy chọn hữu ích:

```bash
python auto.py --root /duong-dan/truyen --profiles "~/chrome-for-automation1,~/chrome-for-automation2"
```

- `--root`: thư mục chứa các bộ truyện (mặc định `./truyen`).
- `--profiles`: danh sách thư mục profile Chrome; tool sẽ xoay vòng khi gặp rate limit (mặc định 5 profile `~/chrome-for-automation1..5`).
- `--headless`: nếu muốn chạy Chrome headless (không khuyến nghị vì khó debug giao diện).

Script sẽ tự động phát hiện chương đã dịch, tạo chat mới sau mỗi chương và chủ động đổi profile khi gặp rate limit.

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

	with connect("truyen/bo_truyen_1/story_data.sqlite") as conn:
		removed = purge_placeholder_entries(conn)
		print("Đã xoá", removed)
	```

---
Để mở rộng thêm (ví dụ: hỗ trợ nhiều truyện cùng lúc, sinh báo cáo thay đổi), hãy tạo thêm module mới và dựa vào lớp `story_db` sẵn có để đọc/ghi SQLite an toàn.
