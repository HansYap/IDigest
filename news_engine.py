"""Free local news collection. Uses only the Python standard library.

NewsEngine is safe to call from a threaded HTTP server. Refreshes run in one
background worker; snapshot() always reads the last committed cache immediately.
"""

from __future__ import annotations

import concurrent.futures
from contextlib import contextmanager
import datetime as dt
import email.utils
from functools import lru_cache
import gzip
import hashlib
import html
from html.parser import HTMLParser
import io
import json
import math
import re
import sqlite3
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


UTC = dt.timezone.utc
MAX_FEED_BYTES = 3 * 1024 * 1024
FETCH_SECONDS = 7
REFRESH_SECONDS = 25
USER_AGENT = "MorningSignal/1.0 (personal local RSS reader)"
BRIEFING = json.loads((Path(__file__).resolve().parent / "static" / "briefing.json").read_text(encoding="utf-8"))
CATEGORIES = tuple(BRIEFING["categories"])
DEFAULT_SETTINGS = {
    "watchlist": BRIEFING["defaults"]["watchlist"],
    "muted_keywords": [],
    "digest_size": BRIEFING["defaults"]["digest_size"],
    "refresh_minutes": 60,
    "retention_days": 30,
}
TRACKING_PARAMS = {"fbclid", "gclid", "dclid", "mc_cid", "mc_eid", "ref_src", "ref_url"}
STOP_WORDS = {"the", "a", "an", "and", "or", "for", "of", "to", "in", "on", "with", "at", "is", "it", "this", "that", "from", "as", "by", "has", "have", "be", "new"}


def utcnow() -> str:
    return dt.datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def watch_matches(title: str, watchlist: list[str]) -> list[str]:
    """Match complete literal phrases, so a watch for AI does not match 'said'."""
    return [word for word in watchlist if word.strip() and re.search(
        r"(?<!\w)" + re.escape(word.strip()) + r"(?!\w)", title, re.IGNORECASE)]


def _story_time(value: str | None) -> dt.datetime | None:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except (AttributeError, TypeError, ValueError):
        return None


def briefing_score(story: dict, now: dt.datetime, watchlist: list[str]) -> float:
    policy = BRIEFING["digest"]
    published = _story_time(story.get("published_at"))
    age = max(0, (now - published).total_seconds() / 3600) if published else 168
    title = story.get("title", "")
    score = max(0, 100 - age * 1.8)
    if watch_matches(title, watchlist):
        score += policy["watch_bonus"]
    if story.get("category") in ("world", "business") and any(
        re.search(pattern, title, re.IGNORECASE | re.ASCII) for pattern in policy.get("region_patterns", [])
    ):
        score += policy.get("region_bonus", 0)
    return score


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.rsplit(":", 1)[-1]
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1
        if tag in {"p", "br", "div", "li"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        tag = tag.rsplit(":", 1)[-1]
        if tag in {"script", "style", "noscript"} and self.hidden:
            self.hidden -= 1
        if tag in {"p", "div", "li"}:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain_text(value: str | None, limit: int = 650) -> str:
    parser = _PlainText()
    try:
        parser.feed(value or "")
        text = " ".join("".join(parser.parts).split())
    except Exception:
        text = re.sub(r"<[^>]+>", " ", value or "")
    text = html.unescape(text)
    text = "".join(c for c in text if c.isprintable() or c.isspace())
    return text[:limit].rstrip() + ("…" if len(text) > limit else "")


def safe_url(value: str | None, base: str = "") -> str:
    try:
        value = urllib.parse.urljoin(base, (value or "").strip())
        parsed = urllib.parse.urlsplit(value)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
            return ""
        if any(ord(c) < 32 for c in value):
            return ""
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))
    except ValueError:
        return ""


def normalize_url(value: str) -> str:
    value = safe_url(value)
    if not value:
        return ""
    parsed = urllib.parse.urlsplit(value)
    query = [(key, val) for key, val in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
             if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMS]
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/") or "/"
    return urllib.parse.urlunsplit(("https", host, path, urllib.parse.urlencode(sorted(query)), ""))


