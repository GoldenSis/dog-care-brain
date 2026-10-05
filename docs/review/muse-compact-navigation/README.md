# Muse compact navigation

One compact business brand and persistent, labelled navigation give direct access
to all 11 destinations. Desktop and tablet use a grouped sidebar; phones use two
rows that scroll horizontally. The dashboard greeting, orange and cream palette,
original photographs, source links, and French carnet de bord wording remain.

The comparison baseline is main at
`52d40482b5c595f6d65d75cc98f2cd0bb4b4b356`. The after images show the compact
navigation with the scrolling correction in this change. Screenshots use isolated
static fixtures, French, Chromium, and device scale 1; no live account data is used.

| Viewport | Before | After |
| --- | --- | --- |
| 1440 × 900 | [Desktop before](before-1440.png) | [Desktop after](compact-nav-1440-False.png) |
| 1024 × 768 | [Tablet before](before-1024.png) | [Tablet after](compact-nav-1024-False.png) |
| 390 × 844 | [Phone before](before-390.png) | [Phone after](compact-nav-390-False.png) |

Desktop and tablet content begins at 136px, compared with 325px in the baseline.
On phones, persistent navigation moves the content start from 168px to 262px.
Later phone destinations require horizontal scrolling within the navigation.
Navigation targets remain at least 44px, with keyboard access and one active page.

Selecting a destination from scrolled content now returns to its heading while
revealing the active button within the navigation's own scroll container.
Regression checks cover both storage modes, switching between the dashboard and
dog record, horizontal button reveal on phones, and vertical sidebar reveal in a
short desktop viewport. The heading and zero document scroll are asserted before
capturing these English fixture screenshots:

- [390 × 844 after switching from scrolled content](nav-scrolled-heading-390-False.png)
- [1024 × 768 after switching from scrolled content](nav-scrolled-heading-1024-False.png)
- [1440 × 900 after switching from scrolled content](nav-scrolled-heading-1440-False.png)

Validation on 2026-10-05: **101 Python tests passed**, with no failures or skips,
including API, tenant isolation, crawler, and static/account browser checks.
**17 JavaScript adapter tests passed**, with no failures or skips. JavaScript
syntax and whitespace checks passed.

```sh
uv run --offline --python 3.12 --with playwright==1.61.0 python -m unittest discover -s tests -v
node --test tests/test_api_adapter.js
node --check app.js
node --check api.js
git diff --check
```

Browser coverage includes all 11 routes and five locales at the three comparison
sizes, active state, keyboard activation, no horizontal page overflow, capture
drafts, simulated dictation, editing, saving, reload persistence, and handoff
source links. Navigation checks assert no console errors or page errors.

To refresh the after and heading screenshots:

```sh
DOGCARE_EVIDENCE_DIR=docs/review/muse-compact-navigation \
  uv run --offline --python 3.12 --with playwright==1.61.0 python -m unittest \
  tests.test_browser_acceptance.StaticBrowserAcceptanceTest.test_all_destinations_are_direct_and_keep_selection \
  tests.test_browser_acceptance.StaticBrowserAcceptanceTest.test_navigation_from_scrolled_content_starts_at_heading -v
```
