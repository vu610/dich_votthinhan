#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os

def create_chapter_files():
    """
    Tạo 500 file txt trống có tên từ chuong_001 đến chuong_500
    """
    # Thư mục đích
    target_dir = "dich_votthinhan"
    
    # Tạo thư mục nếu chưa tồn tại
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        print(f"Đã tạo thư mục: {target_dir}")
    
    # Tạo 500 file
    for i in range(1, 501):
        filename = f"chuong_{i:03d}.txt"  # Format số với 3 chữ số (001, 002, ...)
        filepath = os.path.join(target_dir, filename)
        
        # Tạo file trống
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("")  # File trống
        
        # In tiến độ mỗi 50 file
        if i % 50 == 0:
            print(f"Đã tạo {i} file...")
    
    print(f"Hoàn thành! Đã tạo 500 file txt trong thư mục '{target_dir}'")

if __name__ == "__main__":
    create_chapter_files()