def parse_date(value: str | None, fallback: str | None = None) -> str:
    if value:
        value = value.strip()
        try:
            parsed = email.utils.parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError, OverflowError):
            try:
                parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                parsed = None
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            try:
                parsed = parsed.astimezone(UTC)
                # Bad publisher timestamps should not pin a story to the top forever.
                if parsed <= dt.datetime.now(UTC) + dt.timedelta(hours=6):
                    return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")
            except (ValueError, OverflowError):
                pass
    return fallback or utcnow()


def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(node, names):
    for child in node:
        if _local_tag(child.tag) in names:
            return "".join(child.itertext()).strip()
    return ""


def _excerpt_text(item) -> str:
    # Media RSS descriptions describe an image, often with only a filename.
    # Select publisher article text by its full XML name, never local name alone.
    priorities = (
        "description",
        "{http://www.w3.org/2005/Atom}summary",
        "summary",
        "{http://purl.org/rss/1.0/}description",
        "{http://www.w3.org/2005/Atom}content",
        "{http://purl.org/rss/1.0/modules/content/}encoded",
        "content",
    )
    for tag in priorities:
        child = next((child for child in item if child.tag == tag), None)
        if child is not None:
            value = ET.tostring(child, encoding="unicode") if len(child) else (child.text or "")
            excerpt = plain_text(value)
            if excerpt:
                return excerpt
    return ""


def parse_feed(data: bytes, source: dict, fetched_at: str | None = None) -> list[dict]:
    """Parse RSS 2.0, RSS 1.0 and Atom without rendering publisher markup."""
    if len(data) > MAX_FEED_BYTES:
        raise ValueError("Feed exceeds the size limit")
    # ElementTree does not fetch external entities. Reject DTDs explicitly too.
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("Feeds containing DTDs or entities are not supported")
    root = ET.fromstring(data)
    if _local_tag(root.tag) not in {"rss", "rdf", "feed"}:
        raise ValueError("This URL did not return an RSS or Atom feed")
    fetched_at = fetched_at or utcnow()
    stories = []
    seen = set()
    for item in root.iter():
        if _local_tag(item.tag) not in {"item", "entry"}:
            continue
        tags = [(child.attrib.get("term") or child.text or "").strip().casefold()
                for child in item if _local_tag(child.tag) == "category"]
        if any(tag.startswith(prefix.casefold()) for tag in tags
               for prefix in source.get("exclude_feed_categories", []) if prefix):
            continue
        title = plain_text(_child_text(item, {"title"}), 300)
        if not title:
            continue
        link = ""
        for child in item:
            if _local_tag(child.tag) == "link":
                if child.attrib.get("rel", "alternate") == "alternate":
                    link = child.attrib.get("href") or (child.text or "")
                    if link:
                        break
        if not link:
            candidate = _child_text(item, {"guid", "id"})
            if candidate.startswith(("http://", "https://")):
                link = candidate
        url = safe_url(link, source["url"])
        if not url or not link:
            continue
        key = normalize_url(url)
        if key in seen:
            continue
        seen.add(key)
        published = _child_text(item, {"pubdate", "published", "date"})
        if not published:
            published = _child_text(item, {"updated"})
        story_id = hashlib.sha256((source["id"] + "\0" + key).encode()).hexdigest()[:24]
        stories.append({
            "id": story_id, "title": title, "url": url,
            "normalized_url": key, "source_id": source["id"],
            "source": source["name"], "category": source["category"],
            "excerpt": "" if source.get("headlines_only") else _excerpt_text(item),
            "published_at": parse_date(published, fetched_at),
            "discovered_at": fetched_at,
        })
        if len(stories) >= 100:
            break
    return stories


@lru_cache(maxsize=5000)
def _tokens(title: str) -> frozenset[str]:
    normalized = unicodedata.normalize("NFKC", title).casefold()
    return frozenset(word for word in re.findall(r"\w+", normalized) if word not in STOP_WORDS)


def similar_titles(left: str, right: str) -> bool:
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return False
    if a == b:
        return True
    # Short headlines often share subjects but report different developments.
    if min(len(a), len(b)) < 6:
        return False
    shared = len(a & b)
    if shared / (len(a) + len(b) - shared) < 0.86:
        return False
    if {w for w in a if any(c.isdigit() for c in w)} != {w for w in b if any(c.isdigit() for c in w)}:
        return False
    return True


