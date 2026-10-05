# Maison de la Santé

A direct workspace destination combines six sourced everyday-care guides, three provider-hosted videos and private experience drafts. Search, category filters and three optional topic choices help find a resource. The choices navigate educational content; they do not diagnose a dog or choose a treatment.

Open **Maison de la Santé** (**Care & wellbeing** in English) from the persistent navigation. **Show all** lists guides and saved experiences; select **Videos and tutorials** to browse the three videos. Search matches the selected category, ignoring case and accents. **Where to start?** offers three topics that select relevant good-practice guides. Open a guide for its steps, sources and related videos, then use **Back to resources** to return to the list.

Guide summaries and controls support French, English, Italian, German and Spanish. Each guide identifies its primary sources and their languages. Videos open on the provider site and are labelled English; no third-party media, embedded player or tracking frame is loaded by the app. The catalogue lives in `knowledge-content.js` and source links were checked on 5 October 2026.

## Private experience

“Conseils de grand-mère” and colleague experiences start empty. Add a title, context and category, with optional attribution and an HTTP(S) source/video link. Save, reopen and edit the resulting **private, unreviewed draft**. There is no publication, clinical-approval, messaging or sharing action. User-entered text is displayed as text, and links cannot use executable schemes or embedded credentials. A source link supplied by a contributor does not turn a draft into a sourced guide.

A failed save retains the form and never reports success. Unsaved form entries survive in-app navigation and language changes, but must be saved before closing or reloading the page; these entries do not trigger the care-note draft warning. **Cancel** discards the unsaved edits. Titles, context and attribution retain the contributor's text when the interface language changes. Conflicts require copying the unsaved entries and reloading current data before saving again; tabs do not refresh one another automatically.

## Storage and compatibility

- Static mode stores version-1 experiences under `dogcare-knowledge-v1` in the current browser. Saves require Web Locks in a current browser on HTTPS or localhost. Web Locks serialize writes and the loaded snapshot is compared before saving. Changed storage rejects stale writes. If locking or storage is unavailable, no write is attempted without that protection. Browser quota limits apply; there is no server copy or synchronization.
- Account mode stores a separate `business_knowledge` snapshot, keyed by business. `/api/state` reads it in the same transaction as care data and the shared revision. `PUT /api/knowledge` uses the existing session, business binding, origin/content-type checks and revision precondition. Invalid records roll back atomically.
- `CREATE TABLE IF NOT EXISTS` adds the new table. Existing accounts start with no contributed experiences; existing notes, bookings, agreements, documents and sessions are not rewritten. Experiences are not silently imported from browser storage into an account.
- Invalid stored experiences show a load error and block experience saves without replacing the snapshot. Sourced guides remain available. Resetting demo observations leaves experiences intact in both modes.

## API contract

Read `knowledge` from `GET /api/state`, then send `PUT /api/knowledge` with `{ "knowledge": <snapshot> }`, the session cookie, `X-DogCare-Business: <business_id>` and `If-Match: "<revision>"` as described in the [mutation contract](../README.md#mutation-contract). This is a **full replacement**: preserve every experience you want to keep. `{ "knowledge": { "version": 1, "experiences": [] } }` clears the saved experiences; the UI has no deletion control. A successful write returns the full account state, advances the shared business revision and closes legacy import eligibility, even for an empty snapshot. It leaves care notes and daily records unchanged.

A snapshot has exactly `version: 1` and an `experiences` array of at most 1,000 records. Every field below is required; use `""` for an unused attribution or link. Extra fields are rejected.

| Experience field | Value |
| --- | --- |
| `id` | Unique within the snapshot; 1–81 ASCII letters, digits, underscores or hyphens, beginning with a letter or digit. |
| `title` | Nonblank string, at most 120 Unicode code points. |
| `body` | Nonblank context string, at most 4,000 Unicode code points; line breaks and tabs are allowed. |
| `category` | `"traditional"` or `"colleague"`. |
| `author` | String, at most 120 Unicode code points; may be empty. |
| `url` | String, at most 2,000 Unicode code points; may be empty. A nonempty link needs HTTP(S), a host and a valid port if supplied, with no credentials, whitespace or backslashes. |
| `status` | Always `"draft"`. |

Text is preserved without automatic translation. ASCII control characters and DEL are rejected, except for newline, carriage return and tab in `body`. Invalid records return 400 and database failures return 500; failed writes leave the snapshot, revision and import eligibility unchanged. The authoritative validators are [api/knowledge.py](../api/knowledge.py) and [knowledge-model.js](../knowledge-model.js); shared authentication, precondition and request-size errors are listed in [README errors](../README.md#errors).

## Checks

`tests/test_knowledge_api.py` exercises persistence, edit/reload, isolation, stale/switched-account rejection, invalid links/status and rollback without changing care data. `tests/test_knowledge_browser.py` exercises both storage modes: search, guide/video links, topic choices, five locales, private add/edit/reload, escaped content, failed-save drafts and two-tab conflicts. The shared navigation acceptance checks include this twelfth destination at desktop, tablet and phone sizes.

Run with the repository's full API/browser suite and JavaScript checks from the README. Optional `DOGCARE_EVIDENCE_DIR` captures French guide and contribution views using synthetic fixtures. The external-video journey intercepts the provider page in the fixture; it checks the opened URL rather than pretending to verify remote playback. Provider URLs and metadata require a separate live source check.
