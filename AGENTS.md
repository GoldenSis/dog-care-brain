# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

- Add durable project-specific notes here as they are discovered through real work.

## Localization (i18n)

Vanilla, zero-dependency i18n lives entirely in `app.js`. There is no build step and no framework.

- `translations` is a dict keyed by the **exact English source string**, with locale objects `en`/`fr`/`it`/`de`/`es`. `en` is intentionally empty — `t()` falls back to the English source.
- `t(text)` → `translations[lang][text] || text`. `tf(text, params)` → `t()` then substitutes `{token}` placeholders. `translateTag(tag)` → full-string match first, else splits on `' · '` and translates each segment (handles dynamic tags like `Time · 10:30`).
- **Every user-facing string in the view render functions must be wrapped in `t()`/`tf()`** (or, for `index.html` static chrome, carry `data-i18n`). `localizeContent()` only translates `[data-i18n]` elements + exact-match text nodes, so anything interpolated must go through `t()` explicitly.
- **Keys must be byte-identical to the source literal — mind curly `’` (U+2019) vs straight `'` (U+27) apostrophes.** A curly/straight mismatch silently leaks English (this bit us once on `Today's rhythm`). Keys containing a straight `'` must be double-quoted in the dict.
- **Data stays English in memory/storage; translate only at the render boundary via `t()`.** The `dogs`, `baseObservations`, and inferred-tag values are matched by regex in `careInsight()`/`infer()`, so translating the stored values would break that logic. Proper nouns (dog names, owner, clinic names like `Clinique Artémis · Vet.Avenir`) are intentionally left to fall back.
- For word-order-sensitive strings (e.g. `{name}’s day` → FR `La journée de {name}`), use `tf()` with a `{name}`/`{count}` placeholder rather than prefix/suffix concatenation.
- **Verification:** a headless render harness (Node `vm` + DOM stubs) proxies each locale dict and renders every view for both dogs, asserting `t()` never falls back — the definitive "zero English leaks" check. A browser pass (`chrome-devtools-axi`) confirms end-to-end wiring and the live language switch. When browser-testing, serve with `Cache-Control: no-store`; Chrome will otherwise serve a stale `app.js`.

