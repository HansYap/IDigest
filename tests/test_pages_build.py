import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from news_engine import CATEGORIES, NewsEngine, utcnow
from scripts import build_pages


class PagesBuildTests(unittest.TestCase):
    def test_build_publishes_website_styles_and_each_category_illustration(self):
        with TemporaryDirectory() as temp_dir, patch.object(build_pages, "collect_edition", return_value={"stories": []}):
            output = Path(temp_dir)
            build_pages.build_pages(output)

            html = (output / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="/static/website.css"', html)
            self.assertIn('<body class="web-edition">', html)
            self.assertTrue((output / "static" / "website.css").is_file())
            for category in CATEGORIES:
                with self.subTest(category=category):
                    self.assertTrue((output / "static" / f"category-{category}.svg").is_file())
            self.assertEqual(
                {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()},
                build_pages.OUTPUT_FILES,
            )

    def test_public_edition_contains_headlines_without_publisher_text_or_internal_state(self):
        with TemporaryDirectory() as temp_dir:
            engine = NewsEngine(Path(temp_dir), build_pages.ROOT / "sources.json")
            state = engine.snapshot()

        now = utcnow()
        state["refresh"]["last_success_at"] = now
        state["settings"]["future_private_field"] = "secret setting"
        state["stories"] = [{
            "id": "article", "title": "A headline", "url": "https://example.com/article",
            "source_id": "ars", "source": "Ars Technica", "category": "tech",
            "published_at": "2026-01-01T00:00:00Z", "discovered_at": now, "related_sources": [],
            "normalized_url": "https://example.com/normalized", "excerpt": "Publisher text",
            "watch_matches": ["Match from excerpt"], "saved": True, "read": True,
        }]
        state["stories"].append({**state["stories"][0], "id": "undated", "published_at": now})
        state["digest_ids"] = ["article", "absent"]

        edition = build_pages.public_edition(state)
        self.assertEqual(len(edition["stories"]), 1)
        self.assertEqual(edition["stories"][0]["title"], "A headline")
        self.assertEqual(edition["stories"][0]["url"], "https://example.com/article")
        self.assertEqual(edition["digest_ids"], ["article"])
        for field in ("excerpt", "normalized_url", "saved", "read", "watch_matches"):
            self.assertNotIn(field, edition["stories"][0])
        self.assertNotIn("future_private_field", edition["settings"])

    def test_no_fresh_edition_leaves_previous_output_intact(self):
        with TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            previous = output / "edition.json"
            previous.write_text('{"stories": []}', encoding="utf-8")
            failed_state = {"stories": [], "refresh": {"last_success_at": None, "error": "No sources"}}

            with patch.object(build_pages, "collect_edition", side_effect=lambda: build_pages.public_edition(failed_state)):
                with self.assertRaisesRegex(RuntimeError, "No fresh edition"):
                    build_pages.build_pages(output)

            self.assertEqual(json.loads(previous.read_text(encoding="utf-8")), {"stories": []})

    def test_build_refuses_unexpected_files_in_publish_directory(self):
        with TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            private = output / "local.sqlite3"
            private.touch()

            with self.assertRaisesRegex(RuntimeError, "unexpected path"):
                build_pages.build_pages(output)

            self.assertTrue(private.is_file())
