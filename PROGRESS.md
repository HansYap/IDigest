# Current handoff

Updated 8 November 2026, Malaysia time.

## Baseline and outcome

- Started from a clean `main` at human commit `700210e`, which added the blue sunrise browser-tab icon to the website.
- The local **website** digest now uses the edition's refresh time and ranks stories independently of their read status. Read stories show a text label and keep their place. **Unread only** hides read stories from that selection, and the caught-up message appears when the selection is finished.

## Working tree and publication

- **Local** edits in [the reader](static/app.js), [the website stylesheet](static/website.css), [README](README.md), and this handoff are ready for review and a manual commit.
- **GitHub** `main` was checked directly and points to `700210e`.
- **Live** the [site](https://idigest.pages.dev/) declares the sunrise favicon. The digest change is local. The earlier [scheduled request](https://github.com/HansYap/IDigest/actions/runs/42435146286) succeeded around 09:39 Malaysia time on 8 November, later than the configured 06:30.

## Verification

- All 37 Python tests passed. `node --check static/app.js` and `git diff --check` passed.
- Chrome used a temporary Pages build with five digest stories selected from eight. Marking read or unread, opening a story, and reopening the edition preserved the lineup. **Unread only** hid exactly the read stories and reached the caught-up message. Checked the read label, keyboard focus, and the Windows reader's existing controls with temporary data.

## Next action

Review and manually commit the digest change. After publication, verify the **Read** label, fixed lineup, and **Unread only** on the live digest.
