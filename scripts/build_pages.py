"""Build a headlines-only edition for Cloudflare Pages."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import sys
from tempfile import TemporaryDirectory
import time

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from news_engine import CATEGORIES, NewsEngine, REFRESH_SECONDS


WEBSITE_ICON = "favicon-sunrise.svg"
ASSETS = {
    "app.js": "static/app.js",
    "briefing.js": "static/briefing.js",
    "styles.css": "static/styles.css",
    "favicon.svg": "favicon.svg",
    "website-icon.svg": WEBSITE_ICON,
    "hosted.js": "hosted.js",
    "website.css": "static/website.css",
    **{f"illustrations/{category}.svg": f"static/category-{category}.svg" for category in (*CATEGORIES, "culture", "motorsport")},
}
OUTPUT_FILES = {"index.html", "edition.json", "_headers", *ASSETS.values()}
APP_SCRIPT = '<script defer src="/static/app.js"></script>'
STORY_FIELDS = ("id", "title", "url", "source_id", "source", "category", "published_at", "discovered_at")
SOURCE_FIELDS = ("id", "name", "url", "category", "last_checked_at", "last_success_at", "status", "article_count")
SETTINGS_FIELDS = ("watchlist", "muted_keywords", "enabled_sources", "digest_size", "refresh_minutes", "retention_days")
HEADERS = """/*
  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'
  Referrer-Policy: no-referrer
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  X-Robots-Tag: noindex
/edition.json
  Cache-Control: no-cache
"""


def collect_edition() -> dict:
    with TemporaryDirectory(prefix="morning-signal-pages-") as cache:
        engine = NewsEngine(Path(cache), ROOT / "sources.json")
        engine.start_refresh()
        deadline = time.monotonic() + REFRESH_SECONDS + 10
        while time.monotonic() < deadline:
            state = engine.snapshot()
            if not state["refresh"]["running"]:
                return public_edition(state)
            time.sleep(0.5)
    raise RuntimeError("Feed collection did not finish before the build deadline.")


def public_edition(state: dict) -> dict:
    refresh = state["refresh"]
    if not refresh["last_success_at"] or refresh["error"] or not state["stories"]:
        raise RuntimeError("No fresh edition could be built from the configured feeds.")

    stories = []
    for story in state["stories"][:600]:
        # The local parser uses discovery time when a feed has no valid date.
        # Fresh hosted builds would make those stories look newly published every day.
        if story["published_at"] == story["discovered_at"]:
            continue
        public_story = {key: story[key] for key in STORY_FIELDS}
        public_story["related_sources"] = [
            {key: source[key] for key in ("source_id", "source", "url")}
            for source in story["related_sources"][:3]
        ]
        stories.append(public_story)
    if not stories:
        raise RuntimeError("No stories with publication dates could be built into the edition.")

    sources = []
    for source in state["sources"]:
        public_source = {key: source[key] for key in SOURCE_FIELDS}
        public_source["last_error"] = "Could not check this feed." if source["last_error"] else None
        sources.append(public_source)

    story_ids = {story["id"] for story in stories}
    return {
        "stories": stories,
        "digest_ids": [story_id for story_id in state["digest_ids"] if story_id in story_ids],
        "sources": sources,
        "settings": {key: state["settings"][key] for key in SETTINGS_FIELDS},
        "refresh": {key: refresh[key] for key in ("running", "started_at", "finished_at", "last_success_at", "completed", "total")},
        "updated_at": state["updated_at"],
        "briefing": state["briefing"],
    }


def check_output_directory(output: Path) -> None:
    # Pages publishes every file in the output directory. Refuse unexpected files.
    if output.is_symlink() or (output.exists() and not output.is_dir()):
        raise RuntimeError(f"Choose a real directory for the Pages build: {output}")
    for path in output.rglob("*"):
        relative = path.relative_to(output).as_posix()
        expected = path.is_dir() if relative == "static" else relative in OUTPUT_FILES and path.is_file()
        if not expected or path.is_symlink():
            raise RuntimeError(f"Remove the unexpected path before building Pages: {path}")


def build_pages(output: Path) -> int:
    check_output_directory(output)
    static = ROOT / "static"
    html = (static / "index.html").read_text(encoding="utf-8")
    html, icons_replaced = re.subn(
        r'<link rel="icon"[^>]*>',
        f'<link rel="icon" type="image/svg+xml" href="/{WEBSITE_ICON}">',
        html,
    )
    if icons_replaced != 1:
        raise RuntimeError("Expected one browser-tab icon in the HTML template.")
    if html.count(APP_SCRIPT) != 1:
        raise RuntimeError("Could not find the app script in the HTML template.")
    html = html.replace(
        APP_SCRIPT,
        '<link rel="stylesheet" href="/static/website.css">\n  '
        '<script defer src="/hosted.js"></script>\n  ' + APP_SCRIPT,
    )
    html = html.replace("<body>", '<body class="web-edition">', 1)
    html = html.replace('content="#f5f2eb"', 'content="#f8f6f0"', 1)
    html = html.replace(
        "Your free, private morning digest. Interesting stories from around the internet, gathered on your computer.",
        "Your free morning digest. Find interesting stories and save them in this browser.",
    )
    edition = collect_edition()

    (output / "static").mkdir(parents=True, exist_ok=True)
    for asset, target in ASSETS.items():
        shutil.copyfile(static / asset, output / target)
    (output / "index.html").write_text(html, encoding="utf-8")
    (output / "_headers").write_text(HEADERS, encoding="utf-8")
    (output / "edition.json").write_text(json.dumps(edition, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(edition["stories"])


if __name__ == "__main__":
    try:
        count = build_pages(ROOT / "dist")
    except (RuntimeError, OSError) as error:
        raise SystemExit(f"Pages build failed: {error}") from error
    print(f"Built the Pages edition with {count} stories in dist/.")
