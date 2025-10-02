#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tool để chuyển đổi tên file từ định dạng số Trung Quốc sang định dạng chuong_xxx.txt
"""

import os
import re
import sys

def extract_chapter_number(filename):
    """
    Trích xuất số chương từ tên file
    Patterns:
    - 001_第一章.txt -> 001
    - 031_第31章.txt -> 031  
    - 030_上架感言！.txt -> 030
    - 051_第51章 （本卷完）.txt -> 051
    """
    # Lấy số đầu filename (001, 002, etc.)
    match = re.match(r'^(\d{3})_', filename)
    if match:
        return match.group(1)
    return None

def rename_files_in_directory(directory_path):
    """
    Đổi tên tất cả file trong thư mục
    """
    if not os.path.exists(directory_path):
        print(f"Thư mục không tồn tại: {directory_path}")
        return False
    
    files = os.listdir(directory_path)
    txt_files = [f for f in files if f.endswith('.txt')]
    
    if not txt_files:
        print("Không tìm thấy file .txt nào trong thư mục")
        return False
    
    renamed_count = 0
    skipped_files = []
    
    print(f"Tìm thấy {len(txt_files)} file .txt")
    print("Bắt đầu đổi tên...")
    
    for filename in txt_files:
        chapter_num = extract_chapter_number(filename)
        
        if chapter_num:
            old_path = os.path.join(directory_path, filename)
            new_filename = f"chuong_{chapter_num}.txt"
            new_path = os.path.join(directory_path, new_filename)
            
            # Kiểm tra xem file đích đã tồn tại chưa
            if os.path.exists(new_path):
                print(f"Bỏ qua: {new_filename} đã tồn tại")
                skipped_files.append(filename)
                continue
            
            try:
                os.rename(old_path, new_path)
                print(f"✓ {filename} -> {new_filename}")
                renamed_count += 1
            except Exception as e:
                print(f"✗ Lỗi khi đổi tên {filename}: {e}")
                skipped_files.append(filename)
        else:
            print(f"Bỏ qua: {filename} (không nhận diện được số chương)")
            skipped_files.append(filename)
    
    print(f"\nKết quả:")
    print(f"- Đã đổi tên: {renamed_count} file")
    print(f"- Bỏ qua: {len(skipped_files)} file")
    
    if skipped_files:
        print(f"Các file bỏ qua:")
        for f in skipped_files:
            print(f"  - {f}")
    
    return True

def main():
    # Sử dụng thư mục hiện tại nếu không có tham số
    if len(sys.argv) > 1:
        directory = sys.argv[1]
    else:
        directory = input("Nhập đường dẫn thư mục (Enter để sử dụng thư mục hiện tại): ").strip()
        if not directory:
            directory = "."
    
    # Chuyển đổi đường dẫn tương đối thành tuyệt đối
    directory = os.path.abspath(directory)
    
    print(f"Thư mục làm việc: {directory}")
    
    # Xác nhận trước khi thực hiện
    confirm = input("Bạn có chắc muốn đổi tên tất cả file? (y/N): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("Hủy bỏ thao tác")
        return
    
    rename_files_in_directory(directory)

if __name__ == "__main__":
    main()
