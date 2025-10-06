#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import hashlib
from datetime import UTC, datetime
import sqlite3
import os
import random
import re
import subprocess
import sys
import time
import logging
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

import novel_db

BASE = "https://uukanshu.cc"

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
]

CONTENT_SELECTORS = [
    "#content",
    "#content1",
    "#BookText",
    "#BookContent",
    "#booktxt",
    "#chaptercontent",
    ".bookcontent",
    ".read-content",
    ".readcotent",
    ".content-body",
    "article",
]

CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")

INDEX_LINK_SELECTOR = ".chapterlist a[href$='.html'], #list-chapterAll a[href$='.html']"

MIN_TEXT_LENGTH = 400

logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ChapterLink:
    index: int
    title: str
    url: str


@dataclass
class BookData:
    title: str
    author: Optional[str]
    description: Optional[str]
    cover_url: Optional[str]
    status: Optional[str]
    latest_chapter_name: Optional[str]
    latest_chapter_url: Optional[str]
    chapters: List[ChapterLink]


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": random.choice(UA_POOL),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8,vi;q=0.7",
            "Referer": BASE,
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
    )
    return session


def get_soup(session: requests.Session, url: str, tries: int = 3) -> BeautifulSoup:
    last_response = None
    for attempt in range(tries):
        response = session.get(url, timeout=30)
        last_response = response
        if response.status_code == 200 and "text/html" in response.headers.get("Content-Type", ""):
            response.encoding = response.apparent_encoding or "utf-8"
            return BeautifulSoup(response.text, "lxml")
        sleep_for = 1.0 + attempt * 1.2 + random.random()
        time.sleep(sleep_for)
    raise RuntimeError(
        f"Fetch fail {url} (status={getattr(last_response, 'status_code', None)})"
    )


