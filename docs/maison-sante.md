# Maison de la Santé

A direct workspace destination combines six sourced everyday-care guides, three provider-hosted videos and private experience drafts. Search, category filters and three optional topic choices help find a resource. The choices navigate educational content; they do not diagnose a dog or choose a treatment.

Guide summaries and controls support French, English, Italian, German and Spanish. Each guide identifies its primary sources and their languages. Videos open on the provider site and are labelled English; no third-party media, embedded player or tracking frame is loaded by the app. The catalogue lives in `knowledge-content.js` and source links were checked on 5 October 2026.

## Private experience

“Conseils de grand-mère” and colleague experiences start empty. Add a title, context and category, with optional attribution and an HTTP(S) source/video link. Save, reopen and edit the resulting **private, unreviewed draft**. There is no publication, clinical-approval, messaging or sharing action. User-entered text is displayed as text, and links cannot use executable schemes or embedded credentials. A source link supplied by a contributor does not turn a draft into a sourced guide.

A failed save retains the form and never reports success. Unsaved form entries survive in-app navigation and language changes, but must be saved before closing or reloading the page. Conflicts require copying the unsaved entries and reloading current data before saving again.

## Storage and compatibility

- Static mode stores version-1 experiences under `dogcare-knowledge-v1` in the current browser. Web Locks serialize writes and the loaded snapshot is compared before saving. Changed storage rejects stale writes. If locking or storage is unavailable, no write is attempted without that protection.
- Account mode stores a separate `business_knowledge` snapshot, keyed by business. `/api/state` reads it in the same transaction as care data and the shared revision. `PUT /api/knowledge` uses the existing session, business binding, origin/content-type checks and revision precondition. Invalid records roll back atomically.
- `CREATE TABLE IF NOT EXISTS` adds the new table. Existing accounts start with no contributed experiences; existing notes, bookings, agreements, documents and sessions are not rewritten. Experiences are not silently imported from browser storage into an account.
- A snapshot contains `version: 1` and up to 1,000 experiences. Each experience has `id`, `title` (120 characters), `body` (4,000 characters), `category` (`traditional` or `colleague`), optional `author` (120 characters) and `url` (2,000 characters), and `status: "draft"`. Optional fields are stored as empty strings. The server contract is in `api/knowledge.py`; the browser contract is in `knowledge-model.js`.

## Checks

`tests/test_knowledge_api.py` exercises persistence, edit/reload, isolation, stale/switched-account rejection, invalid links/status and rollback without changing care data. `tests/test_knowledge_browser.py` exercises both storage modes: search, guide/video links, topic choices, five locales, private add/edit/reload, escaped content, failed-save drafts and two-tab conflicts. The shared navigation acceptance checks include this twelfth destination at desktop, tablet and phone sizes.

Run with the repository's full API/browser suite and JavaScript checks from the README. Optional `DOGCARE_EVIDENCE_DIR` captures French guide and contribution views using synthetic fixtures. The external-video journey intercepts the provider page in the fixture; it checks the opened URL rather than pretending to verify remote playback. Provider URLs and metadata require a separate live source check.
