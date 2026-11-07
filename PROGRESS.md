# Current handoff

Updated 7 November 2026, Malaysia time. Treat this as a dated handoff and check current Git and deployment evidence before continuing.

## Baseline and outcome

- Started on `main` at human commit `d411391` (Add unread filtering and website backups), with a clean working tree.
- This task affects development only. Added a short agent entry guide, a shared Claude entry point, development decisions and checks, and rules for continuity, commit messages, and clean handoffs.
- The human makes every commit manually. Agents leave reviewable changes, draft a precise commit message, and explain completed changes and observed human commits in plain language in chat.
- Windows and website reader behavior is unchanged by this documentation task.

## Working tree and publication

- **Local:** this documentation change is uncommitted. Intended files are `AGENTS.md`, `CLAUDE.md`, `README.md`, `PROGRESS.md`, `docs/DEVELOPMENT.md`, and `docs/HISTORY.md`. There were no pre-existing edits. Nothing was staged, committed, pushed, or deployed by the agent.
- **GitHub:** `git ls-remote origin refs/heads/main` confirmed public `main` at `d411391a1a30ab2f203bc1ff5c03cb0f65c48ead` during this task.
- **Live website:** the downloaded `/static/app.js` and `/hosted.js` matched the committed reader scripts after normalizing line endings. The unread filter and website backup code are published. The [live edition](https://idigest.pages.dev/edition.json) contained 600 headlines and `refresh.last_success_at` was 7 November 2026 at 22:34:38 +08:00.
- Windows starts through `Start Morning Signal.cmd` and keeps personal data in `data/`. The website stores each browser's preferences and bookmarks separately. See [README.md](README.md) for usage.

## Verification

- **Earlier feature checks, before this documentation task:** all 36 Python tests passed. Browser checks covered unread filtering on both readers, backup transfer between isolated browser profiles, merging existing bookmarks, repeated import, rejecting invalid input, and narrow-screen layout.
- **This documentation task:** all 19 local Markdown links and 15 referenced code/configuration paths checked; documented app options and the Claude import verified; `git diff --check` passed. Earlier checkpoints were preserved, only the six intended documents changed, and nothing is staged. An independent agent without this chat's history correctly identified startup, code locations, checks, publication status, pending work, and commit ownership; it found no material continuity gaps. Application tests were not rerun because this task changes documentation only.
- See [the development guide](docs/DEVELOPMENT.md) for checks appropriate to the next change. See [historical checkpoints](docs/HISTORY.md) for older evidence.

## Next actions and acceptance

1. Documentation checks are complete. The human can review and manually commit the six documentation files, using the commit draft in chat, then push when ready.
2. After the daily schedule around 06:30 Malaysia time on 8 November 2026, inspect [the publication workflow](https://github.com/HansYap/IDigest/actions/workflows/publish-edition.yml). Confirm a **scheduled** run actually sent the build request and that the resulting deployment serves an edition newer than the timestamp above. At the last inspection, the only run was the [successful manual run](https://github.com/HansYap/IDigest/actions/runs/42373282905). A green run can skip the request if the hook is missing, so inspect the outcome as well as its status.
3. If the request succeeded but the edition remains old, check the corresponding deployment in Cloudflare Pages. Keep the deploy hook URL private.

No implementation blocker is known. The scheduled publication check remains unfinished until both the build request and newer live edition are verified. GitHub publication of these documentation changes depends on the human committing and pushing them.
