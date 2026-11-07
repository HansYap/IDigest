# Morning Signal — development checkpoint

## Agreed requirements

- Free local news app. No paid APIs, required API keys, hosting, or AI services.
- Tech, gaming/reverse engineering, internet and pop culture, animals, science, motorsport, and Malaysia.
- A short daily digest, topic watchlist, saved stories, source links, and easy Windows launch.
- Cached stories load immediately; background collection has bounded timeouts.
- Save work here so development can resume after an interruption.

## Current state

The first version is implemented in this folder:

- Python standard-library server and SQLite news engine; no package installation needed.
- 25 configured public RSS/Atom feeds, independently verified. Exact source evidence in SOURCES.md and source_report.json.
- Responsive Today / All stories / Watchlist / Saved views, search, category filters, bookmarks, read state, source health, and editable settings.
- Double-click Windows launcher and background refresh; local-only address.
- Plain-text publisher excerpts. No generated news or AI dependencies.

Verification completed so far:

- 27 automated parser, cache, duplicate, read-state, settings, failure-handling, and HTTP tests pass.
- JavaScript syntax checked.
- Live full feed refresh: 25/25 healthy in 4.59 seconds in an isolated test; visible cache up to 600 stories.
- Cached state benchmark: approximately 0.16 seconds with 1,000 stored rows.
- Browser checks passed for saving/removing a story, watchlist search, changing digest size, restoring default preferences, and source health. Desktop and narrow layouts inspected.
- Fixed real feed excerpt bug caused by media captions; future matching duplicates inherit read state; nightly shadPS4 builds stay out of the digest.

## Finished checkpoint — 15 October 2026

The first version is complete. No required implementation work remains.

- Restarted with the corrected parser and refreshed the existing cache. All 25 sources succeeded; full collection took about four seconds, cached HTTP response about 0.3 seconds including the client request.
- Verified the real Windows hidden launcher starts the app and reuses an existing instance on reopening.
- Preferences survived restart. Default digest size restored to 15; test bookmarks removed.
- Increased watched-topic priority so yesterday's relevant developments can lead today's digest ahead of unrelated breaking headlines.
- Reran all 27 tests after the final relevance change: pass.
- Browser confirmed corrected excerpts and watched-topic priority. Saved preview.jpg. Temporary viewport override reset.
- Tested the Settings → Stop Morning Signal button successfully. The app is stopped after verification; double-click Start Morning Signal.cmd to reopen it.
- Finished source snapshot saved as .checkpoints/morning-signal-v1.zip (runtime data excluded).

## Practical limits

- Only the configured feeds are collected; it cannot discover every story on the internet.
- Similar-headline grouping is conservative and can leave differently worded coverage separate.
- Excerpts and headlines are publisher material, not AI summaries or independent verification.
- Refresh runs while the local app and computer are running; no system startup or wake schedule was installed.

## Follow-up fix — refresh control and library wording

- User reported losing the refresh button while reading. Confirmed that the old header scrolled away; no code removed the button.
- Made the toolbar sticky with an opaque background. Kept refresh actions from shrinking and gave the refresh button a 44-pixel touch target.
- Clarified All stories as a library collected across refreshes, with original publication dates. It has no hourly cutoff.
- Browser verified the button stays inside the viewport after scrolling far down All stories, at desktop width and at 320-pixel width with no horizontal page overflow.
- JavaScript syntax passes. Saved refresh-control.jpg and source snapshot .checkpoints/morning-signal-v1.0.1.zip.
- Only the separate test preview on port 8875 was stopped. The user's app on its usual port was not stopped. Reload the existing browser tab once to load the updated CSS and wording; no server restart is needed.

## Resume instructions

Latest update: configurable expiry and bookmark protection are complete. Settings now offers 1/3/7/14/30 days for unsaved stories, with 30 days preserved as the default. Automatic cleanup runs on startup, preference changes, and refresh; expired unsaved items are also excluded from live snapshots and removed from the browser's active offline cache. Bookmarks are exempt from time and cache-size limits and no longer hit the old 1,000-row snapshot limit. Removing an expired bookmark makes it eligible for cleanup immediately.

All 33 tests pass. Browser test in a separate temporary database confirmed a 1-day window removes a 2-day-old unsaved story while keeping a 12-day-old bookmark. Temporary test preview and its files were cleaned up. The actual app was restarted at port 8765 and existing preferences/bookmarks were checked as preserved; its retention remains 30 days. The real reader is running, and its new Settings panel is open as a deliverable. Screenshot: retention-settings.jpg. Source checkpoint: .checkpoints/morning-signal-retention-update.zip.

Read this file and README.md, inspect existing files, and run the documented checks before changing anything. Preserve the free/local-only requirement. No publication or external account integration is needed.
