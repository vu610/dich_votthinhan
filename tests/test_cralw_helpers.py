import novel_db
import cralw


def test_slugify_title_basic():
	slug = cralw.slugify_title("Vớt thi nhân", fallback="truyen")
	assert slug.startswith("vot-thi-nhan")


def test_resolve_unique_slug(tmp_path):
	db_path = tmp_path / "db.sqlite"
	with novel_db.connect(str(db_path)) as conn:
		base_slug = cralw.slugify_title("Truyện A", fallback="truyen")
		slug1 = cralw.resolve_unique_slug(conn, base_slug, "https://example.com/book/1/")
		assert slug1 == base_slug
		novel_db.upsert_novel(
			conn,
			title="Truyện A",
			slug=slug1,
			index_url="https://example.com/book/1/",
			root_path="/tmp/truyen-a",
		)
		slug2 = cralw.resolve_unique_slug(conn, base_slug, "https://example.com/book/2/")
		assert slug2 != slug1
		novel_db.upsert_novel(
			conn,
			title="Truyện B",
			slug=slug2,
			index_url="https://example.com/book/2/",
			root_path="/tmp/truyen-b",
		)
		assert slug2.endswith("-2")


def test_determine_new_chapters_skip_existing(tmp_path):
	db_path = tmp_path / "db.sqlite"
	goc = tmp_path / "truyen" / "slug" / "goc"
	goc.mkdir(parents=True)
	existing_file = goc / "chuong_001.txt"
	existing_file.write_text("Nội dung cũ", encoding="utf-8")

	with novel_db.connect(str(db_path)) as conn:
		novel_id = novel_db.upsert_novel(
			conn,
			title="Test",
			slug="test",
			index_url="https://example.com/book/1/",
			root_path=str(tmp_path / "truyen" / "slug"),
		)
		novel_db.record_chapter(
			conn,
			novel_id=novel_id,
			chapter_index=1,
			title="Chương 1",
			source_url="https://example.com/book/1/1.html",
			file_path=str(existing_file),
			content_hash="hash",
		)
		existing_map = novel_db.fetch_chapter_map(conn, novel_id)

	chapters = [
		cralw.ChapterLink(index=1, title="Chương 1", url="https://example.com/book/1/1.html"),
		cralw.ChapterLink(index=2, title="Chương 2", url="https://example.com/book/1/2.html"),
	]
	new = list(cralw.determine_new_chapters(existing_map, chapters))
	assert len(new) == 1 and new[0].index == 2


def test_determine_new_chapters_when_file_missing(tmp_path):
	db_path = tmp_path / "db.sqlite"
	missing_path = tmp_path / "missing.txt"

	with novel_db.connect(str(db_path)) as conn:
		novel_id = novel_db.upsert_novel(
			conn,
			title="Test",
			slug="test",
			index_url="https://example.com/book/1/",
			root_path=str(tmp_path / "truyen" / "slug"),
		)
		novel_db.record_chapter(
			conn,
			novel_id=novel_id,
			chapter_index=1,
			title="Chương 1",
			source_url="https://example.com/book/1/1.html",
			file_path=str(missing_path),
			content_hash="hash",
		)
		existing_map = novel_db.fetch_chapter_map(conn, novel_id)

	chapters = [cralw.ChapterLink(index=1, title="Chương 1", url="https://example.com/book/1/1.html")]
	new = list(cralw.determine_new_chapters(existing_map, chapters))
	assert len(new) == 1 and new[0].index == 1


def test_load_input_urls(tmp_path):
	input_file = tmp_path / "input.txt"
	input_file.write_text(
		"\n".join(
			[
				"# comment",
				"https://example.com/book/1/",
				"   ",
				"https://example.com/book/2/",
			]
		),
		encoding="utf-8",
	)
	urls = cralw.load_input_urls(str(input_file))
	assert urls == [
		"https://example.com/book/1/",
		"https://example.com/book/2/",
	]
