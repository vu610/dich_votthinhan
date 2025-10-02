#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://uukanshu.cc"

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
]

CONTENT_SELECTORS = [
    "#content", "#content1", "#BookText", "#BookContent", "#booktxt", "#chaptercontent",
    ".bookcontent", ".read-content", ".content-body", "article",
]

CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")

def make_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": random.choice(UA_POOL),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8,vi;q=0.7",
        "Referer": BASE,
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    return s

def get_soup(session: requests.Session, url: str, tries: int = 3) -> BeautifulSoup:
    last = None
    for i in range(tries):
        r = session.get(url, timeout=25)
        last = r
        if r.status_code == 200 and "text/html" in r.headers.get("Content-Type", ""):
            r.encoding = r.apparent_encoding or "utf-8"
            return BeautifulSoup(r.text, "lxml")
        time.sleep(1.0 + i * 1.2 + random.random())
    raise RuntimeError(f"Fetch fail {url} (status={getattr(last,'status_code',None)})")

def clean_text(text: str) -> str:
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    kept = []
    for ln in lines:
        if not ln:
            kept.append("")
            continue
        boiler = ("UU看書", "UU看书", "加入書籤", "投票推薦", "小說報錯", "目录", "目錄", "上一章", "下一章")
        if any(k in ln for k in boiler):
            continue
        if len(ln) < 2 and not CHINESE_RE.search(ln):
            continue
        kept.append(ln)
    out = []
    blank = 0
    for ln in kept:
        if ln == "":
            blank += 1
            if blank <= 1:
                out.append("")
        else:
            blank = 0
            out.append(ln)
    return "\n".join(out).strip() + "\n"

def extract_chapter(session: requests.Session, url: str):
    soup = get_soup(session, url)
    title_el = soup.select_one("h1, .title, .bookname h1")
    title = title_el.get_text(strip=True) if title_el else ""
    node = None
    for sel in CONTENT_SELECTORS:
        cand = soup.select_one(sel)
        if cand and len(cand.get_text(strip=True)) > 200:
            node = cand
            break
    if node:
        for bad in node.select("script,style,ins,iframe,.ads,.ad,.advert"):
            bad.decompose()
        parts = []
        for el in node.find_all(["p", "div", "br"]):
            t = el.get_text(" ", strip=True)
            if t:
                parts.append(t)
        raw = "\n".join(parts)
    else:
        body = soup.body or soup
        paras = []
        for el in body.find_all(["p", "div", "br"]):
            t = el.get_text(" ", strip=True)
            if t:
                paras.append(t)
        raw = "\n".join(paras)
    text = clean_text(raw)
    return title, text

def get_book_info(session: requests.Session, index_url: str):
    soup = get_soup(session, index_url)
    meta = soup.find("meta", {"property": "og:novel:book_name"})
    book_title = meta["content"].strip() if meta and meta.get("content") else None
    if not book_title:
        h1 = soup.select_one("h1, .booktitle, .book-info h1")
        book_title = h1.get_text(strip=True) if h1 else "uukanshu_book"
    links = []
    for a in soup.select(".chapterlist a[href$='.html'], #list-chapterAll a[href$='.html']"):
        href = a.get("href")
        if not href:
            continue
        url = urljoin(index_url, href)
        if "/book/" in url and url.endswith(".html"):
            text = a.get_text(strip=True) or ""
            links.append((text, url))
    seen = set()
    ordered = []
    for t, u in links:
        if u not in seen:
            seen.add(u)
            ordered.append((t, u))
    if not ordered:
        raise RuntimeError("Không tìm thấy link chương. Có thể cấu trúc trang đã đổi.")
    return book_title, ordered

def safe_name(s: str) -> str:
    s = s.strip()
    # thay ký tự nguy hiểm
    s = re.sub(r'[\\/*?:"<>|]+', "_", s)
    # gọn hơn
    s = re.sub(r"\s+", " ", s)
    return s[:120] if len(s) > 120 else s

