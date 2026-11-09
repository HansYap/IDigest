# Development guide

Use this guide when editing, verifying, preparing a handoff, or drafting a commit message. [AGENTS.md](../AGENTS.md) contains the session rules, [README.md](../README.md) contains launch and deployment instructions, and [PROGRESS.md](../PROGRESS.md) records the current work.

## Decisions to preserve

| Decision | Reason and consequence |
| --- | --- |
| Python standard library and plain browser JavaScript | Keeps Windows setup simple and avoids a package installation step for the reader. |
| Shared reader UI with separate Windows and website storage | Windows uses SQLite. The website uses each browser's storage. Check both editions when changing shared UI. |
| Feed collection during Cloudflare builds | The public site serves a published edition. Reload edition reads that edition. On-demand collection would require a different hosting design. |
| Public website output contains headlines, dates, sources, and links | The builder selects public fields and uses temporary storage. Personal bookmarks, settings, and private files belong outside the published output. |
| Bookmarks survive expiry | Unsaved stories expire according to their publication date. Preserve bookmarks when changing retention or cache limits. |
| Website imports merge bookmarks and restore saved preferences | Moving between browsers keeps the destination's saved stories. Validate the whole backup before writing the profile. |
| Human-owned commits | The user reviews and commits manually. The agent prepares a reviewable diff, evidence, and a precise message. |

Add a short dated explanation here when an agreed design decision changes. Include the reason and affected behavior so a later session can understand the choice.

### 9 November 2026: finite personal briefing (both editions)

`static/briefing.json` owns topic slots, defaults and portable headline rules. Python and `static/briefing.js` use the same policy; the snapshot includes it so hosted and offline reading need no extra request. Nine is the default ceiling. Candidates must be within 48 hours of the edition anchor; strict topic/source caps prevent repeated feeds from taking over. Caps scale for explicitly larger limits. Empty slots can use other qualified candidates under those caps, never stale filler. Ranking and duplicate representatives are independent of read status. Filters narrow the selected lineup.

Whole-phrase watch matching replaces substring matching, and its bonus applies once. Regional title matches modestly favour client markets; these and promotional/local title rules are limited heuristics, not semantic importance scoring. Malaysia coverage currently comes through Asia; cars has an engineering feed and an enthusiast reading destination. Source access/reuse findings live in [SOURCES.md](../SOURCES.md).

Preferences migrate once by version: replace only values equal to legacy starter defaults, retain custom values and bookmarks, enable newly introduced feeds while honoring known exclusions and explicit all-off choices. Windows records known source IDs in metadata; the hosted profile and new backups record the equivalent fields. Old backups remain valid. A pre-policy cached website edition has a bounded, stable fallback until a fresh edition loads.

The source flag `headlines_only` prevents excerpt retention where only headline links are suitable; `exclude_feed_categories` excludes known subscription tags before storage. These controls do not guarantee a publisher will never restrict an unmarked article. Keep the reading shelf collapsed in Saved and the end-of-edition message free of prompts to browse more.

## Verification

Use the applicable rows. Record the commands or user actions actually performed and their results.

| Change | Checks |
| --- | --- |
| Documentation only | Check local links, named files and commands against the repository, and run `git diff --check`. Inspect new untracked documents as well as tracked diffs. |
| Python, storage, server, or build behavior | Run `python -m unittest discover -s tests -v`. Exercise the changed behavior through its normal entry point using temporary data. |
| Browser scripts | Run `node --check static/app.js` and `node --check static/hosted.js` when Node is available, then test the changed interaction in a browser. Record an unavailable syntax check as skipped. Node is a development check tool. |
| Briefing policy or hosted preferences | Also run `node --check static/briefing.js` and `node --test tests/test_briefing.js`; cover quiet editions, legacy caches, custom limits, migration and backup preservation. |
| Shared UI | Exercise both the Windows server and a generated website preview. Check a narrow screen if layout changes. |
| Bookmarks, settings, or backup handling | Use isolated browser profiles. Check saving and reload, migration, repeated import, and invalid input against existing saved data. |
| Published website behavior | Check the relevant live assets or behavior after deployment. A local build or GitHub commit alone leaves publication unverified. |

For website builds, use the command and preview instructions in README.md. Feed collection uses the network, so distinguish feed failures from code failures. For deterministic interaction tests, use synthetic edition data with the real builder and reader.

For a local test server, use temporary storage and a separate unused port. `app.py` recognizes an existing instance by project folder, so `--data-dir` alone can reconnect to the real reader. The fixtures in `tests/test_server.py` demonstrate an isolated server.

When checking the daily publication schedule, confirm that a scheduled GitHub run sent the deploy request, then verify that the corresponding Cloudflare deployment serves a newer edition. The workflow can finish successfully while skipping a missing deploy hook, so inspect the outcome as well as the green status. Keep the hook URL out of output and documents.

## Handoffs and clean sessions

Following Lecture 5, a session starts with a fresh agent context, such as a new chat or a context reset. Compaction summarizes context within the existing session. Follow-up messages and Git commits are not session boundaries. Resuming the same saved context continues that session; replacing it with fresh context starts another. No manual session commands or status field are required.

