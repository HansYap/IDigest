# Working in Morning Signal

Morning Signal has a Windows reader and a static Cloudflare Pages website. Keep changes small and state whether they affect Windows, the website, or both.

## Begin work

1. Read this guide and [PROGRESS.md](PROGRESS.md) in a fresh agent context (new chat or reset). Compaction summarizes the existing session. Messages and commits do not start another. See the development guide for handoff rules.
2. Inspect `git status --short --branch`, `git log -5 --oneline`, and the relevant source files before editing. Preserve existing work.
3. Check recorded claims against current evidence. Track local edits, GitHub commits, and live deployments separately.
4. Choose one useful task and define completion. Open only relevant sections of [README.md](README.md) for usage and [the development guide](docs/DEVELOPMENT.md) for checks and decisions. Expand reading when evidence requires it.

Keep this guide near 600 words and the handoff near 400. Replace stale facts; preserve unresolved risks. Read relevant excerpts and avoid rereading unchanged material. See the development guide's maintenance rules before adding history or documents.

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

## Finish a change or prepare to end a session

1. Successful completion requires verified work and a clean handoff. Run applicable checks from the development guide. Report failures and skipped checks accurately; stopping with partial work is not successful completion.
2. Review the diff and `git status`. Remove only temporary artifacts created by this task. Keep the normal startup path usable and preserve the human's uncommitted work.
3. Update [PROGRESS.md](PROGRESS.md) when project state changes, with the outcome, evidence, unfinished work, and next action. Record partial work before a planned pause and at useful checkpoints. Explanations alone do not need a history entry.
4. After each completed logical change, explain the outcome in plain language in chat, with the affected edition, verification, local/GitHub/live status, next step, and suggested commit message.
5. When a new human commit is observed, inspect it and explain its effect and publication status in chat. Reconcile the handoff during the next substantive update. Avoid creating a new documentation change solely to record every commit hash.

Search [history](docs/HISTORY.md) only for a specific past decision or regression.