def main():
    ap = argparse.ArgumentParser(description="Crawl uukanshu.cc -> TXT (hỗ trợ tách từng chương).")
    ap.add_argument("--start", required=True, help="Index URL hoặc URL chương bất kỳ")
    ap.add_argument("--out", default=None, help="Đường dẫn file TXT hợp nhất (khi KHÔNG dùng --split).")
    ap.add_argument("--from_ch", type=int, default=None, help="Bắt đầu từ chương N (nếu dùng URL mục lục).")
    ap.add_argument("--limit", type=int, default=None, help="Chỉ tải tối đa N chương.")
    ap.add_argument("--split", action="store_true", help="Bật chế độ lưu MỖI CHƯƠNG MỘT FILE.")
    ap.add_argument("--outdir", default=None, help="Thư mục chứa file chương (mặc định = tên truyện).")
    ap.add_argument("--no-prefix", action="store_true", help="Không thêm tiền tố số thứ tự vào tên file chương.")
    ap.add_argument("--pad", type=int, default=None, help="Độ dài zero-padding số thứ tự (vd 3 -> 001).")
    args = ap.parse_args()

    session = make_session()
    start = args.start.strip()

    # xác định URL mục lục
    if start.endswith("/"):
        index_url = start
    else:
        m = re.search(r"(https?://[^/]+/book/\d+)/", start)
        index_url = (m.group(1) + "/") if m else start

    book_title, chapters = get_book_info(session, index_url)

    # vị trí bắt đầu
    start_idx = 0
    if start.endswith(".html"):
        for i, (_, u) in enumerate(chapters):
            if u.rstrip("/") == start.rstrip("/"):
                start_idx = i
                break
    elif args.from_ch:
        start_idx = max(0, args.from_ch - 1)

    to_fetch = chapters[start_idx:]
    if args.limit:
        to_fetch = to_fetch[:args.limit]

    print(f"Book: {book_title} | Tổng chương: {len(chapters)} | Sẽ tải: {len(to_fetch)}")

    if args.split:
        outdir = Path(args.outdir or safe_name(book_title))
        outdir.mkdir(parents=True, exist_ok=True)
        pad = args.pad if args.pad is not None else max(3, len(str(len(chapters))))
        idx_path = outdir / "index.txt"
        with idx_path.open("w", encoding="utf-8") as idxf:
            idxf.write(f"{book_title}\n{'='*80}\n\n")
        fetched = 0
        for i, (ch_anchor_text, ch_url) in enumerate(to_fetch, start=1):
            try:
                t, body = extract_chapter(session, ch_url)
                title = t or ch_anchor_text or f"Chapter {start_idx + i}"
                base = safe_name(title)
                if not args.no_prefix:
                    prefix = str(start_idx + i).zfill(pad)
                    fname = f"{prefix}_{base}.txt"
                else:
                    fname = f"{base}.txt"
                with (outdir / fname).open("w", encoding="utf-8") as f:
                    f.write(title + "\n")
                    f.write("-" * 80 + "\n\n")
                    f.write(body)
                with idx_path.open("a", encoding="utf-8") as idxf:
                    idxf.write(f"{str(start_idx + i).zfill(pad)}\t{title}\t{ch_url}\n")
                fetched += 1
                print(f"[{fetched}/{len(to_fetch)}] OK {title} -> {fname}")
            except Exception as e:
                print(f"FAIL {ch_url}: {e}", file=sys.stderr)
            time.sleep(0.8 + random.random())  # lịch sự
        print(f"Done. Files at: {outdir.resolve()}")
    else:
        # chế độ gộp như cũ
        out_path = args.out or f"{safe_name(book_title)}.txt"
        fetched = 0
        with open(out_path, "w", encoding="utf-8") as f:
            for (ch_name, ch_url) in to_fetch:
                try:
                    t, body = extract_chapter(session, ch_url)
                    title = t or ch_name
                    f.write(title + "\n")
                    f.write("-" * 80 + "\n\n")
                    f.write(body)
                    f.write("\n" + "=" * 80 + "\n\n")
                    fetched += 1
                    print(f"[{fetched}/{len(to_fetch)}] OK {title}")
                except Exception as e:
                    print(f"FAIL {ch_url}: {e}", file=sys.stderr)
                time.sleep(0.8 + random.random())
        print(f"Done. Output: {Path(out_path).resolve()}")

if __name__ == "__main__":
    main()
