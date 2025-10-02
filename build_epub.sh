#!/bin/bash
# Script tiện lợi để build EPUB từ folder chứa các file truyện

# Màu sắc để output đẹp hơn
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}📚 EPUB Builder Tool${NC}"
echo -e "${BLUE}=====================${NC}"

# Kiểm tra Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 không được tìm thấy!${NC}"
    exit 1
fi

# Function để hiển thị usage
show_usage() {
    echo -e "${YELLOW}Cách sử dụng:${NC}"
    echo "  ./build_epub.sh <folder_truyen> [tên_tác_phẩm] [tác_giả]"
    echo ""
    echo -e "${YELLOW}Ví dụ:${NC}"
    echo "  ./build_epub.sh dich_votthinhan"
    echo "  ./build_epub.sh dich_votthinhan \"Dịch Võ Thị Nhân\" \"Tác giả\""
    echo "  ./build_epub.sh my_novel \"Tiểu thuyết hay\" \"Người viết\""
    echo ""
    echo -e "${YELLOW}Chú ý:${NC}"
    echo "  - Tool sẽ tự động kiểm tra và chỉ build những file có nội dung"
    echo "  - File EPUB sẽ được tạo trong thư mục hiện tại"
    echo "  - Hỗ trợ file .txt với định dạng markdown đơn giản"
}

# Kiểm tra tham số
if [ $# -eq 0 ]; then
    echo -e "${RED}❌ Thiếu tham số!${NC}"
    echo ""
    show_usage
    exit 1
fi

# Lấy tham số
FOLDER="$1"
TITLE="${2:-$(basename "$FOLDER")}"
AUTHOR="${3:-Tác giả}"

# Kiểm tra folder tồn tại
if [ ! -d "$FOLDER" ]; then
    echo -e "${RED}❌ Thư mục không tồn tại: $FOLDER${NC}"
    exit 1
fi

# Kiểm tra có file .txt không
TXT_COUNT=$(find "$FOLDER" -name "*.txt" | wc -l)
if [ "$TXT_COUNT" -eq 0 ]; then
    echo -e "${RED}❌ Không tìm thấy file .txt nào trong thư mục: $FOLDER${NC}"
    exit 1
fi

echo -e "${GREEN}📁 Thư mục:${NC} $FOLDER"
echo -e "${GREEN}📖 Tiêu đề:${NC} $TITLE"
echo -e "${GREEN}✍️  Tác giả:${NC} $AUTHOR"
echo -e "${GREEN}📄 Tìm thấy:${NC} $TXT_COUNT file .txt"
echo ""

# Xác nhận từ người dùng
echo -e "${YELLOW}Bạn có muốn tiếp tục build EPUB? (y/N):${NC} "
read -r CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}⏹️  Đã hủy.${NC}"
    exit 0
fi

# Tạo tên file output
OUTPUT_FILE="${TITLE// /_}.epub"
OUTPUT_FILE=$(echo "$OUTPUT_FILE" | sed 's/[^a-zA-Z0-9._-]//g')

echo ""
echo -e "${BLUE}🔨 Bắt đầu build EPUB...${NC}"
echo ""

# Chạy Python script
python3 epub_builder.py "$FOLDER" -t "$TITLE" -a "$AUTHOR" -o "$OUTPUT_FILE"
BUILD_STATUS=$?

echo ""
if [ $BUILD_STATUS -eq 0 ]; then
    echo -e "${GREEN}✅ Build thành công!${NC}"
    echo -e "${GREEN}📁 File đã tạo:${NC} $OUTPUT_FILE"
    
    # Hiển thị thông tin file
    if [ -f "$OUTPUT_FILE" ]; then
        FILE_SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
        echo -e "${GREEN}📏 Kích thước:${NC} $FILE_SIZE"
        
        # Gợi ý cách mở file
        echo ""
        echo -e "${YELLOW}💡 Gợi ý:${NC}"
        echo "  - Bạn có thể mở file EPUB bằng:"
        echo "    • Calibre (https://calibre-ebook.com/)"
        echo "    • Adobe Digital Editions"
        echo "    • Apple Books (trên macOS/iOS)"
        echo "    • Google Play Books"
        echo "    • Hoặc trình đọc EPUB khác"
    fi
else
    echo -e "${RED}❌ Build thất bại!${NC}"
    exit 1
fi
