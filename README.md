# DogCare Brain

A polished, dependency-free MVP for a small dog-care business. This premium **Muse** edition is branded for Adine-Sophie and Le Bus des Toutous. It follows Billie Blue and Charlie Rose from daily care capture through owner updates, scheduling, media, and lightweight business reporting.

## Run locally

From this directory, start any static file server:

```bash
python3 -m http.server 4173
```

Then open [http://localhost:4173](http://localhost:4173).

No install or build step is required. Static mode stores observations, pending invite previews, and language in the browser's `localStorage` (`dogcare-observations`, `dogcare-invites`, and `dogcare-language`). **Reset demo observations** in Settings replaces only the observations with the original demo data; invites and language are retained.

Slice 1 (accounts, SQLite, still zero pip deps) — local only, no email keys:

```bash
python3 api/server.py          # http://127.0.0.1:8787  (sets window.DOGCARE_API)
# In another terminal while the server is running:
curl -X POST http://127.0.0.1:8787/api/auth/request \
  -H 'Content-Type: application/json' -d '{"email":"you@example.com"}'
# Open the link in ~/.local/share/dogcare-brain/.dev-outbox/*.json
```

Open the `link` value from the newest outbox JSON for your email in your browser. Links are single-use and expire after 15 minutes; request another if needed. First verification creates a separate business for each new email, an owner account, and the Billie/Charlie demo dogs and observations. The business name comes from the email's local part; the interface retains the pilot branding and profiles. Later sign-ins with the same email return to that business. Sessions last 90 days. There is no sign-in form or sign-out control yet; use the auth endpoints below. Opening account mode without a valid session shows a sign-in/reload message and keeps care capture disabled.

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

Account mode imports whichever of the three browser keys exist, once per unused business. Missing keys leave the corresponding account data unchanged; explicitly empty observations or invites clear those collections. A language-only import also consumes this opportunity. The server's `imported` flag means import eligibility is closed, whether by import or by a successful observation, invite, language, or dog write. Uploading audio alone does not close it. A browser marker (`dogcare-imported:<business_id>`) also prevents repeat automatic imports; the server flag protects the account across browser profiles. With no browser keys, the new account keeps its demo data and remains eligible until a care write.

A notice appears before existing inline recordings transfer. Cancel leaves browser data intact and account loading paused; reload to continue. Failed imports remain retryable and keep capture disabled until account loading succeeds. Startup also closes import eligibility for older accounts with non-demo history, invites, recordings, or a non-English preference. Audio is uploaded separately before the snapshot. Local browser copies are retained and are not updated by later account saves; switching back to static mode displays those older browser copies.

### Account configuration and storage

All configuration is through environment variables read by `api/server.py`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DC_HOST` | `127.0.0.1` | HTTP bind address. |
| `DC_PORT` | `8787` | HTTP listen port. |
| `DC_ROOT` | Repository root | Static document root; the API server injects `window.DOGCARE_API="/api"` into HTML. |
| `DC_DATA_DIR` | `~/.local/share/dogcare-brain` | Base directory for private runtime files. |
| `DC_DB` | `<DC_DATA_DIR>/dogcare.db` | SQLite database, using WAL mode. |
| `DC_OUTBOX` | `<DC_DATA_DIR>/.dev-outbox` | Local magic-link JSON files. |
| `DC_BLOBS` | `<DC_DATA_DIR>/blobs` | Audio files, under a directory per business ID. |
| `DC_INSECURE_COOKIE` | `1` | `1` uses HTTP magic links and omits `Secure` on the cookie; any other value uses HTTPS links and a `Secure` cookie. |

Use absolute paths for overrides. `DC_DATA_DIR` expands `~`; the individual path overrides do not expand it themselves. `DC_DB`, `DC_OUTBOX`, and `DC_BLOBS` take precedence over the base directory. Every private runtime path must resolve outside `DC_ROOT`; startup rejects paths or symlinks that resolve inside it. If you ran an earlier version, stop it and move `api/dogcare.db` together with any `-wal`/`-shm` files, `.dev-outbox/`, and `api/blobs/` into the configured private locations before using either launcher. API startup refuses legacy private locations still present in the document root; the generic static server has no such check.

The default launcher binds to loopback HTTP. The `dc_s` session cookie is HttpOnly, SameSite=Lax, and scoped to `/`. `DC_INSECURE_COOKIE=0` is available for an HTTPS reverse proxy; the stdlib listener itself still serves HTTP. Magic-link hosts come from the request's `Host` header. Static mode never injects the API flag; leave it unset when serving with `python3 -m http.server`.

### Saving and recovery

Account mode loads server state before enabling navigation and capture; a failed load shows **Reload account** and does not fall back to browser/demo history. Account saves complete before the app clears a draft or reports success. While saving, navigation and other controls are disabled. Each adapter API request has a 15-second deadline, including reading the response; a timeout restores interaction and keeps the draft available to edit, copy, or retry. Failed writes show a toast. If another tab changes accounts or saves newer care data, the stale tab cannot overwrite it: copy any unsaved draft, reload, then reapply it to the current records. Tabs do not automatically refresh each other's changes. A lost response may follow a committed write, so check the reloaded state before reapplying a draft.

Empty account history remains empty on reload. **Reset demo observations** also writes to the server in account mode: it replaces the business's entire observation history with demo observations, while retaining dogs, invites, and language. Reset does not reopen import eligibility or delete uploaded audio files. Slice 1 has no blob cleanup or account-deletion endpoint; removing an attachment from a snapshot does not remove its stored file.

When loading older account history, unsupported recording references are omitted while care text and supported account recordings are retained, so later notes can still be saved.

## Slice 1 API

The local API uses JSON objects and a `dc_s` session cookie. JSON responses and protected recordings use `Cache-Control: no-store`. All POST/PUT requests require `Content-Type: application/json`. If an `Origin` header is present it must match the server's scheme and `Host`; CLI requests without `Origin` remain supported. Request bodies are capped at 32 MiB, measured in bytes, including UTF-8 text and base64 overhead.

| Method and path | Request / result |
| --- | --- |
| `GET /api/health` | Public health check: `{ "ok": true, "ts": <Unix seconds> }`. |
| `POST /api/auth/request` | `{ "email": "you@example.com" }`; trims/lowercases the email and writes an outbox letter. Returns `{ "ok": true, "mailed": false }`. |
| `GET /api/auth/verify?t=<token>` | Consumes a magic link, sets the session cookie, and redirects to `/?signin=ok`; invalid/expired links redirect with `signin=bad` or `signin=expired`. |
| `GET /api/auth/me` | Returns `{ "ok": true, "email": "…", "role": "owner" }` when signed in, otherwise `{ "ok": false }` with HTTP 200. |
| `POST /api/auth/logout` | Send `{}` and the business header below; deletes the current session and clears its cookie. No revision required. |
| `GET /api/state` | Full snapshot: `ok`, `business_id`, `imported`, `revision`, `email`, `role`, `language`, `dogs`, `observations`, `invites`. |
| `GET /api/dogs` | `{ "ok": true, "dogs": [{ "id": 1, "slug": "billie", "name": "Billie Blue" }, …] }`. |
| `GET /api/dogs/<id>` | `{ "ok": true, "dog": { "id": …, "slug": "…", "name": "…" } }`; numeric ID, scoped to the signed-in business. |
| `POST /api/dogs` | `{ "slug": "new-dog", "name": "New Dog" }`; creates a dog and returns `ok`, `business_id`, `revision`, and `dog`. Name is optional, defaults to the slug, and is trimmed to 80 characters. |
| `GET /api/observations` | `{ "ok": true, "observations": { "billie": […], "charlie": […] } }`. |
| `PUT /api/observations` | `{ "observations": { "billie": […], "charlie": […] } }`; replaces all observations for the business. |
| `GET /api/invites` | `{ "ok": true, "invites": […] }`. |
| `PUT /api/invites` | `{ "invites": […] }`; replaces all pending invite previews for the business. |
| `PUT /api/prefs` | `{ "language": "fr" }`; saves the signed-in user's language. Read preferences through `/api/state`. |
| `POST /api/import` | Any nonempty selection of `observations`, `invites`, and `language`; applies supplied collections once, atomically. Returns the full state plus `skipped`. |
| `POST /api/blobs` | `{ "type": "audio/webm", "data": "<base64 bytes, without data-URL prefix>" }`; returns `{ "ok": true, "ref": "<filename>" }`. No revision required. |
| `GET /api/blobs/<ref>` | Returns the current business's recording bytes; another business's file is not accessible. |

Except for health and the request/verify/me auth routes, these endpoints require a valid session. Invite roles and permissions are preview data only: there is no invite acceptance or membership-granting endpoint. The API can store additional dogs, but the slice-1 UI still uses the fixed Billie/Charlie profiles.

### Mutation contract

First read `/api/state` with your session cookie. Include `X-DogCare-Business: <business_id>` on every authenticated POST/PUT, including uploads and logout. Care writes also require `If-Match: "<revision>"` from that state; the quotation marks are required. Each successful observation, invite, language, dog, or first-import write increments the business revision and closes import eligibility. Use the returned revision for the next care write. Uploads and logout do neither. A repeat `/api/import` still validates the payload and business binding, but returns the current state with `skipped: true` without checking or advancing the revision.

Observation/invite PUTs are **full replacements, not appends or per-dog updates**. Preserve all records you want to keep in the submitted snapshot. Omitting a dog removes its observations, but keeps the dog row; unknown valid slugs create dogs. `{ "observations": {} }` clears all observations, and `{ "invites": [] }` clears all invites. Import leaves absent top-level collections unchanged. Validation or database-constraint failures roll back the whole care write, including its revision. Successful care PUTs return the full state, read in the same transaction as the write. Language belongs to a user, even though changing it advances the business revision.

The browser adapter in [api.js](api.js) loads these records before [app.js](app.js) renders them. `DogCareAPI.ready` resolves to a boolean; `false` means reload/sign-in/import recovery is needed before saving. The getters read its in-memory cache. `saveObservations`, `saveInvites`, and `saveLanguage` serialize writes and resolve to success booleans; `whenSaved()` waits for writes already queued. Account saves do not mirror data back into the three browser keys.

### Care payloads and recording references

- `observations` maps dog slugs to ordered arrays of objects. Slugs use 1–81 lowercase letters, digits, or hyphens, beginning with a letter or digit. Observation fields are `id` (optional signed 64-bit integer), `text`, `title`, `time`, `date` (strings), `tags` (array of strings), and optional `audio`. Missing text fields read back as empty strings; missing tags become `[]`. Array order is retained, not sorted by the display date/time.
- `audio` has a required `url`, optional string `type`, and optional finite `duration` in seconds from 0 to 86400. Upload inline audio first, then construct `/api/blobs/<ref>` using the returned `ref` filename. References have 32 lowercase hexadecimal characters and a `webm`, `ogg`, `m4a`, `wav`, or `mp3` extension. External URLs, inline recordings, and query strings are rejected in care writes. Validation checks the URL shape; it does not check that the file exists. Reads remain scoped to the current business.
- `invites` is an ordered array with string `email`, `name`, `role`, `status`, optional `token`, and `permissions` (array of strings; `areas` is also accepted on write). Missing role/status default to `owner`/`pending`, and missing tokens are generated. Tokens must be unique across the database. Replacements assign new server IDs; client `id`/`created` values are not retained, and reads show `created: "Today"`.
- `language` is a string of 1–8 characters. The UI offers `en`, `fr`, `it`, `de`, and `es`; the API does not enforce that list.

Audio uploads use strict base64 and count toward the JSON body limit, so the maximum raw recording is smaller than 32 MiB. The `type` hint selects the file extension (`ogg`, `m4a` for MP4, `wav`, `mp3` for MPEG, otherwise `webm`); the server does not transcode or inspect the audio. Identical bytes with the same extension reuse a file within the business, including concurrent/retried uploads. Files are separate across businesses. Uploads happen before snapshot writes and are not rolled back if the subsequent save fails.

### Errors

API errors generally return `{ "ok": false, "error": "…" }`. Invalid JSON or care fields return 400; missing/expired sessions return 401; cross-origin writes return 403; unknown or other-business dogs/recordings return 404; conflicting data or stale business/revision headers return 409; oversized bodies return 413; a non-JSON content type returns 415; and missing business/revision headers return 428. Business/revision precondition failures also include `reload_required: true`. Copy the draft, reload current state, and reconcile it before another write. The adapter blocks further writes after that signal or an authenticated write's 401. Other write failures leave the draft available for retry.

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

1. Open **Invite** from the sidebar or top bar.
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

Invitation creation remains a pending preview with no delivery. The magic-link mailer writes local `.dev-outbox` files only. Social connections, automatic owner delivery, payments, and cloud sync remain previews or drafts; social connection previews never collect credentials or post to a network. Explicit sharing can pass selected care content to the app you choose. Slice 2 remains closed: no deployment, keys, prices, or third-party email provider.

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
python3 -m unittest tests.test_api_server tests.test_tenant_isolation tests.test_crawl_site -v
node --test tests/test_api_adapter.js
```

The browser acceptance checks need the optional Playwright dependency and its matching Chromium binary; Crawl4AI is not required. Using `uv` and the Playwright version in `requirements-crawler.txt`:

```bash
uv run --python 3.12 --with playwright==1.61.0 python -m playwright install chromium
uv run --python 3.12 --with playwright==1.61.0 python -m unittest discover -s tests -v
```

The suite starts its own local servers and temporary account storage. It covers both static and account modes, authentication, tenant isolation, safe migration and replacement writes, stale-tab/timeout recovery, protected recordings, robots/origin/output boundaries, the Muse briefing-to-handoff journey, dictated text editing, and mobile overflow. Speech recognition is simulated; these tests do not verify a real microphone or browser-provider transcription service. Browser tests skip with an installation hint if the Playwright Python package is absent; if the package is installed but Chromium is missing, browser launch fails until the install step above completes. Pure API/crawler tests always run with the standard library, and the Node adapter tests run separately.

Set `DOGCARE_EVIDENCE_DIR` to an allowed evidence directory to retain the browser suite's selected screenshots and migration-state JSON; when unset it does not write those evidence files. Browser checks await `#app-content[data-ready="true"]` and rendered content, since adapter hydration alone does not establish that the UI is ready.
