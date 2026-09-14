# Muse workspace design review

Captured on 2026-09-14 using isolated local servers, seeded demo records, French UI, Chromium, and device scale 1. No live account data was used.

- Before: `5121a03ba169e2138a0b2be7cf4d6562bac67713` (merged slice 1).
- After: `7b210c60597531e16c3f14a627c41e1263273999` (rebased design and reviewed integration fixes).
- Mobile viewport: 390 × 844. Desktop viewport: 1440 × 1000. All captures show the full page.

| Viewport width | Before | After |
| --- | --- | --- |
| 390 | [Before mobile](before-390.png) | [After mobile](after-390.png) |
| 1440 | [Before desktop](before-1440.png) | [After desktop](after-1440.png) |

Validation: all 76 Python tests passed, including the original 18 tests and 31 browser tests across account/local demo modes. All 17 JavaScript adapter tests passed. Responsive checks covered 11 routes × 5 languages × 5 widths (320, 390, 700, 768, 1440): no page/content overflow, missing images, or browser errors. The gallery film played with native controls.

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --python 3.12 --with playwright==1.61.0 python -m unittest discover -s tests -v
node --test tests/test_api_adapter.js
node --check app.js
node --check api.js
git diff --check
```

The shared browser journeys now select English explicitly, with a separate test for the French demo default and saved language preference. Account preferences remain authoritative. Empty care-log navigation and record ID `0` are covered without weakening the escaping or save checks.

The pull request is for the owner’s visual approval. It must not be merged automatically.