def clean_text(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    kept: List[str] = []
    boiler_markers = (
        "UU看書",
        "UU看书",
        "加入書籤",
        "投票推薦",
        "小說報錯",
        "目录",
        "目錄",
        "上一章",
        "下一章",
    )
    for line in lines:
        if not line:
            kept.append("")
            continue
        if any(marker in line for marker in boiler_markers):
            continue
        if len(line) < 2 and not CHINESE_RE.search(line):
            continue
        kept.append(line)

    result: List[str] = []
    blank_count = 0
    for line in kept:
        if line == "":
            blank_count += 1
            if blank_count <= 1:
                result.append("")
        else:
            blank_count = 0
            result.append(line)
    cleaned = "\n".join(result).strip()
    return cleaned + ("\n" if cleaned else "")


def extract_chapter(url, session, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title
            title_selectors = ['h1', '.chapter-title', '.bookname', 'title']
            title = ""
            for sel in title_selectors:
                tag = soup.select_one(sel)
                if tag:
                    title = tag.get_text(strip=True)
                    break
            if not title:
                title = "Chương không tiêu đề"
            
            # Try multiple selectors for content
            selectors = ['.readcotent', '.content', '#content', '.chapter-content']
            node = None
            for selector in selectors:
                node = soup.select_one(selector)
                if node:
                    break
            
            if not node:
                logger.warning(f"No content node found for {url}")
                return "", ""
            
            # Decompose unwanted tags
            for tag in node.find_all(['script', 'style', 'noscript', 'iframe']):
                tag.decompose()
            
            # Extract text directly
            raw = node.get_text(" ", strip=True)
            
            # Clean up extra spaces
            cleaned = re.sub(r'\s+', ' ', raw).strip()
            return title, cleaned
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
    return "", ""


def safe_name(value: str) -> str:
    cleaned = value.strip()
    cleaned = re.sub(r"[\\/*?:\"<>|]+", "_", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:160]


def slugify_title(value: str, fallback: str) -> str:
    import unicodedata

    cleaned = safe_name(value or fallback)
    cleaned = cleaned.lower().replace(" ", "-")
    normalized = unicodedata.normalize("NFKD", cleaned)
    ascii_only = "".join(ch for ch in normalized if ch.isalnum() or ch in {"-", "_"})
    ascii_only = re.sub(r"-+", "-", ascii_only).strip("-")
    return ascii_only or fallback


def _absolute_index_url(url: str) -> str:
    if url.endswith("/"):
        return url
    match = re.search(r"(https?://[^/]+/book/\d+)/", url)
    if match:
        return match.group(1) + "/"
    return url


def parse_book_metadata(soup: BeautifulSoup) -> Dict[str, Optional[str]]:
    def meta_property(name: str) -> Optional[str]:
        tag = soup.find("meta", {"property": name})
        if tag and tag.get("content"):
            return tag.get("content").strip()
        return None

    book_title = meta_property("og:novel:book_name")
    if not book_title:
        h1 = soup.select_one("h1, .booktitle, .book-info h1")
        if h1:
            book_title = h1.get_text(strip=True)
        else:
            book_title = "uukanshu_book"

    return {
        "title": book_title,
        "author": meta_property("og:novel:author"),
        "description": meta_property("og:description") or meta_property("description"),
        "cover_url": meta_property("og:image"),
        "status": meta_property("og:novel:status"),
        "latest_name": meta_property("og:novel:latest_chapter_name"),
        "latest_url": meta_property("og:novel:latest_chapter_url"),
    }


def scrape_book(session: requests.Session, index_url: str) -> BookData:
    soup = get_soup(session, index_url)
    meta = parse_book_metadata(soup)
    links = []
    for anchor in soup.select(INDEX_LINK_SELECTOR):
        href = anchor.get("href")
        if not href:
            continue
        full_url = urljoin(index_url, href)
        if "/book/" not in full_url or not full_url.endswith(".html"):
            continue
        title = anchor.get_text(strip=True) or ""
        links.append((title, full_url))

    seen: Dict[str, ChapterLink] = {}
    ordered: List[ChapterLink] = []
    for idx, (title, link_url) in enumerate(links, start=1):
        if link_url in seen:
            continue
        chapter_link = ChapterLink(index=idx, title=title or f"Chương {idx}", url=link_url)
        seen[link_url] = chapter_link
        ordered.append(chapter_link)

    if not ordered:
        raise RuntimeError("Không tìm thấy link chương. Có thể cấu trúc trang đã thay đổi.")

    return BookData(
        title=meta["title"],
        author=meta["author"],
        description=meta["description"],
        cover_url=meta["cover_url"],
        status=meta["status"],
        latest_chapter_name=meta["latest_name"],
        latest_chapter_url=meta["latest_url"],
        chapters=ordered,
    )


def ensure_directories(root_folder: str, slug: str) -> Tuple[str, str, str]:
    novel_root = os.path.join(root_folder, slug)
    goc = os.path.join(novel_root, "goc")
    dich = os.path.join(novel_root, "dich")
    os.makedirs(goc, exist_ok=True)
    os.makedirs(dich, exist_ok=True)
    return novel_root, goc, dich


def resolve_unique_slug(conn: sqlite3.Connection, base_slug: str, index_url: str) -> str:
    slug = base_slug
    suffix = 2
    while True:
        row = conn.execute(
            "SELECT index_url FROM novels WHERE slug = ?", (slug,)
        ).fetchone()
        if row is None or row["index_url"] == index_url:
            return slug
        slug = f"{base_slug}-{suffix}"
        suffix += 1


def make_chapter_filename(chapter_index: int) -> str:
    return f"chuong_{chapter_index:03d}.txt"


def write_chapter_file(path: str, title: str, body: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(title.strip() or "(Không tiêu đề)\n")
        handle.write("-" * 80 + "\n\n")
        handle.write(body)


def write_index_file(path: str, chapters: Sequence[ChapterLink]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("index\ttitle\turl\n")
        for chapter in chapters:
            handle.write(f"{chapter.index}\t{chapter.title}\t{chapter.url}\n")


def load_input_urls(path: str) -> List[str]:
    urls: List[str] = []
    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            urls.append(line)
    return urls


def summarise_new_chapters(downloaded: Dict[str, int]) -> str:
    if not downloaded:
        return "Không có chương mới."
    pairs = [f"{slug}: +{count}" for slug, count in sorted(downloaded.items())]
    return ", ".join(pairs)


def download_chapter(
    session: requests.Session,
    chapter: ChapterLink,
    goc_folder: str,
    min_length: int,
) -> Tuple[str, str, str]:
    title, body = extract_chapter(chapter.url, session)
    final_title = title or chapter.title
    if len(body.strip()) < min_length:
        raise RuntimeError(
            f"Chương '{final_title}' ({chapter.url}) có nội dung quá ngắn ({len(body.strip())} ký tự)."
        )
    filename = make_chapter_filename(chapter.index)
    output_path = os.path.join(goc_folder, filename)
    write_chapter_file(output_path, final_title, body)
    content_hash = hashlib.sha1(body.encode("utf-8")).hexdigest()
    return output_path, content_hash, final_title


def determine_new_chapters(
    existing_map: Dict[int, sqlite3.Row],
    chapters: Sequence[ChapterLink],
) -> Iterable[ChapterLink]:
    existing_urls = {
        row["source_url"]
        for row in existing_map.values()
        if isinstance(row, sqlite3.Row) and row["source_url"]
    }
    for chapter in chapters:
        existing_entry = existing_map.get(chapter.index)
        if existing_entry:
            stored_url = existing_entry["source_url"]
            file_path = existing_entry["file_path"]
            if (
                stored_url == chapter.url
                and file_path
                and os.path.exists(file_path)
                and os.path.getsize(file_path) > 0
            ):
                continue
        if chapter.url in existing_urls:
            match_rows = [row for row in existing_map.values() if row["source_url"] == chapter.url]
            if match_rows and all(
                row["file_path"]
                and os.path.exists(row["file_path"])
                and os.path.getsize(row["file_path"]) > 0
                for row in match_rows
            ):
                continue
        yield chapter


def sync_single_novel(
    session: requests.Session,
    conn,
    *,
    index_url: str,
    root_folder: str,
    min_length: int,
) -> Tuple[str, int]:
    resolved_index = _absolute_index_url(index_url)
    book = scrape_book(session, resolved_index)
    base_slug = slugify_title(book.title, fallback="truyen")
    slug = resolve_unique_slug(conn, base_slug, resolved_index)
    novel_root, goc_folder, _ = ensure_directories(root_folder, slug)

    novel_id = novel_db.upsert_novel(
        conn,
        title=book.title,
        slug=slug,
        index_url=resolved_index,
        root_path=novel_root,
        author=book.author,
        description=book.description,
        cover_url=book.cover_url,
    )

    existing_map = novel_db.fetch_chapter_map(conn, novel_id)
    downloaded = 0
    errors: List[str] = []

    for chapter in determine_new_chapters(existing_map, book.chapters):
        attempt_success = False
        for attempt in range(1, 4):
            try:
                path, content_hash, final_title = download_chapter(
                    session, chapter, goc_folder, min_length
                )
                novel_db.record_chapter(
                    conn,
                    novel_id=novel_id,
                    chapter_index=chapter.index,
                    title=final_title,
                    source_url=chapter.url,
                    file_path=path,
                    content_hash=content_hash,
                )
                downloaded += 1
                attempt_success = True
                print(f"[+] {book.title} - tải chương {chapter.index}: {chapter.title}")
                time.sleep(0.8 + random.random() * 0.8)
                break
            except Exception as exc:  # noqa: BLE001
                print(
                    f"    -> Lỗi khi tải chương {chapter.index} ({chapter.url}): {exc}."
                )
                time.sleep(1.5 * attempt)
        if not attempt_success:
            errors.append(chapter.url)

    write_index_file(os.path.join(goc_folder, "index.tsv"), book.chapters)

    last_scan_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    novel_db.update_novel_scan(
        conn,
        novel_id,
        last_scan_at=last_scan_at,
        latest_index=len(book.chapters),
        latest_chapter_title=book.latest_chapter_name,
        latest_chapter_url=book.latest_chapter_url,
    )

    if errors:
        print(f"[!] Hoàn thành với lỗi, các chương không tải được: {len(errors)}")

    return slug, downloaded


def sync_from_input(
    session: requests.Session,
    conn,
    *,
    urls: Sequence[str],
    root_folder: str,
    min_length: int,
) -> Dict[str, int]:
    results: Dict[str, int] = {}
    for url in urls:
        try:
            slug, count = sync_single_novel(
                session,
                conn,
                index_url=url,
                root_folder=root_folder,
                min_length=min_length,
            )
            results[slug] = results.get(slug, 0) + count
        except Exception as exc:  # noqa: BLE001
            print(f"[X] Không thể đồng bộ '{url}': {exc}")
    return results


def sync_registered_novels(
    session: requests.Session,
    conn,
    *,
    root_folder: str,
    min_length: int,
) -> Dict[str, int]:
    results: Dict[str, int] = {}
    for novel in novel_db.fetch_novels(conn):
        url = novel["index_url"]
        try:
            slug, count = sync_single_novel(
                session,
                conn,
                index_url=url,
                root_folder=root_folder,
                min_length=min_length,
            )
            results[slug] = results.get(slug, 0) + count
        except Exception as exc:  # noqa: BLE001
            print(f"[X] Không thể cập nhật '{novel['title']}': {exc}")
    return results


def run_auto_tool(root_folder: str) -> bool:
    auto_path = os.path.join(os.path.dirname(__file__), "auto.py")
    if not os.path.exists(auto_path):
        print("[!] Không tìm thấy auto.py để chạy dịch.")
        return False
    print("[•] Đang khởi chạy auto.py để dịch các chương mới...")
    try:
        subprocess.run(
            [sys.executable, auto_path, "--root", os.path.abspath(root_folder)],
            check=True,
        )
        return True
    except subprocess.CalledProcessError as exc:
        print(f"[X] auto.py trả về lỗi: {exc}")
        return False


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tool đồng bộ truyện từ uukanshu.cc về cấu trúc /truyen/<slug>/goc/."
    )
    parser.add_argument(
        "--input",
        help="Đường dẫn file chứa danh sách URL truyện (mỗi dòng một URL).",
    )
    parser.add_argument(
        "--root",
        default="truyen",
        help="Thư mục gốc lưu trữ truyện (mặc định: ./truyen).",
    )
    parser.add_argument(
        "--db",
        default=novel_db.DEFAULT_DB_FILE,
        help="Đường dẫn file SQLite lưu thông tin truyện (mặc định: novel_index.sqlite).",
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=MIN_TEXT_LENGTH,
        help="Số ký tự tối thiểu của nội dung chương để coi là hợp lệ (mặc định: 400).",
    )
    parser.add_argument(
        "--skip-registered",
        action="store_true",
        help="Chỉ xử lý các URL trong file input, không quét lại các truyện đã lưu trong DB",
    )
    parser.add_argument(
        "--run-auto",
        action="store_true",
        help="Tự động gọi auto.py sau khi phát hiện chương mới.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    root_folder = os.path.abspath(args.root)
    os.makedirs(root_folder, exist_ok=True)
    novel_db.ensure_database(args.db)

    session = make_session()

    with novel_db.connect(args.db) as conn:
        total_downloaded: Dict[str, int] = {}

        if args.input:
            input_urls = load_input_urls(args.input)
            if not input_urls:
                print("[!] File input không có URL hợp lệ.")
            else:
                print(f"[•] Đang xử lý {len(input_urls)} truyện từ danh sách input...")
                downloaded_from_input = sync_from_input(
                    session,
                    conn,
                    urls=input_urls,
                    root_folder=root_folder,
                    min_length=args.min_length,
                )
                for key, value in downloaded_from_input.items():
                    total_downloaded[key] = total_downloaded.get(key, 0) + value

        if not args.skip_registered:
            print("[•] Đang kiểm tra các truyện đã lưu trong database...")
            downloaded_registered = sync_registered_novels(
                session,
                conn,
                root_folder=root_folder,
                min_length=args.min_length,
            )
            for key, value in downloaded_registered.items():
                total_downloaded[key] = total_downloaded.get(key, 0) + value

        print("[✓] Hoàn tất đồng bộ." )
        print("    ->", summarise_new_chapters(total_downloaded))

        new_chapter_total = sum(total_downloaded.values())
        if new_chapter_total > 0 and args.run_auto:
            run_auto_tool(root_folder)


if __name__ == "__main__":
    main()
