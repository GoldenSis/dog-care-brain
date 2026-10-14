# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

- Add durable project-specific notes here as they are discovered through real work.
- The browser app has no build step. Serve the repository root (`python3 -m http.server`) for static mode (localStorage and accounting IndexedDB), or `python3 api/server.py` for slice-1 accounts (flag on, SQLite). Zero pip deps for the API.
- Critical journeys are capture → editable text → timeline, voice dictation → stop/edit → timeline, daily handoff → evidence source, the booking, agreement, document and monthly-summary flows in [Daily workflows](docs/daily-workflows.md), and guide browsing and private experience save/edit/reload in [Maison de la Santé](docs/maison-sante.md).
- UI changes require a mobile viewport check, no horizontal overflow, and browser-console inspection. Browser tests need Playwright and its matching Chromium binary, not Crawl4AI; see README's acceptance checks for setup and optional `DOGCARE_EVIDENCE_DIR` output.
- Risk tiers determine the minimum gate: low (docs/copy only) requires syntax/unit checks; medium (UI, capture, storage, crawler behavior) requires the full relevant suite and browser evidence; high (microphone/privacy wording, non-diagnostic health language, stored-data compatibility, crawl boundaries, authentication, payments, or destructive actions) requires the full suite, independent review, and explicit human approval before external release.
- Slice 1, daily-workflow, knowledge and accounting gates: run the Python, Node and browser commands in [README acceptance checks](README.md#acceptance-checks). Browser checks cover both modes and await rendered readiness. Flag off = `python3 -m http.server`; flag on is injected only by `api/server.py`.
- Accounting intake, invoices, original documents, workbook export and static/account storage contracts: read [Comptabilité](docs/comptabilite.md) before changing finance modules.
- Private API storage defaults to `~/.local/share/dogcare-brain`; runtime paths must resolve outside the static root. See README for legacy data relocation. Import eligibility closes on care writes; initialization protects pre-fix saved history too.
- Account mutations bind to the loaded business and check care revisions; see README for the CLI contract and stale-draft recovery. Read snapshots and their revisions in the same transaction.
- Generated crawl corpora belong outside the repository unless explicitly reviewed and approved for inclusion.
- French terminology: use **carnet de bord** for everyday records and **dog-sitter** for the person, following the user's correction (2026-09-16). Label individual entries **notes du quotidien**. Do not translate everyday care as **soins** or the role as **gardeur/gardien de chien**. Keep actual health and veterinary terms, medical guidance, privacy meaning, and the idiom **Aux petits soins** intact.

- API role projections, explicit client access, login transport and quoted options are documented in `docs/client-portal.md`. Real signup is closed; tests opt into loopback development signup. Never enable debug-outbox delivery for production.

- The API static surface is an explicit `STATIC_FILES` allowlist in `api/server.py`; new frontend assets need a deliberate entry. Repository/deployment/test files are never API static content. Verify with `tests.test_static_boundary`.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
