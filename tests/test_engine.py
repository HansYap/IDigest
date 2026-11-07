"""Core feed and cache behavior: python -m unittest discover -s tests -v."""
import datetime as dt
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.error

from news_engine import NewsEngine, normalize_url, parse_date, parse_feed, plain_text, safe_url, similar_titles, utcnow


SOURCE = {"id": "test", "name": "Test", "category": "tech", "url": "https://example.org/feed"}
RSS = b'''<?xml version="1.0"?><rss version="2.0"><channel><title>Test</title><item>
<title>A &amp; B discover a new browser breakthrough</title>
<link>https://example.org/story?utm_source=rss</link>
<description>&lt;p&gt;An interesting &lt;b&gt;result&lt;/b&gt;.&lt;/p&gt;&lt;script&gt;evil()&lt;/script&gt;</description>
<pubDate>Thu, 15 Oct 2026 05:00:00 GMT</pubDate></item></channel></rss>'''


class FeedParsingTests(unittest.TestCase):
    def test_rss_plain_text_and_safe_urls(self):
        stories = parse_feed(RSS, SOURCE)
        self.assertEqual(len(stories), 1)
        self.assertEqual(stories[0]["excerpt"], "An interesting result.")
        self.assertEqual(stories[0]["title"], "A & B discover a new browser breakthrough")
        self.assertNotIn("utm_source", stories[0]["normalized_url"])
        self.assertEqual(safe_url("javascript:alert(1)"), "")
        self.assertEqual(safe_url("https://user:pass@example.org/"), "")

    def test_atom_links_dates_and_xhtml(self):
        atom = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Emulation milestone</title>
        <link rel="self" href="https://example.org/api/1"/><link rel="alternate" href="/posts/1"/>
        <published>2025-01-02T03:04:05Z</published><summary type="xhtml"><div xmlns="http://www.w3.org/1999/xhtml"><p>Works &amp; plays.</p><script>hidden</script></div></summary>
        </entry></feed>'''
        item = parse_feed(atom, SOURCE)[0]
        self.assertEqual(item["url"], "https://example.org/posts/1")
        self.assertEqual(item["published_at"], "2025-01-02T03:04:05Z")
        self.assertEqual(item["excerpt"], "Works & plays.")

    def test_media_description_does_not_replace_article_excerpt(self):
        rss = b'''<rss xmlns:media="http://search.yahoo.com/mrss/"><channel><item>
        <title>Research update</title><link>https://example.org/update</link>
        <media:description>Hero Image 261015</media:description>
        <description>&lt;p&gt;The actual publisher excerpt.&lt;/p&gt;</description>
        </item></channel></rss>'''
        self.assertEqual(parse_feed(rss, SOURCE)[0]["excerpt"], "The actual publisher excerpt.")
        self.assertEqual(parse_feed(rss.replace(b"<description>&lt;p&gt;The actual publisher excerpt.&lt;/p&gt;</description>", b""), SOURCE)[0]["excerpt"], "")

    def test_rejects_html_entity_declarations_and_unsafe_articles(self):
        with self.assertRaises(ValueError):
            parse_feed(b"<!DOCTYPE rss><rss/>", SOURCE)
        with self.assertRaises(ValueError):
            parse_feed(b"<html><body>Login required</body></html>", SOURCE)
        self.assertEqual(parse_feed(b"<rss><channel><item><title>No</title><link>javascript:alert(1)</link></item></channel></rss>", SOURCE), [])

    def test_conservative_duplicate_detection(self):
        self.assertTrue(similar_titles("Sony announces a new PlayStation emulation breakthrough", "Sony announces new PlayStation emulation breakthrough"))
        self.assertFalse(similar_titles("PlayStation 5 firmware 12 released today", "PlayStation 5 firmware 13 released today"))
        self.assertFalse(similar_titles("Bloodborne PC port released", "Bloodborne PC port delayed"))
        self.assertEqual(normalize_url("http://www.example.org/story/?utm_campaign=x&x=1#part"), "https://example.org/story?x=1")

    def test_date_fallback_and_text_limit(self):
        self.assertEqual(parse_date("invalid", "2026-01-01T00:00:00Z"), "2026-01-01T00:00:00Z")
        self.assertEqual(parse_date("2099-01-01T00:00:00Z", "2026-01-01T00:00:00Z"), "2026-01-01T00:00:00Z")
        self.assertEqual(plain_text("abcdef", 3), "abc…")


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        sources = [SOURCE, {**SOURCE, "id": "second", "name": "Second", "category": "animals"}]
        self.config = self.root / "sources.json"
        self.config.write_text(json.dumps(sources), encoding="utf-8")
        self.engine = NewsEngine(self.root / "data", self.config)

    def tearDown(self):
        self.temp.cleanup()

    def store(self, source=SOURCE, rss=RSS):
        result = {"source_id": source["id"], "stories": parse_feed(rss, source),
                  "last_checked_at": utcnow(), "last_success_at": utcnow(), "last_error": None,
                  "article_count": 1, "status": 200}
        self.engine._store_result(result)
        return result["stories"][0]

    def test_bookmarks_settings_and_read_survive_restart(self):
        item = self.store()
        self.engine.toggle_saved(item["id"], True)
        self.engine.mark_read(item["id"], True)
        self.engine.update_settings({"watchlist": ["browser"], "muted_keywords": [], "digest_size": 10})
        restarted = NewsEngine(self.root / "data", self.config)
        snapshot = restarted.snapshot()
        self.assertTrue(snapshot["stories"][0]["saved"])
        self.assertTrue(snapshot["stories"][0]["read"])
        self.assertEqual(snapshot["stories"][0]["watch_matches"], ["browser"])
        self.assertEqual(snapshot["settings"]["digest_size"], 10)

    def test_duplicate_grouping_and_read_propagation(self):
        item = self.store()
        other_source = {**SOURCE, "id": "second", "name": "Second"}
        self.store(other_source)
        snapshot = self.engine.snapshot()
        self.assertEqual(len(snapshot["stories"]), 1)
        self.assertEqual(len(snapshot["stories"][0]["related_sources"]), 1)
        self.engine.mark_read(item["id"], True)
        self.assertTrue(all(s["read"] for s in self.engine.snapshot()["stories"]))

    def test_mute_and_disable_preserve_saved_entries(self):
        item = self.store()
        self.engine.update_settings({"muted_keywords": ["browser"]})
        self.assertEqual(self.engine.snapshot()["stories"], [])
        self.engine.toggle_saved(item["id"], True)
        self.engine.update_settings({"enabled_sources": []})
        snapshot = self.engine.snapshot()
        self.assertEqual(len(snapshot["stories"]), 1)
        self.assertEqual(snapshot["digest_ids"], [])

    def test_newly_arriving_duplicate_inherits_read_state(self):
        item = self.store()
        self.engine.mark_read(item["id"], True)
        later_source = {**SOURCE, "id": "second", "name": "Second"}
        later_rss = RSS.replace(b"https://example.org/story?utm_source=rss", b"https://second.example.org/report")
        self.store(later_source, later_rss)
        snapshot = self.engine.snapshot()
        self.assertEqual(len(snapshot["stories"]), 1)
        self.assertTrue(snapshot["stories"][0]["read"])
        self.assertEqual(len(snapshot["stories"][0]["related_sources"]), 1)

    def test_nightly_builds_stay_out_of_digest(self):
        rss = RSS.replace(b"A &amp; B discover a new browser breakthrough", b"Pre-release-shadPS4-2026-10-15")
        item = self.store(rss=rss)
        snapshot = self.engine.snapshot()
        self.assertEqual(snapshot["stories"][0]["id"], item["id"])
        self.assertEqual(snapshot["digest_ids"], [])

    def test_settings_validation(self):
        for payload in ({"digest_size": True}, {"refresh_minutes": 1}, {"watchlist": "one"}, {"enabled_sources": ["missing"]},
                        {"retention_days": True}, {"retention_days": 0}, {"retention_days": 31},
                        {"retention_days": 7.0}, {"retention_days": "7"}):
            with self.assertRaises(ValueError):
                self.engine.update_settings(payload)

    def age_stories(self, days):
        published = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).isoformat(timespec="seconds").replace("+00:00", "Z")
        with self.engine._connect() as conn:
            conn.execute("UPDATE stories SET published_at=?", (published,))
        return published

    def test_startup_expires_unsaved_and_preserves_equally_old_bookmark(self):
        saved = self.store()
        self.engine.toggle_saved(saved["id"], True)
        unsaved = self.store({**SOURCE, "id": "second", "name": "Second"}, RSS.replace(b"example.org/story", b"second.example.org/story"))
        self.age_stories(31)
        restarted = NewsEngine(self.root / "data", self.config)
        snapshot = restarted.snapshot()
        self.assertEqual([item["id"] for item in snapshot["stories"]], [saved["id"]])
        self.assertTrue(snapshot["stories"][0]["saved"])
        with restarted._connect() as conn:
            self.assertIsNone(conn.execute("SELECT id FROM stories WHERE id=?", (unsaved["id"],)).fetchone())

    def test_snapshot_hides_expired_cache_without_a_write(self):
        self.store()
        self.age_stories(31)
        self.assertEqual(self.engine.snapshot()["stories"], [])
        with self.engine._connect() as conn:
            # Snapshot is read-only; scheduled cleanup removes the hidden row.
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM stories").fetchone()[0], 1)

    def test_shorter_retention_persists_and_unbookmark_expires_immediately(self):
        saved = self.store()
        self.engine.toggle_saved(saved["id"], True)
        self.store({**SOURCE, "id": "second", "name": "Second"}, RSS.replace(b"example.org/story", b"second.example.org/story"))
        self.age_stories(5)
        self.engine.update_settings({"retention_days": 3})
        restarted = NewsEngine(self.root / "data", self.config)
        self.assertEqual(restarted.snapshot()["settings"]["retention_days"], 3)
        self.assertEqual(len(restarted.snapshot()["stories"]), 1)
        restarted.toggle_saved(saved["id"], False)
        self.assertEqual(restarted.snapshot()["stories"], [])
        with restarted._connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM stories").fetchone()[0], 0)

    def test_feed_skips_expired_items_but_updates_old_bookmarks(self):
        item = self.store()
        self.engine.toggle_saved(item["id"], True)
        published = self.age_stories(31)
        updated = parse_feed(RSS, SOURCE)[0]
        updated.update(excerpt="Updated publisher excerpt.", published_at=published)
        expired_new = {**updated, "id": "expired-new", "url": "https://example.org/expired", "normalized_url": "https://example.org/expired"}
        self.engine._store_result({"source_id": SOURCE["id"], "stories": [updated, expired_new]})
        snapshot = self.engine.snapshot()
        self.assertEqual(len(snapshot["stories"]), 1)
        self.assertEqual(snapshot["stories"][0]["excerpt"], "Updated publisher excerpt.")
        self.assertTrue(snapshot["stories"][0]["saved"])
        self.assertEqual(snapshot["stories"][0]["published_at"], published)
        with self.engine._connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM stories").fetchone()[0], 1)

    def test_original_publication_date_cannot_be_renewed_by_refetch(self):
        item = self.store()
        old_date = self.age_stories(31)
        updated = parse_feed(RSS, SOURCE)[0]
        updated["published_at"] = utcnow()
        self.engine._store_result({"source_id": SOURCE["id"], "stories": [updated]})
        self.assertEqual(self.engine.snapshot()["stories"], [])
        with self.engine._connect() as conn:
            self.assertEqual(conn.execute("SELECT published_at FROM stories WHERE id=?", (item["id"],)).fetchone()[0], old_date)

    def test_cache_cap_keeps_every_bookmark_and_fresh_unsaved_feed(self):
        now = utcnow()
        old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=31)).isoformat(timespec="seconds").replace("+00:00", "Z")
        rows = []
        for index in range(2006):
            saved = index < 1001
            rows.append({"id": str(index), "title": f"Cached research report entry {index}",
                         "url": f"https://example.org/{index}", "normalized_url": f"https://example.org/{index}",
                         "source_id": "test", "source": "Test", "category": "tech", "excerpt": "Publisher excerpt.",
                         "published_at": old if saved else now, "discovered_at": now, "saved": int(saved)})
        with self.engine._connect() as conn:
            conn.executemany("""INSERT INTO stories
                (id,title,url,normalized_url,source_id,source,category,excerpt,published_at,discovered_at,saved)
                VALUES (:id,:title,:url,:normalized_url,:source_id,:source,:category,:excerpt,:published_at,:discovered_at,:saved)""", rows)
        self.engine.update_settings({})
        restarted = NewsEngine(self.root / "data", self.config)
        snapshot = restarted.snapshot()
        self.assertEqual(sum(item["saved"] for item in snapshot["stories"]), 1001)
        self.assertEqual(sum(not item["saved"] for item in snapshot["stories"]), 600)
        with restarted._connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM stories WHERE saved=1").fetchone()[0], 1001)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM stories WHERE saved=0").fetchone()[0], 1000)

    def test_refresh_nonblocking_single_worker_and_failures_keep_cache(self):
        self.store()
        gate = threading.Event()
        calls = []

        def fetch(source, state, deadline):
            calls.append(source["id"])
            gate.wait(1)
            return {"source_id": source["id"], "last_checked_at": utcnow(), "last_error": "Offline", "stories": []}

        with patch.object(self.engine, "_fetch", side_effect=fetch):
            started = time.monotonic()
            state = self.engine.start_refresh()
            self.assertTrue(state["running"])
            self.engine.start_refresh()
            self.assertLess(time.monotonic() - started, 0.5)
            self.assertEqual(len(self.engine.snapshot()["stories"]), 1)
            gate.set()
            until = time.monotonic() + 3
            while self.engine.snapshot()["refresh"]["running"] and time.monotonic() < until:
                time.sleep(0.01)
        snapshot = self.engine.snapshot()
        self.assertEqual(sorted(calls), ["second", "test"])
        self.assertEqual(len(snapshot["stories"]), 1)
        self.assertFalse(snapshot["refresh"]["running"])
        self.assertIn("No sources", snapshot["refresh"]["error"])

    def test_conditional_get_304_is_healthy(self):
        state = {"etag": '"original"', "modified": "Thu, 15 Oct 2026 05:00:00 GMT", "article_count": 5}
        response = urllib.error.HTTPError(SOURCE["url"], 304, "Not Modified", {}, None)
        with patch("urllib.request.urlopen", side_effect=response) as request:
            result = self.engine._fetch(SOURCE, state, time.monotonic() + 20)
        self.assertEqual(request.call_args.args[0].get_header("If-none-match"), '"original"')
        self.assertIsNone(result["last_error"])
        self.assertEqual(result["status"], 304)
        self.assertEqual(result["article_count"], 5)
        self.assertEqual(result["stories"], [])

    def test_digest_has_category_coverage_and_size(self):
        def item(index, category, score):
            return {"id": str(index), "category": category, "score": score, "published_at": utcnow()}
        stories = [item(i, "tech", 100-i) for i in range(20)] + [item(100, "animals", 10), item(101, "gaming", 9)]
        digest = self.engine._digest(stories, 5)
        self.assertEqual(len(digest), 5)
        self.assertEqual({s["category"] for s in digest}, {"tech", "animals", "gaming"})


if __name__ == "__main__":
    unittest.main()
