# DogCare Brain

A polished, build-free MVP for a small dog-care business. This premium **Muse** edition is branded for Adine-Sophie and Le Bus des Toutous. It follows Billie Blue and Charlie Rose from daily care capture through owner updates, scheduling, media, and accounting preparation.

## Run locally

From this directory, start any static file server:

```bash
python3 -m http.server 4173
```

Then open [http://localhost:4173](http://localhost:4173).

No install or build step is required. The four operational workflows—bookings, base rates/stay extensions, dog documents/follow-up and monthly summaries—are described in [Daily workflows](docs/daily-workflows.md). They persist in this browser in static mode and in the private SQLite database in account mode.

To [register a dog](docs/daily-workflows.md#registering-a-dog) without a booking or care note, open **Dogs / Chiens → ＋ Add a dog / Ajouter un chien**. Only the dog name is required; the owner can remain unknown. **All dogs / Tous les chiens** opens the saved profiles.

Static mode stores observations, pending invite previews, and language in the browser's `localStorage` (`dogcare-observations`, `dogcare-invites`, and `dogcare-language`), with operational records and documents in `dogcare-daily-v1` and [private experience drafts](docs/maison-sante.md) in `dogcare-knowledge-v1`. [Accounting records and originals](docs/comptabilite.md) use a separate IndexedDB database, `dogcare-finance-v1`. Browser quota limits apply; no cloud synchronization is implied. **Reset demo observations** in Settings restores sample observations while retaining saved notes, registered dogs, daily records, experiences, accounting records and originals, invites and language.

Slice 1 (accounts, SQLite, still zero pip deps) — local only, no email keys:

```bash
python3 api/server.py          # http://127.0.0.1:8787  (sets window.DOGCARE_API)
# In another terminal while the server is running:
curl -X POST http://127.0.0.1:8787/api/auth/request \
  -H 'Content-Type: application/json' -d '{"email":"you@example.com"}'
# Open the link in ~/.local/share/dogcare-brain/.dev-outbox/*.json
```

Open the `link` value from the newest outbox JSON for your email in the same browser profile where you want to use the app. Links are single-use and expire after 15 minutes; repeat the request above for a replacement if the link has expired or was already used. First verification creates a separate business for each new email, an owner account, and the Billie/Charlie demo dogs and observations. The business name comes from the email's local part; the interface retains the pilot branding and profiles. Later sign-ins with the same email return to that business. Sessions last 90 days. There is no sign-in form or sign-out control yet; use the auth endpoints below. Opening account mode without a valid session shows the [account recovery screen](#saving-and-recovery) and keeps care capture disabled.

### Import browser records

To import existing static-mode records, stop the static server and start account mode on the **same hostname and port** before saving anything to the business account. For the static URL above:

```bash
DC_HOST=localhost DC_PORT=4173 python3 api/server.py
# In another terminal:
curl -X POST http://localhost:4173/api/auth/request \
  -H 'Content-Type: application/json' -d '{"email":"you@example.com"}'
# Open the outbox link in the same browser profile used for the static app.
```

Use your original scheme, hostname, and port if different. `localhost:4173` and `127.0.0.1:8787` have separate browser storage; the default account URL cannot see records from the static URL. Sign in to an unused business account at the original origin, accept the recording notice if shown, and let the import finish before making account writes. Browser copies stay intact, but an account already used for care writes cannot import them.

Account mode imports whichever of the three browser keys exist, once per unused business. Missing keys leave the corresponding account data unchanged; explicitly empty observations or invites clear those collections. A language-only import also consumes this opportunity. The server's `imported` flag means import eligibility is closed, whether by import or by a successful observation, invite, language, dog, daily-record, document, experience or accounting write. Uploading audio alone does not close it. A browser marker (`dogcare-imported:<business_id>`) also prevents repeat automatic imports; the server flag protects the account across browser profiles. With no browser keys, the new account keeps its demo data and remains eligible until a care write.

**Daily dog names and owner associations, bookings, rates, clients, documents, private experiences and accounting records/originals are not imported by this legacy three-key process.** Imported observations retain their dog identifiers, but do not transfer daily profile details. The excluded records and files remain in their original browser storage; see [daily storage and migration](docs/daily-workflows.md#storage-and-migration), [experience storage](docs/maison-sante.md#storage-and-compatibility) and [accounting storage](docs/comptabilite.md#storage-and-contracts).

A notice appears before existing inline recordings transfer. Cancel leaves browser data intact and account loading paused; reload to continue. Failed imports remain retryable and keep capture disabled until account loading succeeds. Startup also closes import eligibility for older accounts with non-demo history, invites, recordings, or a non-English preference. Audio is uploaded separately before the snapshot. Local browser copies are retained and are not updated by later account saves; switching back to static mode displays those older browser copies.

### Account configuration and storage

All configuration is through environment variables read by `api/server.py`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DC_HOST` | `127.0.0.1` | HTTP bind address. |
| `DC_PORT` | `8787` | HTTP listen port. |
| `DC_ROOT` | Repository root | Static document root; the API server injects `window.DOGCARE_API="/api"` into HTML. |
| `DC_DATA_DIR` | `~/.local/share/dogcare-brain` | Base directory for private runtime files. |
| `DC_DB` | `<DC_DATA_DIR>/dogcare.db` | SQLite database, including daily records, document bytes, private experiences and accounting records/originals, using WAL mode. |
| `DC_OUTBOX` | `<DC_DATA_DIR>/.dev-outbox` | Local magic-link JSON files. |
| `DC_BLOBS` | `<DC_DATA_DIR>/blobs` | Audio files, under a directory per business ID. |
| `DC_INSECURE_COOKIE` | `1` | `1` uses HTTP magic links and omits `Secure` on the cookie; any other value uses HTTPS links and a `Secure` cookie. |

Use absolute paths for overrides. `DC_DATA_DIR` expands `~`; the individual path overrides do not expand it themselves. `DC_DB`, `DC_OUTBOX`, and `DC_BLOBS` take precedence over the base directory. Every private runtime path must resolve outside `DC_ROOT`; startup rejects paths or symlinks that resolve inside it. If you ran an earlier version, stop it and move `api/dogcare.db` together with any `-wal`/`-shm` files, `.dev-outbox/`, and `api/blobs/` into the configured private locations before using either launcher. API startup refuses legacy private locations still present in the document root; the generic static server has no such check.

The root `.private/` Git ignore rule does not change this storage boundary or prevent static serving of files inside that directory.

The default launcher binds to loopback HTTP. The `dc_s` session cookie is HttpOnly, SameSite=Lax, and scoped to `/`. `DC_INSECURE_COOKIE=0` is available for an HTTPS reverse proxy; the stdlib listener itself still serves HTTP. Magic-link hosts come from the request's `Host` header. Static mode never injects the API flag; leave it unset when serving with `python3 -m http.server`.

### Saving and recovery

Account mode loads server state before enabling navigation and capture; a failed load shows **Reload account** (**Recharger le compte** in French) and does not fall back to browser/demo history. Loading and recovery initially appear in French. On the recovery screen, the language picker translates the heading, explanation and reload button into French, English, Italian, German or Spanish. This selection lasts only until reload and writes neither account preferences nor browser settings. Once account loading succeeds, the saved account language applies.

If you are not signed in, open your existing sign-in link in this browser profile. If it has expired or was already used, request a replacement from the person who gave you access; for local development, repeat `POST /api/auth/request` as above. Connection failures, failed browser imports and paused recording imports instead show their own translated reload guidance.

Account saves complete before the app clears a draft or reports success. While saving, navigation and other controls are disabled. Each adapter API request has a 15-second deadline, including reading the response; a timeout restores interaction and keeps the draft available to edit, copy, or retry. Failed writes show an error in the form or a toast. If another tab changes accounts or saves newer care data, the stale tab cannot overwrite it: copy any unsaved draft, reload, then reapply it to the current records. Tabs do not automatically refresh each other's changes. A lost response may follow a committed write, so check the reloaded state before reapplying a draft.

Empty account history remains empty on reload. **Reset demo observations** also writes to the server in account mode: it refreshes exact sample entries and restores missing samples without replacing saved notes or their attachments. A saved note with a sample's ID takes precedence. Dogs, daily records, documents, experiences, accounting records and originals, invites and language are retained. Reset does not reopen import eligibility or delete uploaded audio files. Slice 1 has no blob cleanup or account-deletion endpoint; removing an attachment from a snapshot does not remove its stored file.

When loading older account history, unsupported recording references are omitted while care text and supported account recordings are retained, so later notes can still be saved.

## Slice 1 API

The local API uses JSON objects and a `dc_s` session cookie. JSON responses, protected recordings and documents use `Cache-Control: no-store`. All POST/PUT requests require `Content-Type: application/json`. If an `Origin` header is present it must match the server's scheme and `Host`; CLI requests without `Origin` remain supported. Request bodies are capped at 32 MiB, measured in bytes, including UTF-8 text and base64 overhead.

| Method and path | Request / result |
| --- | --- |
| `GET /api/health` | Public health check: `{ "ok": true, "ts": <Unix seconds> }`. |
| `POST /api/auth/request` | `{ "email": "you@example.com" }`; trims/lowercases the email and writes an outbox letter. Returns `{ "ok": true, "mailed": false }`. |
| `GET /api/auth/verify?t=<token>` | Consumes a magic link, sets the session cookie, and redirects to `/?signin=ok`; invalid/expired links redirect with `signin=bad` or `signin=expired`. |
| `GET /api/auth/me` | Returns `{ "ok": true, "email": "…", "role": "owner" }` when signed in, otherwise `{ "ok": false }` with HTTP 200. |
| `POST /api/auth/logout` | Send `{}` and the business header below; deletes the current session and clears its cookie. No revision required. |
| `GET /api/state` | Full snapshot: `ok`, `business_id`, `imported`, `revision`, `email`, `role`, `language`, `dogs`, `observations`, `invites`, `daily`, `knowledge`, `finance`. |
| `PUT /api/daily` | `{ "daily": <snapshot> }`; replaces the full operational snapshot, preserving uploaded document identities. Returns full account state; see the [daily contract](docs/daily-workflows.md#api-contract). |
| `PUT /api/knowledge` | `{ "knowledge": <snapshot> }`; replaces all private experience drafts. Returns full account state; see the [experience contract](docs/maison-sante.md#api-contract). |
| `PUT /api/finance` | `{ "finance": <snapshot>, "uploads": [] }`; saves the full accounting snapshot and any new originals atomically. Returns full account state; see the [accounting contract](docs/comptabilite.md#api-contract). |
| `GET /api/finance-documents/<sha256>` | Business-scoped private accounting original; session required. |
| `POST /api/documents` | Dog, label, renewal (`""` when unset), filename, supported MIME type and base64 file; returns full state. See [daily contract](docs/daily-workflows.md#api-contract). |
| `GET /api/documents/<id>` | Business-scoped private document attachment; session required. |
| `GET /api/dogs` | `{ "ok": true, "dogs": [{ "id": 1, "slug": "billie", "name": "Billie Blue" }, …] }`. |
| `GET /api/dogs/<id>` | `{ "ok": true, "dog": { "id": …, "slug": "…", "name": "…" } }`; numeric ID, scoped to the signed-in business. |
| `POST /api/dogs` | `{ "slug": "new-dog", "name": "New Dog" }`; creates a care-note dog and returns `ok`, `business_id`, `revision`, and `dog`. Slugs are trimmed but preserve case; see identifier rules below. Name is optional, defaults to the slug, and is trimmed to 80 characters. This does not register a daily client/dog relationship. |
| `GET /api/observations` | `{ "ok": true, "observations": { "billie": […], "charlie": […] } }`. |
| `PUT /api/observations` | `{ "observations": { "billie": […], "charlie": […] } }`; replaces all observations for the business. |
| `GET /api/invites` | `{ "ok": true, "invites": […] }`. |
| `PUT /api/invites` | `{ "invites": […] }`; replaces all pending invite previews for the business. |
| `PUT /api/prefs` | `{ "language": "fr" }`; saves the signed-in user's language. Read preferences through `/api/state`. |
| `POST /api/import` | Any nonempty selection of `observations`, `invites`, and `language`; applies supplied collections once, atomically. Returns the full state plus `skipped`. |
| `POST /api/blobs` | `{ "type": "audio/webm", "data": "<base64 bytes, without data-URL prefix>" }`; returns `{ "ok": true, "ref": "<filename>" }`. No revision required. |
| `GET /api/blobs/<ref>` | Returns the current business's recording bytes; another business's file is not accessible. |

Except for health and the request/verify/me auth routes, these endpoints require a valid session. Invite roles and permissions are preview data only: there is no invite acceptance or membership-granting endpoint. Dogs registered directly in **Dogs / Chiens** or through Planning join the daily registry via `PUT /api/daily` and become available to the care-note UI. They appear in `daily.dogs` within `/api/state`; registration alone does not create a `/api/dogs` row. Billie and Charlie remain the initial profiles.

### Mutation contract

First read `/api/state` with your session cookie. Include `X-DogCare-Business: <business_id>` on every authenticated POST/PUT, including uploads and logout. Care writes also require `If-Match: "<revision>"` from that state; the quotation marks are required. Each successful observation, invite, language, dog, daily-record, document, experience, accounting, or first-import write increments the business revision and closes import eligibility. Use the returned revision for the next care write. Audio uploads and logout do neither; document uploads use the guarded revision contract, including originals submitted with an accounting snapshot. A repeat `/api/import` still validates the payload and business binding, but returns the current state with `skipped: true` without checking or advancing the revision.

Observation/invite PUTs are **full replacements, not appends or per-dog updates**. Preserve all records you want to keep in the submitted snapshot. Omitting a dog removes its observations, but keeps the dog row; unknown valid slugs create dogs. `{ "observations": {} }` clears all observations, and `{ "invites": [] }` clears all invites. Import leaves absent top-level collections unchanged. Validation or database-constraint failures roll back the whole care write, including its revision. Successful care PUTs return the full state, read in the same transaction as the write. Language belongs to a user, even though changing it advances the business revision.

The browser adapter in [api.js](api.js) loads these records before [app.js](app.js) renders them. `DogCareAPI.ready` resolves to a boolean; `false` means reload/sign-in/import recovery is needed before saving. The getters read its in-memory cache; `getDogs()`, `getDaily()`, `getKnowledge()` and `getFinance()` return copies. `saveObservations`, `saveInvites`, `saveLanguage`, `saveDaily`, `saveDocument`, `saveKnowledge` and `saveFinance(finance, uploads=[])` serialize writes and resolve to success booleans; `whenSaved()` waits for writes already queued. `getDocument(id)` fetches the private file with the session cookie and resolves to a `Blob`, or `null` when unavailable; it accepts server-issued 32-character lowercase hexadecimal IDs. `getFinanceDocument(id)` does the same for a 64-character lowercase SHA-256 ID. `reloadFinance()` retries loading only the finance cache, returning `false` if the business or shared revision has changed; it does not resolve a stale-account conflict. Account saves do not mirror data back into localStorage or the static accounting IndexedDB database.

### Care payloads and recording references

- `observations` maps dog identifiers to ordered arrays of objects. Daily records and care notes share case-sensitive identifiers of 1–81 ASCII letters, digits, underscores or hyphens, beginning with a letter or digit. Existing identifiers keep their spelling. Observation fields are `id` (optional signed 64-bit integer), `text`, `title`, `time`, `date` (strings), `tags` (array of strings), and optional `audio`. Missing text fields read back as empty strings; missing tags become `[]`. Array order is retained, not sorted by the display date/time.
- `audio` has a required `url`, optional string `type`, and optional finite `duration` in seconds from 0 to 86400. Upload inline audio first, then construct `/api/blobs/<ref>` using the returned `ref` filename. References have 32 lowercase hexadecimal characters and a `webm`, `ogg`, `m4a`, `wav`, or `mp3` extension. External URLs, inline recordings, and query strings are rejected in care writes. Validation checks the URL shape; it does not check that the file exists. Reads remain scoped to the current business.
- `invites` is an ordered array with string `email`, `name`, `role`, `status`, optional `token`, and `permissions` (array of strings; `areas` is also accepted on write). Missing role/status default to `owner`/`pending`, and missing tokens are generated. Tokens must be unique across the database. Replacements assign new server IDs; client `id`/`created` values are not retained, and reads show `created: "Today"`.
- `language` is a string of 1–8 characters. The UI offers `en`, `fr`, `it`, `de`, and `es`; the API does not enforce that list.

Audio uploads use strict base64 and count toward the JSON body limit, so the maximum raw recording is smaller than 32 MiB. The `type` hint selects the file extension (`ogg`, `m4a` for MP4, `wav`, `mp3` for MPEG, otherwise `webm`); the server does not transcode or inspect the audio. Identical bytes with the same extension reuse a file within the business, including concurrent/retried uploads. Files are separate across businesses. Uploads happen before snapshot writes and are not rolled back if the subsequent save fails.

### Errors

API errors generally return `{ "ok": false, "error": "…" }`. Invalid JSON or care/daily/document/experience/accounting fields return 400; missing/expired sessions return 401; cross-origin writes return 403; unknown or other-business dogs/recordings/documents return 404; conflicting data or stale business/revision headers return 409; oversized bodies return 413; a non-JSON content type returns 415; and missing business/revision headers return 428. Daily-record, document, experience or accounting database failures return 500 and roll back that write. Invalid accounting transitions, duplicate invoice numbers and original-file mismatches return 400; see the [accounting contract](docs/comptabilite.md#api-contract). Business/revision precondition failures also include `reload_required: true`. Copy the draft, reload current state, and reconcile it before another write. The adapter blocks further writes after that signal or an authenticated write's 401. Other write failures leave the draft available for retry.

## Navigate the workspace

The shell keeps one compact **Le Bus des Toutous** brand and the dashboard greeting **Bonjour, Adine-Sophie.** All 12 destinations have labelled buttons in persistent navigation; there is no hamburger or **All sections / Tout l’espace** menu to open.

| Group | Destinations (English labels) |
| --- | --- |
| Today | Home (dashboard), Schedule, Dogs, Capture, Handoff, Care & wellbeing (Maison de la Santé in French), Muse assistant, Daily story |
| Share & organise | Gallery, Invite, Accounting (Comptabilité in French), Settings |

Above 700px, the groups appear in a slim sidebar that can scroll vertically in short windows. At 700px and below, the same buttons form two rows beneath the brand bar. Scroll this strip sideways to reach later destinations, including Invite and Settings; the page itself stays within the viewport. The navigation remains available while scrolling content.

Buttons have at least 44px targets, visible keyboard focus, and an active state exposed as `aria-current="page"`. Use Tab to reach a destination and Enter or Space to activate it. Selecting a destination returns the page to its heading and reveals the selected button within the navigation's own scroll container. Handoff evidence links still open the source note in the dog's timeline.

Navigation is shared by static and account modes and supports French, English, Italian, German, and Spanish. The language picker and capture shortcut remain beside the page heading. See the [compact-navigation review](docs/review/muse-compact-navigation/README.md) for before/after images and regression coverage.

## Comptabilité

Invoices, expense claims, billed extras, local receipt recognition and accountant export are available under **Accounting** (**Comptabilité** in French). Planned monthly booking totals and base rates remain in its **Bookings & rates / Réservations et tarifs** tab, also reached directly from home/planning shortcuts. See [Comptabilité](docs/comptabilite.md) for review, payments, print/PDF, original documents, workbook export and storage boundaries. OCR/PDF/ZIP libraries are bundled locally and loaded only for intake/export; no install or external document service is required.

## Maison de la Santé

Sourced everyday-care guides, labelled provider videos and saved private experience drafts are directly accessible from the workspace navigation. See [Maison de la Santé](docs/maison-sante.md) for the content, storage, compatibility and verification boundaries. Existing records and sessions are preserved; no experience is published or clinically approved by saving it.

## Try the core flow

1. Open **Muse assistant** and ask for today’s briefing, recorded items needing attention, or an owner handoff. Muse answers from deterministic information already held in the browser; it is not connected to a remote AI service.
2. Use a quick action or open **Capture update** from the dashboard or navigation.
3. Choose a dog and type a note, or use **Dictate** to see a voice note transcribed live into the care-note field.
4. Edit the text if needed, review the detected tags, and save the observation.
5. The new structured card appears in the dog's timeline and the owner story preview updates immediately.
6. Open **Handoff** to review a care-continuity summary for either the owner or next carer, follow its evidence links back to today's observations, and check the suggested next-care actions.

Health-watch content is deliberately phrased as factual observation rather than diagnosis. The handoff reminds carers to keep observing and contact the owner or a veterinarian when concerned.

Capture keeps a separate unsaved draft for each dog while the tab remains open. Switching dogs, language, or views preserves each draft; a successful save clears only that dog's draft. Save before reloading or closing the tab: drafts are not persisted, and the browser warns when leaving with unsaved work. If browser storage fails, capture remains editable and displays a persistent failure message; retrying after storage is available saves the note once.

New observations store their local calendar date as `YYYY-MM-DD`. Today's handoff uses that day, while older observations stay in the timeline. Existing app-created records that stored the literal `Today` are dated using their epoch-millisecond ID when read, without rewriting stored history. Low-numbered demo records retain their illustrative Today/Yesterday labels.

## Try the invite preview flow

1. Open **Invite** (**Inviter** in French) from the sidebar or, on phones, scroll the two-row navigation strip sideways to it.
2. Choose **Owner** or **Trusted carer**, add a demo name and email, and select share areas.
3. Review the invite-ready summary and create a **pending invite preview**.
4. The pending invite is saved in this browser in static mode or in the business account in account mode. No email, WhatsApp, SMS, or notification is sent, and no account access is granted.

## Try dictation, retained recordings, and sharing

1. Open **Capture update**, add written care context, then choose **Dictate**. Microphone permission is requested only at that point.
2. Choose **Stop**, edit the transcript, and save the care update. The current **Dictate** control transcribes text only; it does not create a new audio attachment. The separate recording helper in `app.js` is not wired to that control.
3. Existing supported audio attachments remain playable on the dog's timeline and in **Gallery**. Static mode reads inline audio from browser storage; account mode uploads imported recordings to the business's server store and plays them through authenticated URLs.
4. In **Gallery**, preview the clearly labelled Instagram, Facebook, and YouTube access states. These controls do not ask for credentials, connect accounts, make network requests, or post content.

Browsers without speech recognition, `file://` pages, and denied speech permission receive an inline explanation; typed care capture remains available. Open the app through the local HTTP launcher for dictation.

Timeline and story **Share** controls can open the device share sheet and attach supported audio when file sharing is available. In account mode, fetching that audio requires the current session; an expired/switched session shows a sharing error instead of sharing the unavailable recording. Fallback controls open WhatsApp, Telegram, or Facebook, or copy text for Instagram. These are user-initiated sharing actions; they are separate from the Gallery's connection previews and do not provide automatic owner delivery.

## Product boundaries

This is a local interactive prototype using fictional demo care moments around the named pilot profiles. Muse and AI structuring use deterministic, on-device keyword parsing; neither connects to a remote AI service. Assistant questions stay in the browser.

- **Static mode** (`python3 -m http.server`, no `DOGCARE_API`): care records and retained recordings are saved in this browser, with no API upload.
- **Account mode** (`python3 api/server.py`, flag on): care records and recordings are stored in the business’s own account store on the server the business runs. API access is restricted to signed-in members of that business. The one-time recording import shows a notice before moving existing audio.

Invitation creation remains a pending preview with no delivery. The magic-link mailer writes local `.dev-outbox` files only. Social connections, automatic owner delivery and cloud sync remain previews or unavailable; social connection previews never collect credentials or post to a network. Explicit sharing can pass selected care content to the app you choose. Accounting can issue and print invoices and record manually entered payments/reimbursements, but does not send invoices, execute payments, reconcile a bank account or file taxes. Payment processing and subscriptions remain unimplemented. Operational rates are user supplied; this change adds no deployment, credentials or third-party email provider.

Voice transcription uses the browser's built-in speech-recognition feature. Depending on the browser, microphone audio may be processed by the browser provider's speech service; users should check their browser's privacy terms before dictating.

## Public-site research crawler

An optional Crawl4AI tool can turn an allowed public website into a local Markdown/JSON research corpus. It blocks cross-origin navigation, reads `robots.txt`, uses sitemap URLs, and limits requests, discovery-file size, page duration, and retained content by default. Output paths inside the repository require an explicit override; keep generated corpora external unless they are intentionally reviewed and licensed for inclusion.

```bash
python3.12 -m venv /tmp/dogcare-crawler
/tmp/dogcare-crawler/bin/pip install -r requirements-crawler.txt
/tmp/dogcare-crawler/bin/crawl4ai-setup
/tmp/dogcare-crawler/bin/python tools/crawl_site.py https://www.rintintin-pro.com/ \
  --output /tmp/rintintin-pro-corpus --max-pages 12
```

## Acceptance checks

Run the API regressions with the standard library and the adapter regressions with Node:

```bash
python3 -m unittest tests.test_api_server tests.test_tenant_isolation tests.test_daily_api tests.test_knowledge_api tests.test_finance_api tests.test_crawl_site -v
node --test tests/test_api_adapter.js tests/test_daily_model.js tests/test_finance_model.js tests/test_finance_documents.js tests/test_finance_export.js
for file in app.js api.js daily-*.js knowledge-*.js finance-*.js; do node --check "$file" || exit 1; done
```

The browser acceptance checks need the optional Playwright dependency and its matching Chromium binary; Crawl4AI is not required. Using `uv` and the Playwright version in `requirements-crawler.txt`:

```bash
uv run --python 3.12 --with playwright==1.61.0 python -m playwright install chromium
uv run --python 3.12 --with playwright==1.61.0 python -m unittest discover -s tests -v
```

The suite starts its own local servers and temporary account storage. It covers both static and account modes, authentication, tenant isolation, safe migration and replacement writes, stale-tab/timeout recovery, protected recordings, robots/origin/output boundaries, the Muse briefing-to-handoff journey, dictated text editing, and mobile overflow. Daily-workflow checks cover booking create/reload/edit, original-rate extensions, cross-month allocation, unknown rates, private document download and renewal follow-up, and failed-save recovery in both storage modes.

Dog-registration checks cover the selected profile and empty directory, optional owners, distinct IDs for same-named dogs, duplicate-submit prevention, cancel, failed-save/retry, literal drafts across navigation and five locales, save/reload and later booking association. They also cover keyboard focus, 44px controls and overflow at phone, tablet and desktop sizes; API/model checks cover ownerless records and business/revision guards.

Knowledge checks cover guide search and provider links, topic choices, five locales, private experience save/edit/reload, literal text and Unicode limits, failed-save drafts, and conflicting tabs in both storage modes. API checks cover business isolation, stale/switched-account rejection and atomic validation. External video navigation is intercepted in the fixture; remote playback and live source verification are separate from these tests.

Accounting checks cover invoice/extra/payment save/reload, local receipt OCR and PDF/manual intake, immutable originals, duplicate rejection, ZIP/XLSX contents, literal cells, failed-save recovery and stale-tab protection in both storage modes. See [accounting checks](docs/comptabilite.md#local-readers-and-checks) for focused commands; the full Python discovery command above includes the finance browser suite.

Navigation checks cover all 12 destinations and five locales at 1440 × 900, 1024 × 768, and 390 × 844, keyboard activation, active state, 44px targets, a single business brand, and heading visibility after switching from scrolled content. Separate checks verify active-button reveal within the phone strip and a short desktop sidebar.

Account recovery checks cover French initial copy, all five recovery languages, no account or browser-setting writes when switching languages, and no fallback to demo history. They also check overflow and the reload button's 44px target at the three viewports above.

Speech recognition is simulated; these tests do not verify a real microphone or browser-provider transcription service. Browser tests skip with an installation hint if the Playwright Python package is absent; if the package is installed but Chromium is missing, browser launch fails until the install step above completes. Pure API/crawler tests always run with the standard library, and the Node adapter tests run separately.

Set `DOGCARE_EVIDENCE_DIR` to an allowed evidence directory to retain the browser suite's selected screenshots and migration-state JSON; when unset it does not write those evidence files. Browser checks await `#app-content[data-ready="true"]` and rendered content, since adapter hydration alone does not establish that the UI is ready.