class NewsEngine:
    def __init__(self, data_dir: Path, sources_path: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "news.sqlite3"
        self.sources_path = Path(sources_path)
        raw = json.loads(self.sources_path.read_text(encoding="utf-8-sig"))
        raw = raw.get("sources", []) if isinstance(raw, dict) else raw
        self.sources = []
        ids = set()
        for item in raw:
            source_id = str(item.get("id", ""))
            if not source_id or source_id in ids or item.get("category") not in CATEGORIES or not safe_url(item.get("url")):
                raise ValueError("Invalid or duplicate feed configuration")
            ids.add(source_id)
            self.sources.append({"id": source_id, "name": str(item["name"]),
                                 "url": safe_url(item["url"]), "category": item["category"],
                                 "website": safe_url(item.get("website", item["url"])),
                                 "headlines_only": item.get("headlines_only") is True,
                                 "exclude_feed_categories": [str(tag).strip() for tag in item.get("exclude_feed_categories", []) if str(tag).strip()]})
        self._lock = threading.RLock()
        self._refresh = {"running": False, "started_at": None, "finished_at": None,
                         "last_success_at": None, "error": None, "completed": 0, "total": 0}
        self._initialize()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _initialize(self):
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS stories (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL,
                    normalized_url TEXT NOT NULL, source_id TEXT NOT NULL,
                    source TEXT NOT NULL, category TEXT NOT NULL, excerpt TEXT NOT NULL,
                    published_at TEXT NOT NULL, discovered_at TEXT NOT NULL,
                    saved INTEGER NOT NULL DEFAULT 0, read INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS stories_published ON stories(published_at DESC);
                CREATE INDEX IF NOT EXISTS stories_saved_published ON stories(saved,published_at DESC);
                CREATE TABLE IF NOT EXISTS feed_state (
                    source_id TEXT PRIMARY KEY, etag TEXT, modified TEXT,
                    last_checked_at TEXT, last_success_at TEXT, last_error TEXT,
                    article_count INTEGER DEFAULT 0, status INTEGER
                );
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)
            row = conn.execute("SELECT value FROM metadata WHERE key='refresh'").fetchone()
            if row:
                try:
                    self._refresh.update(json.loads(row["value"]))
                except (TypeError, ValueError):
                    pass
            # A terminated process must never leave the next session "refreshing".
            self._refresh["running"] = False
            self._migrate_settings(conn)
            # Reclassify cached stories when a retained source moves sections.
            # Removed sources' bookmarks keep their original content and category.
            conn.executemany("UPDATE stories SET category=? WHERE source_id=?", [
                (source["category"], source["id"]) for source in self.sources
            ])
            self._cleanup(conn)

    def _migrate_settings(self, conn):
        row = conn.execute("SELECT value FROM metadata WHERE key='settings'").fetchone()
        try:
            previous = json.loads(row["value"]) if row else {}
            previous = previous if isinstance(previous, dict) else {}
        except (ValueError, TypeError):
            previous = {}
        row = conn.execute("SELECT value FROM metadata WHERE key='briefing_preferences'").fetchone()
        try:
            migration = json.loads(row["value"]) if row else {}
            migration = migration if isinstance(migration, dict) else {}
        except (ValueError, TypeError):
            migration = {}
        settings = {**DEFAULT_SETTINGS, **previous}
        if migration.get("version", 0) < BRIEFING["version"]:
            for key in ("watchlist", "digest_size"):
                if settings[key] == BRIEFING["legacy"][key]:
                    settings[key] = DEFAULT_SETTINGS[key]
        source_ids = [source["id"] for source in self.sources]
        if "enabled_sources" not in previous:
            settings["enabled_sources"] = source_ids
        else:
            # Old releases did not record the known source list. Its original
            # catalogue distinguishes newly introduced feeds from exclusions.
            legacy_ids = BRIEFING["legacy"]["source_ids"]
            fallback_known = legacy_ids if set(source_ids).intersection(legacy_ids) else source_ids
            known = set(migration.get("known_source_ids", fallback_known))
            enabled = set(previous["enabled_sources"])
            settings["enabled_sources"] = [source_id for source_id in source_ids
                if source_id in enabled or (enabled and source_id not in known)]
        conn.execute("INSERT OR REPLACE INTO metadata VALUES ('settings', ?)", (json.dumps(settings),))
        conn.execute("INSERT OR REPLACE INTO metadata VALUES ('briefing_preferences', ?)", (
            json.dumps({"version": BRIEFING["version"], "known_source_ids": source_ids}),
        ))

    def _settings(self, conn) -> dict:
        settings = {**DEFAULT_SETTINGS, "enabled_sources": [s["id"] for s in self.sources]}
        row = conn.execute("SELECT value FROM metadata WHERE key='settings'").fetchone()
        if row:
            try:
                settings.update(json.loads(row["value"]))
            except (ValueError, TypeError):
                pass
        return settings

    @staticmethod
    def _retention_cutoff(settings: dict) -> str:
        return (dt.datetime.now(UTC) - dt.timedelta(days=settings["retention_days"])).isoformat(timespec="seconds").replace("+00:00", "Z")

    def _cleanup(self, conn, settings: dict | None = None):
        """Prune unsaved articles only; bookmarks have no age or count limit."""
        settings = settings or self._settings(conn)
        conn.execute("DELETE FROM stories WHERE saved=0 AND published_at < ?", (self._retention_cutoff(settings),))
        conn.execute("""DELETE FROM stories WHERE saved=0 AND id NOT IN (
            SELECT id FROM stories WHERE saved=0 ORDER BY published_at DESC, id LIMIT 1000
        )""")

    def update_settings(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("Settings must be an object")
        with self._connect() as conn:
            settings = self._settings(conn)
            for key in ("watchlist", "muted_keywords"):
                if key in payload:
                    if not isinstance(payload[key], list) or any(not isinstance(x, str) for x in payload[key]):
                        raise ValueError(f"{key} must be a list of text values")
                    settings[key] = list(dict.fromkeys(x.strip()[:80] for x in payload[key][:50] if x.strip()))
            for key, lower, upper in (("digest_size", 5, 30), ("refresh_minutes", 15, 1440), ("retention_days", 1, 30)):
                if key in payload:
                    if type(payload[key]) is not int or not lower <= payload[key] <= upper:
                        raise ValueError(f"{key} must be between {lower} and {upper}")
                    settings[key] = payload[key]
            if "enabled_sources" in payload:
                allowed = {s["id"] for s in self.sources}
                if not isinstance(payload["enabled_sources"], list) or any(not isinstance(x, str) or x not in allowed for x in payload["enabled_sources"]):
                    raise ValueError("enabled_sources must contain valid source IDs")
                settings["enabled_sources"] = list(dict.fromkeys(payload["enabled_sources"]))
            conn.execute("INSERT OR REPLACE INTO metadata VALUES ('settings', ?)", (json.dumps(settings),))
            self._cleanup(conn, settings)
        return settings

    def _set_story_flag(self, story_id: str, key: str, value: bool) -> dict:
        if type(value) is not bool:
            raise ValueError(f"{key} must be true or false")
        with self._connect() as conn:
            story = conn.execute("SELECT * FROM stories WHERE id=?", (story_id,)).fetchone()
            if story is None:
                raise KeyError("Story not found")
            if key == "read":
                # Keep a grouped article read when a different publisher becomes
                # its representative after the next refresh.
                candidates = conn.execute("SELECT id,title,normalized_url,category FROM stories").fetchall()
                ids = [(int(value), item["id"]) for item in candidates
                       if item["normalized_url"] == story["normalized_url"] or
                       (item["category"] == story["category"] and similar_titles(item["title"], story["title"]))]
                conn.executemany("UPDATE stories SET read=? WHERE id=?", ids)
            else:
                conn.execute("UPDATE stories SET saved=? WHERE id=?", (int(value), story_id))
                if not value:
                    self._cleanup(conn)
        return {"id": story_id, key: value}

    def toggle_saved(self, story_id: str, saved: bool) -> dict:
        return self._set_story_flag(story_id, "saved", saved)

    def mark_read(self, story_id: str, read: bool) -> dict:
        return self._set_story_flag(story_id, "read", read)

    def snapshot(self) -> dict:
        with self._connect() as conn:
            settings = self._settings(conn)
            # Saved articles are fetched without a global limit. Fresh unsaved
            # cache remains available even with more than 1,000 bookmarks.
            rows = conn.execute("SELECT * FROM stories WHERE saved=1 ORDER BY published_at DESC").fetchall()
            rows += conn.execute("""SELECT * FROM stories WHERE saved=0 AND published_at >= ?
                ORDER BY published_at DESC LIMIT 1000""", (self._retention_cutoff(settings),)).fetchall()
            health = {row["source_id"]: dict(row) for row in conn.execute("SELECT * FROM feed_state")}
        enabled = set(settings["enabled_sources"])
        with self._lock:
            refresh = dict(self._refresh)
        # Fix the lineup to the published edition, including across read toggles.
        # Before the first refresh, cached discovery time is a stable fallback.
        now = _story_time(refresh.get("last_success_at")) or max(
            (_story_time(row["discovered_at"]) for row in rows if _story_time(row["discovered_at"])),
            default=dt.datetime.now(UTC),
        )
        stories, muted_count = [], 0
        for row in rows:
            item = dict(row)
            item["saved"], item["read"] = bool(item["saved"]), bool(item["read"])
            searchable = (item["title"] + " " + item["excerpt"]).casefold()
            item["muted"] = any(word.casefold() in searchable for word in settings["muted_keywords"])
            item["enabled"] = item["source_id"] in enabled
            if item["muted"]:
                muted_count += 1
            if not item["saved"] and (item["muted"] or not item["enabled"]):
                continue
            item["watch_matches"] = watch_matches(item["title"] + " " + item["excerpt"], settings["watchlist"])
            item["score"] = round(briefing_score(item, now, settings["watchlist"]), 2)
            item["related_sources"] = []
            stories.append(item)
        stories.sort(key=lambda x: (-x["score"], -(_story_time(x["published_at"]) or now).timestamp(), x["id"]))
        grouped = []
        for story in stories:
            if story["saved"]:
                grouped.append(story)
                continue
            match = next((other for other in grouped if story["normalized_url"] == other["normalized_url"]
                          or (story["category"] == other["category"] and similar_titles(story["title"], other["title"]))), None)
            # Saved entries remain individually accessible even if a duplicate is saved.
            if match is not None and not story["saved"]:
                related = {"source": story["source"], "source_id": story["source_id"], "url": story["url"]}
                if story["source_id"] != match["source_id"] and related not in match["related_sources"]:
                    match["related_sources"].append(related)
                continue
            grouped.append(story)
        # The visible unsaved feed is bounded separately from all bookmarks.
        saved = [s for s in grouped if s["saved"]]
        others = [s for s in grouped if not s["saved"]]
        grouped = sorted(saved + others[:600], key=lambda s: (s["score"], s["published_at"]), reverse=True)
        eligible = [s for s in grouped if s["enabled"] and not s["muted"]]
        digest = self._digest(eligible, settings["digest_size"], now, settings["watchlist"])
        source_info = []
        for source in self.sources:
            state = health.get(source["id"], {})
            source_info.append({**source, **{k: state.get(k) for k in ("last_checked_at", "last_success_at", "last_error", "status")},
                                "article_count": state.get("article_count", 0), "enabled": source["id"] in enabled})
        return {"stories": grouped, "digest_ids": [s["id"] for s in digest], "sources": source_info,
                "settings": settings, "briefing": BRIEFING, "refresh": refresh, "updated_at": utcnow(),
                "stats": {"story_count": len(grouped), "unread_count": sum(not s["read"] for s in grouped),
                          "saved_count": sum(s["saved"] for s in grouped), "muted_count": muted_count,
                          "healthy_sources": sum(bool(s["last_success_at"]) and not s["last_error"] for s in source_info),
                          "enabled_sources": len(enabled)}}

    @staticmethod
    def _digest(stories: list[dict], size: int, now: dt.datetime | None = None,
                watchlist: list[str] | None = None) -> list[dict]:
        """A finite, varied shortlist. Quiet sections never force stale filler."""
        now = now or dt.datetime.now(UTC)
        watchlist = DEFAULT_SETTINGS["watchlist"] if watchlist is None else watchlist
        policy = BRIEFING["digest"]
        # Keep the nine-story balance strict, while making larger saved limits
        # useful rather than permanently bounded by the default category total.
        scale = max(1, size / BRIEFING["defaults"]["digest_size"])
        category_caps = {category: math.ceil(cap * scale) for category, cap in policy["category_caps"].items()}
        source_cap = math.ceil(policy["source_cap"] * scale)
        cutoff = now - dt.timedelta(hours=policy["max_age_hours"])
        pool = []
        for story in stories:
            published = _story_time(story.get("published_at"))
            title = story.get("title", "")
            category = story.get("category")
            if category not in CATEGORIES or not published or not cutoff <= published <= now:
                continue
            if any(re.search(pattern, title, re.IGNORECASE | re.ASCII) for pattern in policy["exclude_patterns"]):
                continue
            if category == "local" and not any(
                re.search(pattern, title, re.IGNORECASE | re.ASCII) for pattern in policy["local_patterns"]
            ):
                continue
            pool.append(story)
        pool.sort(key=lambda story: (
            -briefing_score(story, now, watchlist),
            -_story_time(story["published_at"]).timestamp(), story["id"],
        ))
        selected, category_counts, source_counts = set(), {}, {}

        def fits(story):
            category = story["category"]
            source_id = story.get("source_id") or story.get("source") or story["id"]
            return (story["id"] not in selected
                    and category_counts.get(category, 0) < category_caps.get(category, 0)
                    and source_counts.get(source_id, 0) < source_cap)

        def select(story):
            selected.add(story["id"])
            category = story["category"]
            source_id = story.get("source_id") or story.get("source") or story["id"]
            category_counts[category] = category_counts.get(category, 0) + 1
            source_counts[source_id] = source_counts.get(source_id, 0) + 1

        for categories in policy["slot_categories"]:
            if len(selected) >= size:
                break
            candidate = next((story for story in pool if story["category"] in categories and fits(story)), None)
            if candidate is not None:
                select(candidate)
        for story in pool:
            if len(selected) >= size:
                break
            if fits(story):
                select(story)
        return [story for story in pool if story["id"] in selected]

    def start_refresh(self) -> dict:
        with self._lock:
            if not self._refresh["running"]:
                with self._connect() as conn:
                    settings = self._settings(conn)
                self._refresh.update(running=True, started_at=utcnow(), finished_at=None,
                                     error=None, completed=0, total=len(settings["enabled_sources"]))
                thread = threading.Thread(target=self._run_refresh, name="news-refresh", daemon=True)
                thread.start()
            return dict(self._refresh)

    def _fetch(self, source: dict, state: dict, refresh_deadline: float) -> dict:
        checked = utcnow()
        deadline = min(refresh_deadline, time.monotonic() + FETCH_SECONDS)
        result = {"source_id": source["id"], "last_checked_at": checked, "stories": [],
                  "etag": state.get("etag"), "modified": state.get("modified"),
                  "last_success_at": state.get("last_success_at"), "last_error": None,
                  "article_count": state.get("article_count", 0), "status": None}
        headers = {"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.1", "Accept-Encoding": "gzip"}
        if state.get("etag"):
            headers["If-None-Match"] = state["etag"]
        if state.get("modified"):
            headers["If-Modified-Since"] = state["modified"]
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Refresh time limit reached")
            request = urllib.request.Request(source["url"], headers=headers)
            with urllib.request.urlopen(request, timeout=max(0.25, remaining)) as response:
                result["status"] = response.status
                length = response.headers.get("Content-Length")
                if length and int(length) > MAX_FEED_BYTES:
                    raise ValueError("Feed exceeds the size limit")
                chunks, size = [], 0
                while True:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Source took too long to respond")
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_FEED_BYTES:
                        raise ValueError("Feed exceeds the size limit")
                    chunks.append(chunk)
                data = b"".join(chunks)
                if response.headers.get("Content-Encoding", "").lower() == "gzip":
                    with gzip.GzipFile(fileobj=io.BytesIO(data)) as compressed:
                        data = compressed.read(MAX_FEED_BYTES + 1)
                result["stories"] = parse_feed(data, source, checked)
                result["article_count"] = len(result["stories"])
                result["etag"] = response.headers.get("ETag")
                result["modified"] = response.headers.get("Last-Modified")
                result["last_success_at"] = checked
        except urllib.error.HTTPError as exc:
            result["status"] = exc.code
            if exc.code == 304:
                result["last_success_at"] = checked
            else:
                result["last_error"] = f"HTTP {exc.code}: source unavailable"
            exc.close()
        except (TimeoutError, OSError, ValueError, ET.ParseError) as exc:
            result["last_error"] = plain_text(str(exc), 180) or "Unable to read this feed"
        except Exception as exc:
            result["last_error"] = f"Unable to read feed ({type(exc).__name__})"
        return result

    def _store_result(self, result: dict):
        with self._connect() as conn:
            conn.execute("""INSERT OR REPLACE INTO feed_state
                (source_id,etag,modified,last_checked_at,last_success_at,last_error,article_count,status)
                VALUES (?,?,?,?,?,?,?,?)""", tuple(result.get(k) for k in ("source_id", "etag", "modified", "last_checked_at", "last_success_at", "last_error", "article_count", "status")))
            read_rows = conn.execute("SELECT normalized_url,title,category FROM stories WHERE read=1").fetchall()
            read_urls = {item["normalized_url"] for item in read_rows}
            read_titles = {}
            for item in read_rows:
                read_titles.setdefault(item["category"], []).append(item["title"])
            cutoff = self._retention_cutoff(self._settings(conn))
            existing = {item["id"]: item for item in conn.execute("SELECT id,saved,published_at FROM stories")}
            for story in result.get("stories", []):
                original = existing.get(story["id"])
                published_at = original["published_at"] if original is not None else story["published_at"]
                if published_at < cutoff and not (original is not None and original["saved"]):
                    continue
                inherited_read = story["normalized_url"] in read_urls or any(
                    similar_titles(story["title"], title) for title in read_titles.get(story["category"], [])
                )
                conn.execute("""INSERT INTO stories
                    (id,title,url,normalized_url,source_id,source,category,excerpt,published_at,discovered_at,read)
                    VALUES (:id,:title,:url,:normalized_url,:source_id,:source,:category,:excerpt,:published_at,:discovered_at,:read)
                    ON CONFLICT(id) DO UPDATE SET title=excluded.title, excerpt=excluded.excerpt,
                    url=excluded.url, source=excluded.source, category=excluded.category,
                    read=MAX(stories.read,excluded.read)""", {**story, "read": int(inherited_read)})

    def _run_refresh(self):
        executor = None
        success_count = 0
        try:
            with self._connect() as conn:
                settings = self._settings(conn)
                states = {row["source_id"]: dict(row) for row in conn.execute("SELECT * FROM feed_state")}
            enabled = set(settings["enabled_sources"])
            sources = [s for s in self.sources if s["id"] in enabled]
            deadline = time.monotonic() + REFRESH_SECONDS
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix="feed")
            pending = {executor.submit(self._fetch, source, states.get(source["id"], {}), deadline): source for source in sources}
            while pending and time.monotonic() < deadline:
                done, _ = concurrent.futures.wait(pending, timeout=min(0.5, max(0, deadline - time.monotonic())), return_when=concurrent.futures.FIRST_COMPLETED)
                for future in done:
                    pending.pop(future)
                    result = future.result()
                    self._store_result(result)
                    if not result["last_error"]:
                        success_count += 1
                    with self._lock:
                        self._refresh["completed"] += 1
            for future, source in pending.items():
                future.cancel()
                state = states.get(source["id"], {})
                self._store_result({**state, "source_id": source["id"], "last_checked_at": utcnow(),
                                    "last_error": "Refresh time limit reached; try again later", "stories": []})
                with self._lock:
                    self._refresh["completed"] += 1
            with self._connect() as conn:
                self._cleanup(conn)
            with self._lock:
                if success_count:
                    self._refresh["last_success_at"] = utcnow()
                elif sources:
                    self._refresh["error"] = "No sources could refresh. Cached stories are still available; check your connection or source health."
        except Exception as exc:
            with self._lock:
                self._refresh["error"] = f"Refresh failed: {plain_text(str(exc), 180)}"
        finally:
            if executor:
                executor.shutdown(wait=False, cancel_futures=True)
            with self._lock:
                refresh = {**self._refresh, "running": False, "finished_at": utcnow()}
                try:
                    with self._connect() as conn:
                        conn.execute("INSERT OR REPLACE INTO metadata VALUES ('refresh', ?)", (json.dumps(refresh),))
                except sqlite3.Error:
                    pass
                self._refresh.update(refresh)
