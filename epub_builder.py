#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tool để build truyện từ các file text thành file EPUB
Chỉ build những file có nội dung (không trống)
"""

import os
import re
import zipfile
import uuid
from datetime import datetime
from pathlib import Path
import argparse

class EpubBuilder:
    def __init__(self, input_folder, output_file=None, title="Truyện", author="Tác giả"):
        self.input_folder = Path(input_folder)
        self.output_file = output_file or f"{title.replace(' ', '_')}.epub"
        self.title = title
        self.author = author
        self.book_id = str(uuid.uuid4())
        self.chapters = []
        
    def scan_chapters(self):
        """Quét các file chương và chỉ lấy những file có nội dung"""
        print("Đang quét các file chương...")
        
        # Tìm tất cả file .txt trong folder
        txt_files = list(self.input_folder.glob("*.txt"))
        
        # Sắp xếp theo số thứ tự chương
        def extract_chapter_number(filename):
            match = re.search(r'(\d+)', filename.name)
            return int(match.group(1)) if match else 0
        
        txt_files.sort(key=extract_chapter_number)
        
        # Kiểm tra file nào có nội dung
        valid_chapters = []
        for file_path in txt_files:
            if file_path.stat().st_size > 0:  # File không trống
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:  # Có nội dung thực sự
                            valid_chapters.append({
                                'file': file_path,
                                'title': self.extract_chapter_title(content),
                                'content': content
                            })
                            print(f"✓ {file_path.name} - Có nội dung ({file_path.stat().st_size} bytes)")
                        else:
                            print(f"✗ {file_path.name} - File trống")
                except Exception as e:
                    print(f"✗ {file_path.name} - Lỗi đọc file: {e}")
            else:
                print(f"✗ {file_path.name} - File trống (0 bytes)")
        
        self.chapters = valid_chapters
        print(f"\nTìm thấy {len(self.chapters)} chương có nội dung")
        return len(self.chapters)
    
    def extract_chapter_title(self, content):
        """Trích xuất tiêu đề chương từ nội dung"""
        lines = content.split('\n')
        for line in lines[:5]:  # Chỉ kiểm tra 5 dòng đầu
            line = line.strip()
            if line.startswith('###') or line.startswith('**Chương') or line.startswith('Chương'):
                # Loại bỏ markdown formatting
                title = re.sub(r'[#*]', '', line).strip()
                return title
        
        # Nếu không tìm thấy, dùng dòng đầu tiên không trống
        for line in lines:
            line = line.strip()
            if line and not line.startswith('###'):
                return line[:50] + "..." if len(line) > 50 else line
        
        return "Chương không tên"
    
    def create_mimetype(self):
        """Tạo file mimetype"""
        return "application/epub+zip"
    
    def create_container_xml(self):
        """Tạo META-INF/container.xml"""
        return '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>'''
    
    def create_content_opf(self):
        """Tạo OEBPS/content.opf"""
        # Tạo danh sách manifest
        manifest_items = []
        spine_items = []
        
        # Thêm CSS
        manifest_items.append('<item id="style" href="style.css" media-type="text/css"/>')
        
        # Thêm các chương
        for i, chapter in enumerate(self.chapters):
            chapter_id = f"chapter_{i+1:03d}"
            manifest_items.append(f'<item id="{chapter_id}" href="{chapter_id}.xhtml" media-type="application/xhtml+xml"/>')
            spine_items.append(f'<itemref idref="{chapter_id}"/>')
        
        manifest_content = '\n        '.join(manifest_items)
        spine_content = '\n        '.join(spine_items)
        
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<package version="3.0" xmlns="http://www.idpf.org/2007/opf" unique-identifier="book-id">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:identifier id="book-id">{self.book_id}</dc:identifier>
        <dc:title>{self.title}</dc:title>
        <dc:creator>{self.author}</dc:creator>
        <dc:language>vi</dc:language>
        <meta property="dcterms:modified">{datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')}</meta>
    </metadata>
    <manifest>
        {manifest_content}
    </manifest>
    <spine>
        {spine_content}
    </spine>
</package>'''
    
    def create_css(self):
        """Tạo CSS cho styling"""
        return '''body {
    font-family: "Times New Roman", serif;
    font-size: 1.1em;
    line-height: 1.6;
    margin: 2em;
    text-align: justify;
}

h1, h2, h3 {
    color: #333;
    text-align: center;
    margin: 2em 0 1em 0;
}

h1 {
    font-size: 1.8em;
    border-bottom: 2px solid #333;
    padding-bottom: 0.5em;
}

h2 {
    font-size: 1.5em;
}

h3 {
    font-size: 1.3em;
}

p {
    margin: 1em 0;
    text-indent: 2em;
}

.chapter-title {
    font-size: 1.6em;
    font-weight: bold;
    text-align: center;
    margin: 2em 0;
    color: #2c3e50;
}

.page-break {
    page-break-before: always;
}'''
    
    def create_chapter_xhtml(self, chapter, chapter_num):
        """Tạo file XHTML cho một chương"""
        chapter_id = f"chapter_{chapter_num:03d}"
        title = chapter['title']
        content = chapter['content']
        
        # Xử lý nội dung: chuyển đổi markdown đơn giản và format đoạn văn
        formatted_content = self.format_content(content)
        
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="vi">
<head>
    <title>{title}</title>
    <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
    <div class="page-break">
        <h1 class="chapter-title">{title}</h1>
        {formatted_content}
    </div>
</body>
</html>'''
    
    def format_content(self, content):
        """Format nội dung từ markdown đơn giản sang HTML"""
        lines = content.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Bỏ qua dòng tiêu đề (đã xử lý ở trên)
            if line.startswith('###') or (line.startswith('**') and line.endswith('**') and 'Chương' in line):
                continue
            
            # Xử lý tiêu đề phụ
            if line.startswith('##'):
                line = line.replace('##', '').strip()
                formatted_lines.append(f'<h2>{line}</h2>')
            elif line.startswith('#'):
                line = line.replace('#', '').strip()
                formatted_lines.append(f'<h3>{line}</h3>')
            else:
                # Xử lý đoạn văn bình thường
                # Escape HTML characters
                line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                formatted_lines.append(f'<p>{line}</p>')
        
        return '\n        '.join(formatted_lines)
    
    def build_epub(self):
        """Build file EPUB"""
        if not self.chapters:
            print("Không có chương nào để build!")
            return False
        
        print(f"\nĐang tạo file EPUB: {self.output_file}")
        
        try:
            with zipfile.ZipFile(self.output_file, 'w', zipfile.ZIP_DEFLATED) as epub:
                # Thêm mimetype (không nén)
                epub.writestr('mimetype', self.create_mimetype(), compress_type=zipfile.ZIP_STORED)
                
                # Thêm META-INF/container.xml
                epub.writestr('META-INF/container.xml', self.create_container_xml())
                
                # Thêm OEBPS/content.opf
                epub.writestr('OEBPS/content.opf', self.create_content_opf())
                
                # Thêm CSS
                epub.writestr('OEBPS/style.css', self.create_css())
                
                # Thêm các file chương
                for i, chapter in enumerate(self.chapters):
                    chapter_xhtml = self.create_chapter_xhtml(chapter, i + 1)
                    chapter_filename = f'OEBPS/chapter_{i+1:03d}.xhtml'
                    epub.writestr(chapter_filename, chapter_xhtml)
                    print(f"  ✓ Đã thêm: {chapter['title']}")
            
            print(f"\n🎉 Đã tạo thành công file EPUB: {self.output_file}")
            print(f"📊 Thống kê:")
            print(f"   - Số chương: {len(self.chapters)}")
            print(f"   - Kích thước file: {os.path.getsize(self.output_file) / 1024:.2f} KB")
            return True
            
        except Exception as e:
            print(f"❌ Lỗi khi tạo EPUB: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description='Build truyện từ các file text thành EPUB')
    parser.add_argument('input_folder', help='Thư mục chứa các file chương (.txt)')
    parser.add_argument('-o', '--output', help='Tên file EPUB đầu ra')
    parser.add_argument('-t', '--title', default='Truyện', help='Tiêu đề truyện')
    parser.add_argument('-a', '--author', default='Tác giả', help='Tên tác giả')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_folder):
        print(f"❌ Thư mục không tồn tại: {args.input_folder}")
        return
    
    # Tạo tên file output mặc định nếu không được chỉ định
    if not args.output:
        folder_name = os.path.basename(args.input_folder.rstrip('/'))
        args.output = f"{folder_name}.epub"
    
    print(f"📚 EPUB Builder")
    print(f"📁 Thư mục input: {args.input_folder}")
    print(f"📖 Tiêu đề: {args.title}")
    print(f"✍️  Tác giả: {args.author}")
    print(f"💾 File output: {args.output}")
    print("=" * 50)
    
    # Tạo builder và build EPUB
    builder = EpubBuilder(args.input_folder, args.output, args.title, args.author)
    
    # Quét các chương
    chapter_count = builder.scan_chapters()
    if chapter_count == 0:
        print("❌ Không tìm thấy file chương nào có nội dung!")
        return
    
    # Build EPUB
    success = builder.build_epub()
    if success:
        print(f"\n✅ Hoàn thành! Bạn có thể mở file {args.output} bằng trình đọc EPUB.")
    else:
        print("\n❌ Build thất bại!")

if __name__ == "__main__":
    main()
