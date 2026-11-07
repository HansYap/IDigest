# Morning Signal

A personal morning newspaper for gaming, technology, internet culture, science, animals, motorsport, and Malaysia.

**Free to run.** No API keys, paid services, cloud hosting, JavaScript build step, or third-party Python packages. Python 3.10 or newer and an internet connection are all you need.

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

PROGRESS.md records what was finished, what was checked, and anything still outstanding. Read it before continuing development after an interruption. Code is stored in this folder; stopping the chat does not delete it.

Run the checks with:

```text
python -m unittest discover -s tests -v
```

There is no installation or build command.
