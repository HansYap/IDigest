# Working in Morning Signal

Morning Signal has a Windows reader with local storage and a static website on Cloudflare Pages. Keep changes small and state whether each change affects Windows, the website, or both.

## Start each session

1. Read [README.md](README.md) for usage and [PROGRESS.md](PROGRESS.md) for the current handoff.
2. Inspect `git status --short --branch`, `git log -5 --oneline`, and the relevant source files before editing. Preserve existing work.
3. Check recorded claims against current evidence. Track local edits, GitHub commits, and live deployments separately.
4. Choose one useful task and state what observable result will count as complete. Read [the development guide](docs/DEVELOPMENT.md) for applicable checks and design decisions.

## Project map

| Area | Files |
| --- | --- |
| Windows launch and local server | `Start Morning Signal.cmd`, `launch.ps1`, `app.py` |
| Collection, ranking, SQLite storage, and expiry | `news_engine.py` |
| Shared reader screens and filters | `static/index.html`, `static/app.js`, `static/styles.css` |
| Website preferences and backups | `static/hosted.js` |
| Website build | `scripts/build_pages.py` |
| Daily build request | `.github/workflows/publish-edition.yml` |
| Feed configuration and evidence | `sources.json`, [SOURCES.md](SOURCES.md), `source_report.json` |
| Automated checks | `tests/` |

## Working rules

- **The human makes every commit manually.** Never create, amend, or rewrite commits through Git commands, scripts, APIs, or a graphical interface. This includes merges, rebases, and cherry-picks that create or rewrite commits. Draft a commit message for the human using the development guide.
- Leave edits available for human review. Stage files, push existing commits, or deploy only when the user explicitly requests that action.
- Keep bookmarks, browser profiles, exported backups, `data/`, logs, and deployment secret values private. Use temporary storage and synthetic stories for testing. Confirm the publish output contains only intended public files.
- Reuse the existing Python standard library and browser code. Preserve saved stories and settings when changing storage or expiry behavior.
- Work on one logical change at a time. Record newly discovered unrelated work in the handoff.
- Keep durable project decisions in repository documents. Update the relevant document with a behavior change. Link to details instead of copying them into this file.

## Finish each change and session

1. Run the checks appropriate to the change from the development guide. Report failures and skipped checks accurately.
2. Review the diff and `git status`. Remove only temporary artifacts created by this task. Keep the normal startup path usable and preserve the human's uncommitted work.
3. Update [PROGRESS.md](PROGRESS.md) with the outcome, evidence, unfinished work, and next action. Record incomplete work explicitly if interrupted.
4. After each completed logical change, explain the outcome in plain language in chat, with the affected edition, verification, local/GitHub/live status, next step, and suggested commit message.
5. When a new human commit is observed, inspect it and explain its effect and publication status in chat. Reconcile the handoff during the next substantive update. Avoid creating a new documentation change solely to record every commit hash.

Historical checkpoints are in [docs/HISTORY.md](docs/HISTORY.md). Read them when investigating a past decision or regression.
