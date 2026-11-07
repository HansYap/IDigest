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

## Verification

Use the applicable rows. Record the commands or user actions actually performed and their results.

| Change | Checks |
| --- | --- |
| Documentation only | Check local links, named files and commands against the repository, and run `git diff --check`. Inspect new untracked documents as well as tracked diffs. |
| Python, storage, server, or build behavior | Run `python -m unittest discover -s tests -v`. Exercise the changed behavior through its normal entry point using temporary data. |
| Browser scripts | Run `node --check static/app.js` and `node --check static/hosted.js` when Node is available, then test the changed interaction in a browser. Record an unavailable syntax check as skipped. Node is a development check tool. |
| Shared UI | Exercise both the Windows server and a generated website preview. Check a narrow screen if layout changes. |
| Bookmarks, settings, or backup handling | Use isolated browser profiles. Check saving and reload, migration, repeated import, and invalid input against existing saved data. |
| Published website behavior | Check the relevant live assets or behavior after deployment. A local build or GitHub commit alone leaves publication unverified. |

For website builds, use the command and preview instructions in README.md. Feed collection uses the network, so distinguish feed failures from code failures. For deterministic interaction tests, use synthetic edition data with the real builder and reader.

For a local test server, use temporary storage and a separate unused port. `app.py` recognizes an existing instance by project folder, so `--data-dir` alone can reconnect to the real reader. The fixtures in `tests/test_server.py` demonstrate an isolated server.

When checking the daily publication schedule, confirm that a scheduled GitHub run sent the deploy request, then verify that the corresponding Cloudflare deployment serves a newer edition. The workflow can finish successfully while skipping a missing deploy hook, so inspect the outcome as well as the green status. Keep the hook URL out of output and documents.

## Handoffs and clean sessions

Keep the current handoff short. Use these fields in PROGRESS.md and replace stale current facts as work progresses.

| Field | What to record |
| --- | --- |
| Baseline | Date in Malaysia time, branch, and inspected starting commit. |
| Outcome | Completed behavior and whether it affects Windows, the website, or development. |
| Working tree | Intended uncommitted files and any pre-existing edits belonging to the human. |
| Verification | Check, result, applicable commit or working tree, and any skipped or failed checks. Distinguish earlier evidence from checks run in this session. |
| Publication | Separately observed local, GitHub, and live status, with public evidence where available. |
| Blockers and next action | Remaining work, what prevents completion, and the exact evidence needed to finish. |

If interrupted, record the partial work, failing checks, and safe next action. Preserve work for review. A session can finish with reviewed uncommitted edits ready for the human, because the human owns the commit step.

Remove temporary files and stop test processes created by the task when safe. Inspect final Git status for accidental artifacts. Keep older checkpoints in [HISTORY.md](HISTORY.md) when they stop being useful in the current handoff. Revisit rules when a recurring failure or design change gives a reason to update them.

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