A session ends when that context is abandoned or replaced. An ordinary reply does not end it. This does not establish successful completion. Following Lecture 12, claim successful completion only when the task passes verification and the clean-state checks pass. Assess all five areas: build, tests, recorded progress, temporary artifacts, and the normal startup path. Use the applicable verification rows above, explain checks that do not apply, and distinguish earlier evidence from newly run checks. Failed or unknown checks must remain visible in the handoff.

Before a planned stop or reset, save the handoff. Keep it current after meaningful changes so an unexpected interruption loses less information. After an abrupt stop, inspect actual files and checks rather than assuming cleanup ran. Lecture 5's suggestion to prepare a handoff when a task needs more than roughly 60% of the context window is a planning heuristic, not an automatic cutoff. Use reliable context measurements when available; never invent a percentage or skip verification to rush a finish.

Keep the current handoff short. Use these fields in PROGRESS.md and replace stale current facts as work progresses.

| Field | What to record |
| --- | --- |
| Baseline | Date in Malaysia time, branch, and inspected starting commit. |
| Outcome | Completed behavior and whether it affects Windows, the website, or development. |
| Working tree | Intended uncommitted files and any pre-existing edits belonging to the human. |
| Verification | Check, result, applicable commit or working tree, and any skipped or failed checks. Distinguish earlier evidence from checks run in this session. |
| Publication | Separately observed local, GitHub, and live status, with public evidence where available. |
| Blockers and next action | Remaining work, what prevents completion, and the exact evidence needed to finish. |

If stopping with unfinished work, record partial changes, failing checks, and the safe next action; label the work incomplete. Preserve work for review rather than discarding it to make Git look clean. The user requires manual commits, so reviewed uncommitted edits are an acceptable handoff when their scope and verification are explicit. Agents never commit or automatically roll back the human's work.

Remove temporary files and stop test processes created by the task when safe. Inspect final Git status for accidental artifacts. Preserve useful historical rationale according to the maintenance rules below. Revisit rules when a recurring failure or design change gives a reason to update them.

## Reading and document maintenance

- The startup reading set is AGENTS.md and PROGRESS.md. Search headings or keywords and read only relevant sections of other documents and code. Do not recursively open every linked document. Expand scope for dependencies, failures, or uncertainty that could affect correctness.
- Keep AGENTS.md near 600 words or fewer and PROGRESS.md near 400. Rewrite the current handoff instead of appending a session diary. Preserve unresolved work and evidence; move supporting detail behind a link when needed. These are practical targets, not context-window limits.
- Keep one authoritative home for each rule or decision and link to it. Add a document only when existing sections cannot hold the information clearly. Do not copy chat transcripts, full test logs, or routine commit descriptions into history; Git already preserves committed changes.
- HISTORY.md is searched only to answer a specific historical question. When it grows beyond roughly 2,000 words, move dated entries into files under `docs/history/`, grouped by period or topic, and leave a short index in HISTORY.md. Preserve dates, rationale, evidence, and working links. Do not load all archives at startup.
- Review length and duplication when editing the affected document. No separate maintenance job is needed. Definitions, explanations, and unchanged status alone do not require progress or history edits.

## Commit messages and chat reports

Draft a message after each completed logical change. The human chooses the files and makes the commit. If the human commits while work continues, inspect the new commit when it becomes visible and report its actual scope.

Use an imperative, specific subject, ideally within 72 characters. Name the behavior or component. In the body, explain why it changed, what now happens, and what evidence supports it. Use exact paths, command names, and meaningful identifiers when helpful. Prefer stable terminology over vague phrases such as "misc fixes". Never claim checks that were not run, include secrets, or describe unrelated files as part of the change.

For changes needing a body, use the following structure and omit empty sections. Keep each section concise.

```text
<Imperative description of the completed change>

Why
<Problem or requirement that motivated it>

Changes
- <Observable behavior and affected component or edition>

Verification
- <Actual command or interaction and result>

Remaining
- <Unfinished verification or publication step, when relevant>
```

After a completed change or an observed human commit, also write a brief plain-language chat message. Explain what the user can now do, what was checked, where the change exists, and the next unfinished step. For dashboard actions, give the exact page, one button at a time, and the expected result. The commit draft and chat explanation serve different readers and should both be understandable without the old conversation.

## Design background

These practices apply repository knowledge, short instruction entry points, durable handoffs, and session cleanup to this project's size. The manual-commit rule comes from the user.

- [Lecture 3 — Repository as the system of record](https://walkinglabs.github.io/learn-harness-engineering/en/lectures/lecture-03-why-the-repository-must-become-the-system-of-record/)
- [Lecture 4 — Focused instructions and links to detail](https://walkinglabs.github.io/learn-harness-engineering/en/lectures/lecture-04-why-one-giant-instruction-file-fails/)
- [Lecture 5 — Continuity across sessions](https://walkinglabs.github.io/learn-harness-engineering/en/lectures/lecture-05-why-long-running-tasks-lose-continuity/)
- [Lecture 12 — Clean handoffs](https://walkinglabs.github.io/learn-harness-engineering/en/lectures/lecture-12-why-every-session-must-leave-a-clean-state/)
