# Morning Signal

A personal morning newspaper for gaming, technology, internet culture, science, animals, motorsport, and Malaysia.

**Free to run.** The Windows reader uses Python 3.10 or newer and an internet connection. It runs with Python's standard library and plain browser JavaScript. The website edition runs on Cloudflare Pages, as described below.

## Open it

Double-click **Start Morning Signal.cmd** in this folder. Your browser opens the reader. Reopening the launcher reuses the running app rather than starting another copy.

The small launcher window can close; the reader runs quietly in the background. To stop the reader, use **Settings → Stop app**. Closing the browser tab alone leaves collection running while your computer is awake.

Alternatively, open a terminal in this folder and run:

```text
python app.py --open
```

This keeps a terminal attached; press Ctrl+C there to stop it. The usual address is http://127.0.0.1:8765. If that port belongs to something else, Morning Signal chooses the next available port.

## Your daily routine

- **Today** is a short selection balanced across your interests.
- **All stories** shows the collected library across refreshes, including earlier days, with search and category filters. It has no hourly cutoff. Up to 600 recent unsaved stories are displayed, along with your bookmarks. Unsaved items expire after your chosen retention period (30 days by default), or sooner when the cache reaches its size limit.
- **Watchlist** highlights stories matching your watched phrases.
- **Saved** holds stories you bookmarked. Use the bookmark icon on any story to keep its headline, excerpt, and original link. Bookmarks do not expire. Removing a bookmark makes that story subject to the normal expiry rules again.
- Turn on **Unread only** in the filter bar to hide stories you've read in the current view. Turn it off to see those stories again.
- **Settings** lets you change watched phrases, mute words, choose sources, and set digest size, refresh frequency, and how long unsaved stories are kept (1, 3, 7, 14, or 30 days).
- **Refresh** collects the latest available stories. Source health shows which feeds worked and which need another try.

The refresh toolbar stays visible while you scroll. During collection, the button reads **Gathering…** until the update finishes.

Expiry uses each story's original publication date. Cleanup runs when the app starts, when you change the retention period, and after feed collection. It also hides expired stories from the browser's offline copy when you open or use it. No cleanup can run while your computer is off. Bookmarked stories are exempt from both age and cache size cleanup.

Cached stories appear without waiting for news collection. The reader refreshes stale content on startup, then periodically while it is running. It does not wake a sleeping computer. If your computer is off overnight, open the launcher in the morning and it catches up.

## What the digest means

Stories come from public publisher RSS and project Atom feeds. Headlines, publisher excerpts, original dates, source names, and links stay visible. The reader groups similar coverage and ranks it using freshness, watched phrases, and category diversity. It does not claim to verify reporting or turn a rumour into a confirmed fact. It does not generate AI summaries. No story is invented to fill an empty category.

The first feed collection usually takes a few to a few dozen seconds, depending on connection and source availability. Slow or broken feeds time out separately. If a refresh fails, previously collected stories stay available. Some publishers supply only short excerpts, and opening an original article may encounter the publisher's paywall.

Feeds and editorial coverage can change. See SOURCES.md for verified sources, attribution, and source maintenance. You can disable a noisy source in Settings; sources.json holds the source definitions.

## Your data

The **data** folder contains the local SQLite database, preferences, saved/read state, and rotating diagnostic logs. Your browser also caches the latest edition for faster opening and reading if the server disconnects. No account or telemetry is included. Feed requests go to the publishers; opening an article visits its original website. The app listens only on your own computer's loopback address.

Back up the entire data folder while the app is stopped to preserve your reader. Keep this project folder together when moving it. Git ignores the data folder so your bookmarks and settings stay local.

## Troubleshooting

- **The launcher reports Python is missing:** install Python 3.10 or newer from python.org and enable its PATH option. Python is free.
- **A feed fails:** check Sources, try Refresh later, or disable that source. Other feeds continue working.
- **No new stories:** check the internet connection and source status. Try All stories, clear search/filter selections, and review muted keywords.
- **The app cannot start:** read data/app.log. You can also run `python app.py --open` to see the error directly.
- **Another app uses the usual ports:** run `python app.py --open --port 8875`.
- **Want cached content only:** run `python app.py --open --no-refresh`.

## Development and resuming

[AGENTS.md](AGENTS.md) guides coding agents at the start and end of work. [PROGRESS.md](PROGRESS.md) records the current handoff, with older checkpoints in [docs/HISTORY.md](docs/HISTORY.md). The [development guide](docs/DEVELOPMENT.md) covers design decisions, verification, and commit-message drafts. The human reviews and makes every commit manually. Agents explain each completed change and observed human commit in plain language in chat.

Run the checks with:

```text
python -m unittest discover -s tests -v
```

The local reader has no installation or build command.

## Cloudflare Pages

The hosted edition collects feeds during each Cloudflare Pages build and publishes headlines, dates, sources, and links. Bookmarks, reading history, and preferences are stored in the browser you use to open the hosted site. The local reader uses its own database. **Reload edition** loads the most recently published edition.

The website digest opens with an illustrated lead story, a short list from the same edition, and more stories below. Each category uses the same original illustration across the website, including filtered and saved stories. The category name is always shown.

On the website, reading a story in **Today’s digest** adds a **Read** label and keeps the story in its place. **Unread only** hides read stories from the selected digest, so the list gets shorter as you read.

To move website bookmarks and preferences to another browser, open **Make it yours** and click **Export backup**. In the other browser, open the same panel, click **Import backup**, and choose the downloaded JSON file. Import adds the bookmarks to your existing saved list and restores the preferences from the file. Keep the backup somewhere private.

In **Workers & Pages → Create application → Continue to Pages**, choose **Import an existing Git repository**, select this repository, and use the following settings.

| Setting | Value |
| --- | --- |
| Production branch | `main` |
| Framework preset | None |
| Root directory | Repository root (leave blank) |
| Build command | `python scripts/build_pages.py` |
| Build output directory | `dist` |

The build needs Python 3.10 or newer, which is available on the current Pages build image. Only `dist` is published. The generated site requests that search engines skip indexing it. Anyone with the Pages URL can still open it.

For a daily edition, create a **Deploy Hook** for `main` in the Pages project's build settings, then save its URL in the GitHub repository under **Settings → Secrets and variables → Actions** as `PAGES_DEPLOY_HOOK`. The **Publish Morning Signal edition** workflow requests a build around 6:30 a.m. Malaysia time and can also be run manually from the **Actions** tab. Keep the hook URL in the secret field. A failed feed collection leaves the previous successful deployment live.

To preview a hosted build locally, run `python scripts/build_pages.py`, then `python -m http.server --bind 127.0.0.1 --directory dist 8875` and open `http://127.0.0.1:8875`.
