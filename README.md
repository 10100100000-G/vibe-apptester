# Vibe App Tester 🧪

**A pre-launch QA check for apps built with AI tools** (Lovable, Bolt, Cursor, Replit, v0, Claude Code).

AI-built apps often ship with problems their makers never see: pages that crash, prices
showing "NaN", buttons that lead nowhere, and layouts that break on phones. Security
scanners don't look for these. This skill gives your AI coding agent a QA engineer's
checklist, so it can test your app on desktop and mobile and hand you a plain-English
report, with a ready-to-paste **fix prompt** for every problem.

👉 **See what you get:** [example report](examples/sample_QA_REPORT.md)

## What the free Lite version checks

On every page, on a desktop screen **and** a phone screen:

- JavaScript crashes and console errors
- Failing API calls and missing files (4xx / 5xx)
- Broken links, dead `#` links and 404 pages
- Broken images
- Leftover `undefined`, `NaN`, `[object Object]`, "lorem ipsum" and TODOs on screen
- Pages that don't fit phones (missing mobile viewport, content wider than the screen)
- Missing page titles and slow pages

It only reads pages. It never submits forms, and it skips logout and delete links.

## Install

**Claude Code:** copy the `skills/vibe-app-tester-lite` folder into `~/.claude/skills/`
(for all your projects) or into `.claude/skills/` inside one project.

**Other coding agents (Cursor, Codex, etc.):** copy the folder into your project and ask:
*"Read skills/vibe-app-tester-lite/SKILL.md and follow it to test my app."*

The agent installs what it needs (Python + Playwright) the first time.

## Use

Start your app, then ask your agent:

> Test my app before launch.

You'll get `QA_REPORT.md` with a verdict, the problems in plain English ordered by
importance, screenshots, and a fix prompt for each.

You can also run the crawler yourself:

```bash
pip install playwright && python -m playwright install chromium
python skills/vibe-app-tester-lite/scripts/smoke_crawl.py http://localhost:5173 --out qa-results
```

## Pro version (coming soon)

The full version also:

- **Stress-tests your forms**: empty, invalid, very long and non-English input, and
  double-click duplicate submissions
- **Writes end-to-end tests** for your key user journeys (signup, the main action,
  checkout), checks your data really saves, and leaves the tests in your project to re-run
- Adds an **exploratory checklist** of the bugs AI-built apps most often ship with
  (lost logins on refresh, missing empty and error states, wrong dates and prices...)

⭐ **Star or watch this repository** to hear when it's released.

## Notes

- This is functional testing, not a security audit.
- Always test your own app, ideally a local or staging copy.
- Found a false alarm or a bug the crawler missed? Please
  [open an issue](../../issues): every report makes it better.

## License

MIT
