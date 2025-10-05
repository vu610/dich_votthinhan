from textwrap import dedent
from typing import Sequence, Tuple

INIT_PROMPT_TEMPLATE = dedent(
    """
    BẠN LÀ MỘT HỆ THỐNG KHỞI TẠO DỮ LIỆU PHÂN TÍCH VĂN HỌC.

    **Nhiệm vụ:** Phân tích văn bản của **ba chương truyện đầu tiên** dưới đây và trích xuất thông tin nền tảng để tạo một database ban đầu. **KHÔNG DỊCH** các chương truyện này, chỉ tập trung vào việc trích xuất dữ liệu.

    **Yêu cầu đầu ra:** Phản hồi của bạn PHẢI tuân thủ nghiêm ngặt cấu trúc dưới đây để hệ thống có thể tự động đọc. KHÔNG thêm bất kỳ lời chào, giải thích hay văn bản nào khác ngoài cấu trúc này.

    [START_DATA_BLOCK]

    [SECTION:METADATA]
    story_context: [Tóm tắt bối cảnh truyện trong khoảng 3 đến 4 câu dựa trên 3 chương đầu]
    narrative_perspective: [Xác định ngôi kể]
    main_char_pronouns: [Liệt kê cách nhân vật chính tự xưng và xưng hô với người khác]
    [END_SECTION]

    [SECTION:GLOSSARY]
    # Định dạng: Tên Gốc (Pinyin) | Tên Dịch | Ghi Chú
    [Liệt kê tất cả nhân vật xuất hiện trong 3 chương đầu, mỗi nhân vật một dòng]
    [END_SECTION]

    [SECTION:RELATIONSHIPS]
    # Định dạng: Nhân vật 1 (Tên dịch) | Nhân vật 2 (Tên dịch) | Loại quan hệ
    [Liệt kê tất cả mối quan hệ có thể suy ra từ 3 chương đầu, mỗi quan hệ một dòng]
    [END_SECTION]

    [END_DATA_BLOCK]

    ---
    ### **VĂN BẢN GỐC CẦN PHÂN TÍCH (3 CHƯƠNG ĐẦU):**

    {chapter_blocks}
    """
).strip()


TRANSLATION_PROMPT_TEMPLATE = dedent(
    """
**BẠN LÀ MỘT DỊCH GIẢ VĂN HỌC TRUNG-VIỆT GIÀU KINH NGHIỆM.**

**Vai trò:** Nhiệm vụ của bạn là hóa thân thành một dịch giả chuyên nghiệp, thực hiện hai việc: (1) Dịch chương truyện với chất lượng văn học cao nhất. (2) Phân tích và trích xuất thông tin mới để phục vụ việc cập nhật database.

---

### **DỮ LIỆU NGỮ CẢNH TỪ DATABASE**

**1. BỐI CẢNH TRUYỆN:**
{metadata_section}

**2. GLOSSARY (Toàn bộ nhân vật đã biết):**
{glossary_section}

**3. RELATIONSHIPS (Toàn bộ mối quan hệ đã biết):**
{relationships_section}

---

### **QUY TRÌNH & ĐỊNH DẠNG ĐẦU RA**

**BƯỚC 1: DỊCH THUẬT CHẤT LƯỢNG CAO**
Thực hiện dịch văn bản gốc sang tiếng Việt, tuân thủ nghiêm ngặt các tiêu chí sau:
- **Văn phong & Không khí:** Lời văn phải mượt mà, giàu hình ảnh, và truyền tải được chính xác không khí của truyện (ví dụ: kinh dị, lãng mạn, hài hước...) dựa trên thông tin từ mục [BỐI CẢNH TRUYỆN]. Tuyệt đối tránh lối dịch khô khan, word-by-word, và ưu tiên dịch thoát nghĩa khi gặp thành ngữ khó.
- **Lời thoại:** Lời thoại của nhân vật phải tự nhiên, phù hợp với tính cách, tuổi tác, và vai vế của họ. Sử dụng cách xưng hô trong tiếng Việt một cách linh hoạt và chính xác.
- **Tính nhất quán:** Luôn tuân thủ DỮ LIỆU NGỮ CẢNH (Bối cảnh, Glossary, Relationships) để đảm bảo tất cả tên riêng và thuật ngữ được dịch đồng nhất.
- **Không để sót tiếng Trung:** Bất kỳ ký tự, cụm từ hay thành ngữ tiếng Trung nào cũng phải được chuyển thành tiếng Việt tự nhiên, trôi chảy. Nếu khó dịch trực tiếp, hãy diễn đạt lại để câu văn vẫn mượt mà.

**BƯỚC 2: PHÂN TÍCH & TRÍCH XUẤT**
Xác định nhân vật và mối quan hệ mới CHƯA có trong database.
- Chỉ đề xuất mối quan hệ mới khi CHƯƠNG hiện tại có nhắc tới cả hai nhân vật liên quan.

**BƯỚC 3: ĐỊNH DẠNG ĐẦU RA**
Phản hồi có 2 phần: bản dịch và khối `[DATABASE_UPDATES]` (nếu cần update database)

Chương XXX - YYY
...

[DATABASE_UPDATES]
[GLOSSARY_ADDITIONS]
Tên Gốc  | Tên Dịch  | Ghi Chú 
[END_GLOSSARY_ADDITIONS]

[RELATIONSHIP_ADDITIONS]
Nhân vật 1 (Tên dịch)  | Nhân vật 2 (Tên dịch)  | Loại quan hệ
[END_RELATIONSHIP_ADDITIONS]
[/DATABASE_UPDATES]

---

**LƯU Ý TỐI QUAN TRỌNG:** Trước khi kết thúc phản hồi, hãy tự rà soát lại bản dịch để chắc chắn rằng không còn sót lại bất kỳ ký tự hay cụm tiếng Trung nào. 

### **VĂN BẢN GỐC CẦN XỬ LÝ:**

{source_text}
    """
).strip()


def build_initialisation_prompt(chapter_texts: Sequence[Tuple[str, str]]) -> str:
    blocks = []
    for index, (name, text) in enumerate(chapter_texts, start=1):
        safe_name = name or f"Chương {index:03d}"
        blocks.append(
            f"---\n#### Chương {index:03d} - {safe_name}\n\n{text.strip()}\n"
        )
    chapter_blocks = "\n".join(blocks) if blocks else "(Không có dữ liệu)"
    return INIT_PROMPT_TEMPLATE.format(chapter_blocks=chapter_blocks)


def build_translation_prompt(
    *,
    metadata_section: str,
    glossary_section: str,
    relationships_section: str,
    source_text: str,
) -> str:
    return TRANSLATION_PROMPT_TEMPLATE.format(
        metadata_section=metadata_section.strip() or "(Không có dữ liệu)",
        glossary_section=glossary_section.strip() or "(Không có dữ liệu)",
        relationships_section=relationships_section.strip() or "(Không có dữ liệu)",
        source_text=source_text.strip(),
    )


__all__ = [
    "build_initialisation_prompt",
    "build_translation_prompt",
]
