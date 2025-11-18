# Dịch Truyện Tự Động – Chinese to Vietnamese Novel Translation Tool

[English](#english) | [Tiếng Việt](#tiếng-việt)

---

## English

### Overview

An automated translation tool that uses Google AI Studio to translate Chinese novels to Vietnamese with intelligent context management. The system maintains character glossaries, relationships, and story metadata using SQLite databases to ensure consistent, high-quality translations.

### Key Features

- **Automated Web Scraping**: Downloads chapters from uukanshu.cc automatically
- **Context-Aware Translation**: Maintains character names, relationships, and story context across chapters
- **SQLite-Based Memory**: Stores glossaries and metadata for consistent translations
- **Browser Automation**: Uses Playwright to interact with Google AI Studio
- **Rate Limit Handling**: Automatically rotates between Chrome profiles when rate limits are hit
- **Incremental Updates**: Checks for new chapters daily and translates them automatically

### Architecture

```
truyen/                          # Root folder for all novels
├── <novel_slug>/               # Individual novel folder
│   ├── goc/                    # Original Chinese chapters
│   │   ├── chuong_001.txt
│   │   ├── chuong_002.txt
│   │   └── ...
│   ├── dich/                   # Translated Vietnamese chapters
│   │   ├── chuong_001.txt
│   │   └── ...
│   └── story_data.sqlite       # Novel-specific database
└── ...

novel_index.sqlite              # Global novel index database
```

#### Database Schema

**story_data.sqlite** (per novel):
- `Metadata`: Story context, narrative perspective, pronouns
- `Glossary`: Character names mapping (Chinese → Pinyin → Vietnamese)
- `Relationships`: Character relationships and interactions

**novel_index.sqlite** (global):
- `novels`: Novel metadata, URLs, latest chapters
- `chapters`: Chapter tracking with content hashes

### Installation

#### Prerequisites

- Python 3.8+
- Google Chrome browser
- Active Google AI Studio account

#### Setup

1. **Clone the repository**:
```bash
git clone https://github.com/vu610/dich_votthinhan.git
cd dich_votthinhan
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Install Playwright browsers**:
```bash
playwright install chromium
```

4. **Update requirements.txt** (recommended to add missing dependencies):
```bash
# Add these to requirements.txt if not already present:
# beautifulsoup4>=4.12
# lxml>=4.9
# requests>=2.31
```

### Usage

#### 1. Downloading Novels

Create an `input.txt` file with novel URLs (one per line):
```
https://uukanshu.cc/book/17474/
https://uukanshu.cc/book/25060/
```

Run the crawler:
```bash
python cralw.py --input input.txt --run-auto
```

**Options**:
- `--root`: Root directory for novels (default: `./truyen`)
- `--db`: Database file path (default: `novel_index.sqlite`)
- `--min-length`: Minimum chapter length in characters (default: 400)
- `--skip-registered`: Only process URLs from input file, skip registered novels
- `--run-auto`: Automatically run translation after downloading new chapters

#### 2. Translating Chapters

**Manual translation**:
```bash
python auto.py
```

**With custom options**:
```bash
python auto.py --root /path/to/truyen --profiles "~/chrome1,~/chrome2,~/chrome3"
```

**Options**:
- `--root`: Root directory containing novel folders (default: `./truyen`)
- `--profiles`: Comma-separated list of Chrome profile paths for rotation
- `--headless`: Run Chrome in headless mode (not recommended for debugging)

#### 3. Daily Automation

Set up a cron job to check for new chapters daily:

```bash
# Add to crontab (crontab -e)
0 2 * * * cd /path/to/dich_votthinhan && python cralw.py --run-auto
```

### Translation Workflow

1. **Initialization** (first 3 chapters):
   - Analyzes story context, characters, and relationships
   - Creates initial database with glossary entries
   - Establishes narrative perspective and pronouns

2. **Translation** (subsequent chapters):
   - Loads relevant context from database
   - Generates context-aware translation prompt
   - Translates chapter maintaining consistency
   - Updates database with new characters/relationships

3. **Quality Assurance**:
   - Detects and removes remaining Chinese characters
   - Converts Chinese punctuation to Vietnamese equivalents
   - Ensures stable AI responses before proceeding

### Configuration

#### System Prompt

Create a `system_prompt.md` file to customize AI behavior:
```markdown
Bạn là một dịch giả văn học chuyên nghiệp, có khả năng dịch truyện Trung Việt với chất lượng cao.
```

#### Chrome Profiles

By default, the tool uses 6 Chrome profiles (`~/chrome-for-automation0` to `~/chrome-for-automation5`). You can customize this:

```python
# In auto.py or via command line
--profiles "~/profile1,~/profile2"
```

### Development

#### Project Structure

```
.
├── auto.py                 # Main translation automation script
├── browser_utils.py        # Browser interaction utilities (NEW)
├── config.py              # Configuration constants (NEW)
├── cralw.py               # Web scraping for chapters
├── context_builder.py     # Context extraction from database
├── prompt_builder.py      # Prompt generation for AI
├── response_parser.py     # Parse AI responses
├── story_db.py           # Story database operations
├── novel_db.py           # Novel index database operations
├── epub_builder.py       # EPUB generation (optional)
├── cleanup_db.py         # Database maintenance utilities
└── tests/                # Test suite
    ├── test_auto_helpers.py
    ├── test_context_builder.py
    ├── test_cralw_helpers.py
    ├── test_prompt_builder.py
    └── test_response_parser.py
```

#### Running Tests

```bash
python -m pytest
```

#### Code Quality

The codebase has been refactored for better maintainability:
- Separated configuration into `config.py`
- Extracted browser utilities into `browser_utils.py`
- Added comprehensive docstrings
- Improved type hints
- Better error handling

### Troubleshooting

#### Common Issues

**1. "Content blocked" errors**:
- Modify your system prompt to be less explicit
- Try different phrasing in prompts
- Use a different Chrome profile

**2. Rate limits**:
- Tool automatically rotates profiles
- Ensure you have multiple Chrome profiles configured
- Wait time between requests is built-in

**3. Missing translations**:
- Check if initialization completed successfully
- Verify database exists in novel folder
- Review logs for parse errors

**4. Chinese characters remain in translation**:
- The tool attempts automatic cleanup
- May need to adjust `MAX_CHINESE_FIX_ROUNDS` in config

### Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

### License

This project is provided as-is for educational purposes.

### Acknowledgments

- Uses Google AI Studio for translation
- Web scraping from uukanshu.cc
- Built with Playwright for browser automation

---

## Tiếng Việt

### Tổng Quan

Công cụ dịch truyện tự động sử dụng Google AI Studio để dịch tiểu thuyết Trung Quốc sang tiếng Việt với quản lý ngữ cảnh thông minh. Hệ thống duy trì bảng thuật ngữ nhân vật, mối quan hệ và metadata truyện bằng cơ sở dữ liệu SQLite để đảm bảo bản dịch nhất quán và chất lượng cao.

### Tính Năng Chính

- **Thu Thập Web Tự Động**: Tải chương từ uukanshu.cc tự động
- **Dịch Thuật Nhận Biết Ngữ Cảnh**: Duy trì tên nhân vật, quan hệ và ngữ cảnh truyện qua các chương
- **Bộ Nhớ SQLite**: Lưu trữ bảng thuật ngữ và metadata cho bản dịch nhất quán
- **Tự Động Hóa Trình Duyệt**: Sử dụng Playwright tương tác với Google AI Studio
- **Xử Lý Giới Hạn Tần Suất**: Tự động xoay vòng giữa các profile Chrome khi gặp giới hạn
- **Cập Nhật Tăng Dần**: Kiểm tra chương mới hằng ngày và dịch tự động

### Kiến Trúc

```
truyen/                          # Thư mục gốc cho tất cả truyện
├── <ten_truyen>/               # Thư mục truyện riêng
│   ├── goc/                    # Chương gốc tiếng Trung
│   │   ├── chuong_001.txt
│   │   ├── chuong_002.txt
│   │   └── ...
│   ├── dich/                   # Chương đã dịch tiếng Việt
│   │   ├── chuong_001.txt
│   │   └── ...
│   └── story_data.sqlite       # Database riêng cho truyện
└── ...

novel_index.sqlite              # Database chỉ mục truyện toàn cục
```

#### Cấu Trúc Database

**story_data.sqlite** (mỗi truyện):
- `Metadata`: Ngữ cảnh truyện, góc nhìn tường thuật, đại từ
- `Glossary`: Ánh xạ tên nhân vật (Trung → Pinyin → Việt)
- `Relationships`: Mối quan hệ và tương tác nhân vật

**novel_index.sqlite** (toàn cục):
- `novels`: Metadata truyện, URL, chương mới nhất
- `chapters`: Theo dõi chương với content hash

### Cài Đặt

#### Yêu Cầu

- Python 3.8+
- Trình duyệt Google Chrome
- Tài khoản Google AI Studio đang hoạt động

#### Thiết Lập

1. **Clone repository**:
```bash
git clone https://github.com/vu610/dich_votthinhan.git
cd dich_votthinhan
```

2. **Cài dependencies**:
```bash
pip install -r requirements.txt
```

3. **Cài trình duyệt Playwright**:
```bash
playwright install chromium
```

4. **Cập nhật requirements.txt** (khuyến nghị thêm các dependency còn thiếu):
```bash
# Thêm vào requirements.txt nếu chưa có:
# beautifulsoup4>=4.12
# lxml>=4.9
# requests>=2.31
```

### Sử Dụng

#### 1. Tải Truyện

Tạo file `input.txt` với URL truyện (mỗi dòng một URL):
```
https://uukanshu.cc/book/17474/
https://uukanshu.cc/book/25060/
```

Chạy crawler:
```bash
python cralw.py --input input.txt --run-auto
```

**Tùy chọn**:
- `--root`: Thư mục gốc cho truyện (mặc định: `./truyen`)
- `--db`: Đường dẫn file database (mặc định: `novel_index.sqlite`)
- `--min-length`: Độ dài tối thiểu chương (mặc định: 400 ký tự)
- `--skip-registered`: Chỉ xử lý URL từ file input, bỏ qua truyện đã đăng ký
- `--run-auto`: Tự động chạy dịch sau khi tải chương mới

#### 2. Dịch Chương

**Dịch thủ công**:
```bash
python auto.py
```

**Với tùy chọn tùy chỉnh**:
```bash
python auto.py --root /duong-dan/truyen --profiles "~/chrome1,~/chrome2,~/chrome3"
```

**Tùy chọn**:
- `--root`: Thư mục gốc chứa thư mục truyện (mặc định: `./truyen`)
- `--profiles`: Danh sách các đường dẫn profile Chrome, phân cách bằng dấu phẩy
- `--headless`: Chạy Chrome ở chế độ headless (không khuyến nghị cho debug)

#### 3. Tự Động Hóa Hằng Ngày

Thiết lập cron job để kiểm tra chương mới mỗi ngày:

```bash
# Thêm vào crontab (crontab -e)
0 2 * * * cd /path/to/dich_votthinhan && python cralw.py --run-auto
```

### Quy Trình Dịch

1. **Khởi tạo** (3 chương đầu):
   - Phân tích ngữ cảnh truyện, nhân vật và quan hệ
   - Tạo database ban đầu với các mục glossary
   - Xác định góc nhìn tường thuật và đại từ

2. **Dịch thuật** (các chương tiếp theo):
   - Tải ngữ cảnh liên quan từ database
   - Tạo prompt dịch nhận biết ngữ cảnh
   - Dịch chương duy trì tính nhất quán
   - Cập nhật database với nhân vật/quan hệ mới

3. **Đảm Bảo Chất Lượng**:
   - Phát hiện và loại bỏ ký tự tiếng Trung còn sót
   - Chuyển dấu câu tiếng Trung sang tiếng Việt
   - Đảm bảo phản hồi AI ổn định trước khi tiếp tục

### Cấu Hình

#### System Prompt

Tạo file `system_prompt.md` để tùy chỉnh hành vi AI:
```markdown
Bạn là một dịch giả văn học chuyên nghiệp, có khả năng dịch truyện Trung Việt với chất lượng cao.
```

#### Chrome Profiles

Mặc định, công cụ sử dụng 6 profile Chrome (`~/chrome-for-automation0` đến `~/chrome-for-automation5`). Bạn có thể tùy chỉnh:

```python
# Trong auto.py hoặc qua command line
--profiles "~/profile1,~/profile2"
```

### Phát Triển

#### Cấu Trúc Dự Án

```
.
├── auto.py                 # Script tự động hóa dịch thuật chính
├── browser_utils.py        # Tiện ích tương tác trình duyệt (MỚI)
├── config.py              # Hằng số cấu hình (MỚI)
├── cralw.py               # Web scraping cho chương
├── context_builder.py     # Trích xuất ngữ cảnh từ database
├── prompt_builder.py      # Tạo prompt cho AI
├── response_parser.py     # Phân tích phản hồi AI
├── story_db.py           # Thao tác database truyện
├── novel_db.py           # Thao tác database chỉ mục truyện
├── epub_builder.py       # Tạo EPUB (tùy chọn)
├── cleanup_db.py         # Tiện ích bảo trì database
└── tests/                # Bộ test
    ├── test_auto_helpers.py
    ├── test_context_builder.py
    ├── test_cralw_helpers.py
    ├── test_prompt_builder.py
    └── test_response_parser.py
```

#### Chạy Tests

```bash
python -m pytest
```

#### Chất Lượng Code

Codebase đã được refactor để dễ bảo trì hơn:
- Tách cấu hình vào `config.py`
- Trích xuất tiện ích trình duyệt vào `browser_utils.py`
- Thêm docstring toàn diện
- Cải thiện type hints
- Xử lý lỗi tốt hơn

### Xử Lý Sự Cố

#### Vấn Đề Thường Gặp

**1. Lỗi "Content blocked"**:
- Chỉnh sửa system prompt của bạn để ít rõ ràng hơn
- Thử cách diễn đạt khác trong prompt
- Sử dụng profile Chrome khác

**2. Giới hạn tần suất**:
- Công cụ tự động xoay vòng profile
- Đảm bảo bạn có nhiều profile Chrome đã cấu hình
- Thời gian chờ giữa các request đã được tích hợp sẵn

**3. Bản dịch bị thiếu**:
- Kiểm tra xem khởi tạo đã hoàn tất thành công chưa
- Xác minh database tồn tại trong thư mục truyện
- Xem lại log để tìm lỗi parse

**4. Ký tự tiếng Trung còn sót trong bản dịch**:
- Công cụ thử tự động dọn dẹp
- Có thể cần điều chỉnh `MAX_CHINESE_FIX_ROUNDS` trong config

### Đóng Góp

Chào đón đóng góp! Vui lòng:
1. Fork repository
2. Tạo branch tính năng
3. Thêm test cho chức năng mới
4. Đảm bảo tất cả test pass
5. Gửi pull request

### Giấy Phép

Dự án này được cung cấp as-is cho mục đích giáo dục.

### Lời Cảm Ơn

- Sử dụng Google AI Studio cho dịch thuật
- Web scraping từ uukanshu.cc
- Xây dựng với Playwright cho tự động hóa trình duyệt
