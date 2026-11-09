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

from news_engine import BRIEFING, DEFAULT_SETTINGS, NewsEngine, briefing_score, normalize_url, parse_date, parse_feed, plain_text, safe_url, similar_titles, utcnow, watch_matches


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

    def test_headlines_only_source_omits_publisher_excerpt(self):
        story = parse_feed(RSS, {**SOURCE, "headlines_only": True})[0]
        self.assertEqual(story["excerpt"], "")
        self.assertEqual(story["title"], "A & B discover a new browser breakthrough")
        self.assertEqual(story["url"], "https://example.org/story?utm_source=rss")

    def test_paid_feed_tags_are_excluded_without_banning_premium_car_titles(self):
        source = {**SOURCE, "exclude_feed_categories": ["premium"]}
        for category in (b"Premium", b"PREMIUM finance news"):
            paid = RSS.replace(b"<item>", b"<item><category>" + category + b"</category>")
            self.assertEqual(parse_feed(paid, source), [])
        free = RSS.replace(b"A &amp; B discover a new browser breakthrough", b"Engineering a premium car")
        self.assertEqual(parse_feed(free, source)[0]["title"], "Engineering a premium car")
        atom = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Paid story</title><category term="Premium analysis"/><link href="https://example.org/paid"/></entry></feed>'
        self.assertEqual(parse_feed(atom, source), [])

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

    def test_legacy_defaults_migrate_without_losing_exclusions_or_bookmarks(self):
        item = self.store()
        self.engine.toggle_saved(item["id"], True)
        self.engine.mark_read(item["id"], True)
        old_settings = {
            "watchlist": BRIEFING["legacy"]["watchlist"], "digest_size": 15,
            "enabled_sources": [source_id for source_id in BRIEFING["legacy"]["source_ids"] if source_id != "paultan"],
            "muted_keywords": ["spoiler"], "retention_days": 7, "refresh_minutes": 120,
        }
        with self.engine._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO metadata VALUES ('settings', ?)", (json.dumps(old_settings),))
            conn.execute("DELETE FROM metadata WHERE key='briefing_preferences'")
        sources = [{**SOURCE, "id": source_id, "category": category}
                   for source_id, category in (("ars", "tech"), ("paultan", "cars"), ("new-world", "world"))]
        self.config.write_text(json.dumps(sources), encoding="utf-8")
        restarted = NewsEngine(self.root / "data", self.config)
        state = restarted.snapshot()
        self.assertEqual(state["settings"]["digest_size"], 9)
        self.assertEqual(state["settings"]["watchlist"], DEFAULT_SETTINGS["watchlist"])
        self.assertEqual(state["settings"]["enabled_sources"], ["ars", "new-world"])
        self.assertEqual(state["settings"]["muted_keywords"], ["spoiler"])
        self.assertEqual(state["settings"]["retention_days"], 7)
        self.assertEqual(state["settings"]["refresh_minutes"], 120)
        self.assertEqual([story["id"] for story in state["stories"]], [item["id"]])
        self.assertTrue(state["stories"][0]["saved"])
        self.assertTrue(state["stories"][0]["read"])
        self.assertFalse(state["stories"][0]["enabled"])
        self.assertEqual(state["briefing"]["version"], BRIEFING["version"])

    def test_migration_preserves_custom_settings_and_explicit_empty_sources(self):
        self.engine.update_settings({"watchlist": ["wetlands"], "digest_size": 21, "enabled_sources": []})
        with self.engine._connect() as conn:
            conn.execute("DELETE FROM metadata WHERE key='briefing_preferences'")
        self.config.write_text(json.dumps([SOURCE, {**SOURCE, "id": "new-world", "category": "world"}]), encoding="utf-8")
        restarted = NewsEngine(self.root / "data", self.config)
        settings = restarted.snapshot()["settings"]
        self.assertEqual(settings["watchlist"], ["wetlands"])
        self.assertEqual(settings["digest_size"], 21)
        self.assertEqual(settings["enabled_sources"], [])

    def test_default_migration_runs_once_and_new_sources_keep_known_exclusions(self):
        self.engine.update_settings({
            "watchlist": BRIEFING["legacy"]["watchlist"], "digest_size": 15,
            "enabled_sources": ["test"],
        })
        sources = json.loads(self.config.read_text(encoding="utf-8"))
        sources.append({**SOURCE, "id": "new-world", "category": "world"})
        self.config.write_text(json.dumps(sources), encoding="utf-8")
        restarted = NewsEngine(self.root / "data", self.config)
        settings = restarted.snapshot()["settings"]
        self.assertEqual(settings["watchlist"], BRIEFING["legacy"]["watchlist"])
        self.assertEqual(settings["digest_size"], 15)
        self.assertEqual(settings["enabled_sources"], ["test", "new-world"])
        restarted.update_settings({"enabled_sources": ["test"]})
        again = NewsEngine(self.root / "data", self.config)
        self.assertEqual(again.snapshot()["settings"]["enabled_sources"], ["test"])

    def test_source_recategorization_keeps_saved_content(self):
        item = self.store()
        self.engine.toggle_saved(item["id"], True)
        self.config.write_text(json.dumps([{**SOURCE, "category": "cars"}]), encoding="utf-8")
        restarted = NewsEngine(self.root / "data", self.config)
        story = restarted.snapshot()["stories"][0]
        self.assertEqual(story["category"], "cars")
        self.assertEqual(story["title"], item["title"])
        self.assertEqual(story["url"], item["url"])
        self.assertTrue(story["saved"])

    def test_headlines_only_source_policy_reaches_the_feed_parser(self):
        self.config.write_text(json.dumps([{**SOURCE, "headlines_only": True}]), encoding="utf-8")
        engine = NewsEngine(self.root / "data", self.config)
        self.assertTrue(engine.sources[0]["headlines_only"])
        self.assertEqual(parse_feed(RSS, engine.sources[0])[0]["excerpt"], "")

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

    def test_digest_keeps_work_world_and_interests_in_a_finite_mix(self):
        now = dt.datetime.now(dt.timezone.utc)
        stories = [{"id": f"{category}-{index}", "source_id": f"source-{category}-{index}",
                    "title": f"A development in {category} number {index}", "category": category,
                    "published_at": now.isoformat()}
                   for category in ("business", "tech", "world", "science", "cars", "animals", "gaming")
                   for index in range(4)]
        digest = self.engine._digest(stories, 9, now, [])
        self.assertEqual(len(digest), 9)
        counts = {category: sum(story["category"] == category for story in digest) for category in BRIEFING["categories"]}
        self.assertEqual(counts, {"world": 2, "business": 2, "tech": 1, "science": 1,
                                  "cars": 1, "animals": 1, "gaming": 1, "local": 0})
        self.assertEqual(digest, self.engine._digest(list(reversed(stories)), 9, now, []))

    def test_digest_filters_quiet_day_filler_and_keeps_strict_caps(self):
        now = dt.datetime.now(dt.timezone.utc)
        def item(story_id, category="tech", title="Engineering development", age=0, source=None):
            return {"id": story_id, "source_id": source or story_id, "title": title, "category": category,
                    "published_at": (now - dt.timedelta(hours=age)).isoformat()}
        stories = [item("old", age=49), item("future", age=-1), item("invalid", "culture"),
                   item("promo", title="Best deals on graphics cards"), item("patch", "gaming", "Game patch notes"),
                   item("live", "world", "Live updates from the summit"),
                   item("chatter", "local", "Politician spotted at a restaurant"),
                   item("flood", "local", "Flood evacuations continue in Malaysia"),
                   item("budget", "local", "Malaysia budget changes income tax"),
                   item("science", "science", "New research result"),
                   item("tech1", source="same"), item("tech2", source="same"), item("tech3", source="same")]
        digest = self.engine._digest(stories, 9, now, [])
        self.assertEqual({story["id"] for story in digest}, {"budget", "science", "tech1", "tech2"})
        self.assertEqual(self.engine._digest([item("old", age=49)], 9, now), [])

    def test_larger_custom_digest_limit_scales_diversity_caps(self):
        now = dt.datetime.now(dt.timezone.utc)
        categories = ("world", "business", "tech", "science", "cars", "animals", "gaming")
        stories = [{"id": f"{category}-{index:02}", "source_id": f"{category}-publisher",
                    "category": category, "title": f"A useful {category} development {index}",
                    "published_at": now.isoformat()} for category in categories for index in range(12)]
        digest = self.engine._digest(stories, 24, now, [])
        self.assertEqual(len(digest), 24)
        self.assertEqual({story["category"] for story in digest}, set(categories))
        for category in categories:
            count = sum(story["category"] == category for story in digest)
            self.assertLessEqual(count, 3 if category in ("cars", "animals", "gaming") else 6)
        self.assertEqual(len(self.engine._digest(stories, 9, now, [])), 9)

    def test_watch_phrases_are_bounded_and_overlapping_matches_do_not_stack(self):
        self.assertEqual(watch_matches("The company said its trailer is ready", ["AI"]), [])
        self.assertEqual(watch_matches("AI inference improves on the 987.2 project", ["AI", "987.2"]), ["AI", "987.2"])
        self.assertEqual(watch_matches("The C++ runtime and caféAI system", ["C++", "AI"]), ["C++"])
        now = dt.datetime.now(dt.timezone.utc)
        story = {"id": "car", "title": "Porsche 944 engineering", "category": "cars", "published_at": now.isoformat()}
        self.assertEqual(briefing_score(story, now, ["Porsche", "Porsche 944"]), briefing_score(story, now, ["Porsche 944"]))
        self.assertEqual(briefing_score(story, now, ["Porsche 944"]) - briefing_score(story, now, []), 12)

    def test_read_changes_and_restart_preserve_digest_order(self):
        now = utcnow()
        rows = [{"id": f"stable-{index}", "title": title, "url": f"https://example.org/stable-{index}",
                 "normalized_url": f"https://example.org/stable-{index}", "source_id": "test", "source": "Test",
                 "category": "tech", "excerpt": "", "published_at": now, "discovered_at": now}
                for index, title in enumerate(("New battery architecture", "A processor design milestone", "Improved database reliability"))]
        self.engine._store_result({"source_id": "test", "stories": rows})
        with self.engine._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO metadata VALUES ('refresh', ?)", (json.dumps({"last_success_at": now}),))
        self.engine._refresh["last_success_at"] = now
        before = self.engine.snapshot()["digest_ids"]
        self.assertEqual(len(before), 2)
        self.engine.mark_read(before[0], True)
        self.assertEqual(self.engine.snapshot()["digest_ids"], before)
        restarted = NewsEngine(self.root / "data", self.config)
        self.assertEqual(restarted.snapshot()["digest_ids"], before)
        restarted.mark_read(before[0], False)
        self.assertEqual(restarted.snapshot()["digest_ids"], before)


if __name__ == "__main__":
    unittest.main()
