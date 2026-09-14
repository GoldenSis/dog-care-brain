# Muse workspace design review

The workspace uses the Bivouac Club reference’s typography, compact navigation and joined photo/action layout, adapted to Le Bus des Toutous. French remains the default for the local demo; orange accents and Adine-Sophie’s original photographs and film carry through the care screens.

Captured on 2026-09-14 using isolated local servers, seeded demo records, French UI, Chromium, and device scale 1. No live account data was used.

- Before: `5121a03ba169e2138a0b2be7cf4d6562bac67713` (merged slice 1); original captures retained.
- After code: `03bd897161f410c92a718be518684c204ca4ea27` (modern design with PR #4’s care-log fixes).
- Mobile viewport: 390 × 844. Desktop viewport: 1440 × 1000. All captures show the full page.

| Viewport width | Before | After |
| --- | --- | --- |
| 390 | [Before mobile](before-390.png) | [After mobile](after-390.png) |
| 1440 | [Before desktop](before-1440.png) | [After desktop](after-1440.png) |

Validation on the combined code: **76 Python tests passed** with no skips, including 31 browser tests across account/local demo modes. **17 JavaScript adapter tests passed**. [275 responsive checks](modern-visual-qa.json) covered 11 routes × 5 languages × 5 widths (320, 390, 700, 768, 1440): no page/content overflow, missing images, or browser errors. Gallery film playback and native controls passed. [Navigation checks](modern-navigation-qa.json) verify the landscape menu stays inside the viewport, the phone menu remains reachable after scrolling, and capture remains accessible.

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --python 3.12 --with playwright==1.61.0 python -m unittest discover -s tests -v
node --test tests/test_api_adapter.js
node --check app.js
node --check api.js
git diff --check
```

The shared browser journeys select English explicitly, with separate coverage for the French demo default and saved language preference. Account preferences remain authoritative. Empty care logs still open capture for Billie, and record ID `0` retains its evidence link. The desktop invitation test now opens the grouped navigation before selecting Invite; all prior assertions remain.

Relative to PR #4 at `9b31e69`, API code, application state, care calculations, event handlers and persistence are unchanged. Independent review found no remaining blockers. Dashboard date/progress and business snapshot claims remain removed; planning and business screens still disclose sample data.

The pull request is for the owner’s visual approval. It must not be merged automatically.
