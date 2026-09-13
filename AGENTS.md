# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

- Add durable project-specific notes here as they are discovered through real work.
- The browser app has no build step. Serve the repository root (`python3 -m http.server`) for the localStorage MVP, or `python3 api/server.py` for slice-1 accounts (flag on, SQLite). Zero pip deps for the API.
- Critical journeys are capture → editable text → timeline, voice dictation → stop/edit → timeline, and daily handoff → evidence source.
- UI changes require a mobile viewport check, no horizontal overflow, and browser-console inspection. Browser tests need Playwright and its matching Chromium binary, not Crawl4AI; see README's acceptance checks for setup and optional `DOGCARE_EVIDENCE_DIR` output.
- Risk tiers determine the minimum gate: low (docs/copy only) requires syntax/unit checks; medium (UI, capture, storage, crawler behavior) requires the full relevant suite and browser evidence; high (microphone/privacy wording, non-diagnostic health language, stored-data compatibility, crawl boundaries, authentication, payments, or destructive actions) requires the full suite, independent review, and explicit human approval before external release.
- Slice 1 gates: `python3 -m unittest tests.test_api_server tests.test_tenant_isolation tests.test_crawl_site -v`, `node --test tests/test_api_adapter.js`, and `uv run --python 3.12 --with playwright==1.61.0 python -m unittest discover -s tests -v` (matching Chromium installed). Browser checks cover both modes and await rendered readiness. Flag off = `python3 -m http.server`; flag on is injected only by `api/server.py`.
- Private API storage defaults to `~/.local/share/dogcare-brain`; runtime paths must resolve outside the static root. See README for legacy data relocation. Import eligibility closes on care writes; initialization protects pre-fix saved history too.
- Account mutations bind to the loaded business and check care revisions; see README for the CLI contract and stale-draft recovery. Read snapshots and their revisions in the same transaction.
- Generated crawl corpora belong outside the repository unless explicitly reviewed and approved for inclusion.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
