# DogCare Brain

A polished, build-free MVP for a small dog-care business. This premium **Muse** edition is branded for Adine-Sophie and Le Bus des Toutous. It provides a public service welcome, a private client space, [selected read-only professional access](docs/client-portal.md#selected-professional-access) and a complete dog-sitter workspace. The static demo retains Billie Blue and Charlie Rose. See [client access, requests, pricing and login delivery](docs/client-portal.md).

## Run locally

From this directory, start any static file server:

```bash
python3 -m http.server 4173
```

Then open [http://localhost:4173](http://localhost:4173).

No install or build step is required. The four operational workflows—bookings, base rates/stay extensions, dog documents/follow-up and monthly summaries—are described in [Daily workflows](docs/daily-workflows.md). They persist in this browser in static mode and in the private SQLite database in account mode.

To [register a dog](docs/daily-workflows.md#registering-a-dog) without a booking or care note, open **Dogs / Chiens → ＋ Add a dog / Ajouter un chien**. Only the dog name is required; the owner can remain unknown. **All dogs / Tous les chiens** opens the saved profiles.

Static mode stores observations, pending invite previews, and language in the browser's `localStorage` (`dogcare-observations`, `dogcare-invites`, and `dogcare-language`), with operational records and documents in `dogcare-daily-v1` and [private experience drafts](docs/maison-sante.md) in `dogcare-knowledge-v1`. [Accounting records and originals](docs/comptabilite.md) use a separate IndexedDB database, `dogcare-finance-v1`. Browser quota limits apply; no cloud synchronization is implied. **Reset demo observations** in Settings restores sample observations while retaining saved notes, registered dogs, daily records, experiences, accounting records and originals, invites and language.

Account mode (SQLite, zero pip dependencies) opens on the public welcome. For an isolated local demo:

```bash
preview_data="$(mktemp -d)"
DC_DATA_DIR="$preview_data" DC_AUTH_MODE=development DC_ALLOW_DEMO_SIGNUP=1 python3 api/server.py
# http://127.0.0.1:8787 — explicit local development only
```

Use that same temporary directory for the [preview seeder](docs/client-portal.md#isolated-verification)'s `--data-dir` argument. Create synthetic access with the seeder, or request a demo link through `/api/auth/request` in this explicit development mode and open the newest JSON under `<preview_data>/.dev-outbox`. Without these flags, unknown emails never create owners. Real accounts require explicit owner bootstrap and configured encrypted login delivery; see [transport configuration](docs/client-portal.md#login-transport). No deployment or real email receipt is implied by local tests.

### Import browser records

To import existing static-mode records, stop the static server and start account mode on the **same hostname and port** before saving anything to the business account. For the static URL above:

```bash
DC_AUTH_MODE=development DC_ALLOW_DEMO_SIGNUP=1 DC_HOST=localhost DC_PORT=4173 python3 api/server.py
# In another terminal:
curl -X POST http://localhost:4173/api/auth/request \
  -H 'Content-Type: application/json' -d '{"email":"you@example.com"}'
# Open the outbox link in the same browser profile used for the static app.
```

Use your original scheme, hostname, and port if different. `localhost:4173` and `127.0.0.1:8787` have separate browser storage; the default account URL cannot see records from the static URL. Sign in to an unused business account at the original origin, accept the recording notice if shown, and let the import finish before making account writes. Browser copies stay intact, but an account already used for care writes cannot import them.

Account mode imports whichever of the three browser keys exist, once per unused business. Missing keys leave the corresponding account data unchanged; explicitly empty observations or invites clear those collections. A language-only import also consumes this opportunity. The server's `imported` flag means import eligibility is closed, whether by import or by a successful observation, invite, language, dog, daily-record, document, experience, accounting or portal write, or a media upload. Uploading audio alone does not close it. A browser marker (`dogcare-imported:<business_id>`) also prevents repeat automatic imports; the server flag protects the account across browser profiles. With no browser keys, the account remains eligible until one of those writes. Explicit development demo accounts retain demo data; operator-created real accounts start empty. Only owners can import browser history; clients and professionals receive `imported: true` in their projected state.

**Daily dog names and owner associations, bookings, rates, clients, documents, private experiences and accounting records/originals are not imported by this legacy three-key process.** Imported observations retain their dog identifiers, but do not transfer daily profile details. The excluded records and files remain in their original browser storage; see [daily storage and migration](docs/daily-workflows.md#storage-and-migration), [experience storage](docs/maison-sante.md#storage-and-compatibility) and [accounting storage](docs/comptabilite.md#storage-and-contracts).

A notice appears before existing inline recordings transfer. Cancel leaves browser data intact and account loading paused; reload to continue. Failed imports remain retryable and keep capture disabled until account loading succeeds. Startup also closes import eligibility for older accounts with non-demo history, invites, recordings, or a non-English preference. Audio is uploaded separately before the snapshot. Local browser copies are retained and are not updated by later account saves; switching back to static mode displays those older browser copies.

### Account configuration and storage

Listener and storage configuration uses these environment variables. See [login transport](docs/client-portal.md#login-transport) for authentication/SMTP settings and [public prices](docs/client-portal.md#prices-and-options) for the `DC_PUBLIC_BUSINESS` binding used by rates and artwork.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DC_HOST` | `127.0.0.1` | HTTP bind address. |
| `DC_PORT` | `8787` | HTTP listen port. |
| `DC_TRUSTED_PROXY` | Unset | Only `127.0.0.1` enables the dedicated local proxy's client-IP header for login limits, with a matching loopback bind and peer. See the [deployment trust contract](docs/private-beta-release.md#https-browser-permissions-and-public-verification). Leave unset for direct access. |
| `DC_ROOT` | Repository root | Root for the explicit frontend allowlist; the API server injects `window.DOGCARE_API="/api"` into served HTML. |
| `DC_DATA_DIR` | `~/.local/share/dogcare-brain` | Base directory for private runtime files. |
| `DC_DB` | `<DC_DATA_DIR>/dogcare.db` | SQLite database, including daily records, documents, private experiences, accounting, client access/requests, professional grants/shared versions and media/artwork bytes, using WAL mode. |
| `DC_OUTBOX` | `<DC_DATA_DIR>/.dev-outbox` | Private magic-link JSON files in explicit development mode only. |
| `DC_BLOBS` | `<DC_DATA_DIR>/blobs` | Audio files, under a directory per business ID. |
| `DC_INSECURE_COOKIE` | `1` | `1` uses HTTP development links and omits `Secure` on the cookie; other values use HTTPS development links and a `Secure` cookie. SMTP requires `0` and links use `DC_PUBLIC_ORIGIN`. |

Use absolute paths for overrides. `DC_DATA_DIR` expands `~`; the individual path overrides do not expand it themselves. `DC_DB`, `DC_OUTBOX`, and `DC_BLOBS` take precedence over the base directory. Every private runtime path must resolve outside `DC_ROOT`; startup rejects paths or symlinks that resolve inside it. If you ran an earlier version, stop it and move `api/dogcare.db` together with any `-wal`/`-shm` files, `.dev-outbox/`, and `api/blobs/` into the configured private locations before using either launcher. API startup refuses legacy private locations still present in the document root; the generic static server has no such check.

The root `.private/` Git ignore rule does not change this storage boundary. The API serves only `STATIC_FILES` in `api/server.py`: repository docs, deployment files, tests, scripts, dotfiles and provenance metadata remain unavailable, including aliases and symlinks. Add intended frontend assets deliberately and verify with `tests.test_static_boundary`. The generic static server has no allowlist and can expose private files left beneath its root.

The default launcher binds to loopback HTTP. The `dc_s` session cookie is HttpOnly, SameSite=Lax, and scoped to `/`. `DC_INSECURE_COOKIE=0` is available for an HTTPS reverse proxy; the stdlib listener itself still serves HTTP. Production magic links use the fixed HTTPS `DC_PUBLIC_ORIGIN`; only loopback development links use the request Host. Login delivery is disabled by default; see the [auth transport configuration](docs/client-portal.md#login-transport). Static mode never injects the API flag; leave it unset when serving with `python3 -m http.server`.

### Saving and recovery

Account mode loads server state before enabling navigation and capture; a failed load shows **Reload account** (**Recharger le compte** in French) and does not fall back to browser/demo history. Loading and recovery initially appear in French. On the recovery screen, the language picker translates the heading, explanation and reload button into French, English, Italian, German or Spanish. This selection lasts only until reload and writes neither account preferences nor browser settings. Once account loading succeeds, the saved account language applies.

If you are not signed in, the public welcome provides **Mon espace** and a sign-in form. Expired or already-used links offer a replacement request. The owner must first link a client email to an existing client and their dogs. Connection failures, failed browser imports and paused recording imports instead show their own translated reload guidance.

Care, planning, accounting and portal saves complete before the app clears a draft or reports success. While saving, navigation and other controls are disabled. These adapter requests have a 15-second deadline, including reading the response; a timeout restores interaction and keeps the draft available to edit, copy, or retry. Failed writes show an error in the form or a toast. If another tab changes accounts or saves newer care data, the stale tab cannot overwrite it: copy any unsaved draft, reload, then reapply it to the current records. Tabs do not automatically refresh each other's changes. A lost response may follow a committed write, so check the reloaded state before reapplying a draft. [Media uploads](docs/media.md#stockage-et-api) use a separate 180-second transfer timeout and recovery contract.

Empty account history remains empty on reload. Account Settings has no demo reset; **Reset demo observations** is available only in static mode. It restores sample observations without replacing saved notes or their attachments, including a saved note with a sample's ID. Slice 1 has no audio-blob cleanup or account-deletion endpoint; removing an audio attachment from a snapshot does not remove its stored file. Private photo/video deletion follows the separate [media contract](docs/media.md#stockage-et-api).

When loading older account history, unsupported recording references are omitted while care text and supported account recordings are retained, so later notes can still be saved.

## Slice 1 API

The API uses JSON objects and a `dc_s` session cookie. JSON responses, protected recordings and documents use `Cache-Control: no-store`. POST/PUT requests require `Content-Type: application/json`, except raw binary [media uploads](docs/media.md#stockage-et-api). If an `Origin` header is present it must match the server's scheme and `Host`; CLI requests without `Origin` remain supported. JSON request bodies are capped at 32 MiB, measured in bytes, including UTF-8 text and base64 overhead; media uploads have separate 12 MiB photo and 80 MiB video limits.

| Method and path | Request / result |
| --- | --- |
| `GET /api/health` | Public health check: `{ "ok": true, "ts": <Unix seconds> }`. |
| `POST /api/auth/request` | `{ "email": "you@example.com", "service": "day" }`; signs in known members through the configured transport. Public form uses `/api/auth/access`; see [delivery rules](docs/client-portal.md#login-transport). |
| `GET /api/auth/verify?t=<token>` | Consumes a magic link, sets the session cookie, and redirects to `/?signin=ok`; a valid `service` query is retained. Invalid/expired links redirect with `signin=bad` or `signin=expired`. Sessions last 90 days unless revoked or signed out. |
| `GET /api/auth/me` | Returns `{ "ok": true, "email": "…", "role": "owner" }` when signed in, otherwise `{ "ok": false }` with HTTP 200. |
| `POST /api/auth/logout` | Send `{}` and the business header below; deletes the current session and clears its cookie. No revision required. |
| `GET /api/state` | Full snapshot: `ok`, `business_id`, `imported`, `revision`, `email`, `role`, `language`, `dogs`, `observations`, `invites`, `daily`, `knowledge`, `finance`, `portal`, `media`; contents are projected by role. |
| `PUT /api/daily` | `{ "daily": <snapshot> }`; replaces the full operational snapshot, preserving uploaded document identities. Returns full account state; see the [daily contract](docs/daily-workflows.md#api-contract). |
| `PUT /api/knowledge` | `{ "knowledge": <snapshot> }`; replaces all private experience drafts. Returns full account state; see the [experience contract](docs/maison-sante.md#api-contract). |
| `PUT /api/finance` | `{ "finance": <snapshot>, "uploads": [] }`; saves the full accounting snapshot and any new originals atomically. Returns full account state; see the [accounting contract](docs/comptabilite.md#api-contract). |
| `GET /api/finance-documents/<sha256>` | Business-scoped private accounting original; owner session required. |
| `POST /api/documents` | Dog, label, renewal (`""` when unset), filename, supported MIME type and base64 file; returns full state. See [daily contract](docs/daily-workflows.md#api-contract). |
| `GET /api/documents/<id>` | Business-scoped private document attachment; staff session or an individual professional grant required. |
| `GET /api/dogs` | `{ "ok": true, "dogs": […] }`; staff receive care-dog rows such as `{ "id": 1, "slug": "billie", "name": "Billie Blue" }`. Clients/professionals receive only allowed daily dogs, with both `id` and `slug` set to the daily string identifier. |
| `GET /api/dogs/<id>` | `{ "ok": true, "dog": { "id": …, "slug": "…", "name": "…" } }`; numeric care-dog row ID, scoped to the signed-in business and the client/professional's allowed dogs. Daily string IDs from their list response are not accepted here. |
| `POST /api/dogs` | `{ "slug": "new-dog", "name": "New Dog" }`; creates a care-note dog and returns `ok`, `business_id`, `revision`, and `dog`. Slugs are trimmed but preserve case; see identifier rules below. Name is optional, defaults to the slug, and is trimmed to 80 characters. This does not register a daily client/dog relationship. |
| `GET /api/observations` | `{ "ok": true, "observations": { "billie": […], "charlie": […] } }`. |
| `PUT /api/observations` | `{ "observations": { "billie": […], "charlie": […] } }`; replaces all observations for the business. |
| `GET /api/invites` | `{ "ok": true, "invites": […] }`. |
| `PUT /api/invites` | `{ "invites": […] }`; replaces all pending invite previews for the business. |
| `PUT /api/prefs` | `{ "language": "fr" }`; saves the signed-in user's language. Read preferences through `/api/state`. |
| `POST /api/import` | Any nonempty selection of `observations`, `invites`, and `language`; applies supplied collections once, atomically. Returns the full state plus `skipped`. |
| `POST /api/blobs` | `{ "type": "audio/webm", "data": "<base64 bytes, without data-URL prefix>" }`; returns `{ "ok": true, "ref": "<filename>" }`. No revision required. |
| `GET /api/blobs/<ref>` | Returns the current business's recording bytes to staff; clients and professionals cannot access raw audio. |

Except for health, public service prices, explicitly published branding/media and request/access/verify/me auth routes, endpoints require a valid session and the appropriate role. See [portal API additions](docs/client-portal.md#api-additions) and [media routes](docs/media.md#stockage-et-api) for their contracts. Legacy invite previews still grant no access; the owner-only [membership controls](docs/client-portal.md#accounts-and-access) provide explicit client/carer access and separate [professional selections](docs/client-portal.md#selected-professional-access). Dogs registered directly in **Dogs / Chiens** or through Planning join the daily registry via `PUT /api/daily` and become available to the care-note UI. They appear in `daily.dogs` within `/api/state`; registration alone does not create a care-dog row. Only explicit development signup seeds Billie and Charlie; real owner bootstrap is empty.

### Mutation contract

First read `/api/state` with your session cookie. Include `X-DogCare-Business: <business_id>` on every authenticated POST/PUT, including uploads and logout. Care and portal writes also require `If-Match: "<revision>"` from that state; the quotation marks are required. Each successful observation, invite, language, dog, daily-record, document, experience, accounting, portal, or first-import write increments the business revision and closes import eligibility. Use the returned revision for the next care/portal write. Audio uploads and logout do neither. Media mutations do not advance the revision, but a successful media upload closes import eligibility. Document uploads use the guarded revision contract, including originals submitted with an accounting snapshot. A repeat `/api/import` still validates the payload and business binding, but returns the current state with `skipped: true` without checking or advancing the revision.

Observation/invite PUTs are **full replacements, not appends or per-dog updates**. Preserve all records you want to keep in the submitted snapshot. Omitting a dog removes its observations, but keeps the dog row; unknown valid slugs create dogs only when their observation list is nonempty. Empty unknown keys do not manufacture dog records. `{ "observations": {} }` clears all observations, and `{ "invites": [] }` clears all invites. Import leaves absent top-level collections unchanged. Validation or database-constraint failures roll back the whole care write, including its revision. Successful care PUTs return the full state, read in the same transaction as the write. Language belongs to a user, even though changing it advances the business revision.

The browser adapter in [api.js](api.js) loads these records before [app.js](app.js) renders them. `DogCareAPI.ready` resolves to a boolean; `false` with `isAnonymous()` means the public welcome, otherwise reload/sign-in/import recovery is needed. The getters read its in-memory cache; `getDogs()`, `getDaily()`, `getKnowledge()` and `getFinance()` return copies. `saveObservations`, `saveInvites`, `saveLanguage`, `saveDaily`, `saveDocument`, `saveKnowledge`, `saveFinance(finance, uploads=[])` and `savePortal(action, payload)` serialize writes and resolve to success booleans; `whenSaved()` waits for writes already queued. See the [portal adapter](docs/client-portal.md#api-additions) for session, estimate and logout helpers, and the [media adapter](docs/media.md#stockage-et-api) for independent transfers. `getDocument(id)` fetches the private file with the session cookie and resolves to a `Blob`, or `null` when unavailable; it accepts server-issued 32-character lowercase hexadecimal IDs. `getFinanceDocument(id)` does the same for a 64-character lowercase SHA-256 ID. `reloadFinance()` retries loading only the finance cache, returning `false` if the business or shared revision has changed; it does not resolve a stale-account conflict. Account saves do not mirror data back into localStorage or the static accounting IndexedDB database.

### Care payloads and recording references

- `observations` maps dog identifiers to ordered arrays of objects. Daily records and care notes share case-sensitive identifiers of 1–81 ASCII letters, digits, underscores or hyphens, beginning with a letter or digit. Existing identifiers keep their spelling. Observation fields are `id` (optional signed 64-bit integer), `text`, `title`, `time`, `date` (strings), `tags` (array of strings), and optional `audio`. Missing text fields read back as empty strings; missing tags become `[]`. Array order is retained, not sorted by the display date/time.
- `audio` has a required `url`, optional string `type`, and optional finite `duration` in seconds from 0 to 86400. Upload inline audio first, then construct `/api/blobs/<ref>` using the returned `ref` filename. References have 32 lowercase hexadecimal characters and a `webm`, `ogg`, `m4a`, `wav`, or `mp3` extension. External URLs, inline recordings, and query strings are rejected in care writes. Validation checks the URL shape; it does not check that the file exists. Reads remain scoped to the current business.
- `invites` is an ordered array with string `email`, `name`, `role`, `status`, optional `token`, and `permissions` (array of strings; `areas` is also accepted on write). Missing role/status default to `owner`/`pending`, and missing tokens are generated. Tokens must be unique across the database. Replacements assign new server IDs; client `id`/`created` values are not retained, and reads show `created: "Today"`.
- `language` is a string of 1–8 characters. The UI offers `en`, `fr`, `it`, `de`, and `es`; the API does not enforce that list.

Audio uploads use strict base64 and count toward the JSON body limit, so the maximum raw recording is smaller than 32 MiB. The `type` hint selects the file extension (`ogg`, `m4a` for MP4, `wav`, `mp3` for MPEG, otherwise `webm`); the server does not transcode or inspect the audio. Identical bytes with the same extension reuse a file within the business, including concurrent/retried uploads. Files are separate across businesses. Uploads happen before snapshot writes and are not rolled back if the subsequent save fails.

### Errors

API errors generally return `{ "ok": false, "error": "…" }`. Invalid JSON or care/daily/document/experience/accounting fields return 400; missing/expired sessions return 401; cross-origin writes or forbidden roles return 403; unknown or other-business dogs/recordings/documents return 404; conflicting data or stale business/revision headers return 409; oversized bodies return 413; a non-JSON content type on JSON routes returns 415; and missing business/revision headers return 428. Login rate limits return 429 and disabled/misconfigured delivery returns 503. Daily-record, document, experience or accounting database failures return 500 and roll back that write. Invalid accounting transitions, duplicate invoice numbers and original-file mismatches return 400; see the [accounting contract](docs/comptabilite.md#api-contract). Business/revision precondition failures also include `reload_required: true`. Copy the draft, reload current state, and reconcile it before another write. The adapter blocks further queued care/portal writes after that signal or an authenticated write's 401; logout remains available. Other write failures leave the draft available for retry. Media errors follow their [separate contract](docs/media.md#stockage-et-api).

## Navigate the workspace

The shell keeps one **Le Bus des Toutous · by Plus de Fun** header. The staff dashboard, **Votre journée, au clair.**, shows saved planning, dogs, notes and pending client requests. Four primary destinations sit above the content; **All my tools / Tous mes outils** opens the remaining tools in a dialog.

| Group | Destinations (English labels) |
| --- | --- |
| Primary navigation | Home (dashboard), Schedule, Dogs, Capture |
| All my tools | Handoff, Care & wellbeing (Maison de la Santé in French), Muse assistant, Daily story, Gallery, Invite, Accounting (Comptabilité in French), Settings |

The primary buttons wrap within the page at desktop and phone widths. The header and navigation scroll with the page; the tools dialog scrolls independently when needed. Trusted carers have the same care navigation but no Invite, Accounting or Settings. Clients have a separate four-button space: **My dogs**, **Reservations**, **Updates** and **Documents**, with no staff tools or capture shortcut. Professionals have one **Shared records / Dossiers partagés** destination for selected dogs and records, with language and sign-out controls but no staff tools or capture shortcut.

Buttons have at least 44px targets, visible keyboard focus, and an active state exposed as `aria-current="page"`. Use Tab to reach a destination and Enter or Space to activate it. Selecting a tool closes the dialog and returns the page to its heading. Handoff evidence links open the source note in the dog's timeline.

The static workspace uses the owner navigation. Both modes support French, English, Italian, German, and Spanish; the language picker remains beside the page heading. **Public site / Site public** opens the service welcome, and signed-in accounts can **Sign out / Se déconnecter**. The [compact-navigation review](docs/review/muse-compact-navigation/README.md) retains historical sidebar/strip images, not the current layout.

## Comptabilité

Invoices, expense claims, billed extras, local receipt recognition and accountant export are available under **Accounting** (**Comptabilité** in French). Planned monthly booking totals and base rates remain in its **Bookings & rates / Réservations et tarifs** tab, also reached directly from home/planning shortcuts. See [Comptabilité](docs/comptabilite.md) for review, payments, print/PDF, original documents, workbook export and storage boundaries. OCR/PDF/ZIP libraries are bundled locally and loaded only for intake/export; no install or external document service is required.

## Maison de la Santé

Sourced everyday-care guides, labelled provider videos and saved private experience drafts are accessible from **Tous mes outils** in the workspace. See [Maison de la Santé](docs/maison-sante.md) for the content, storage, compatibility and verification boundaries. Existing records and sessions are preserved; no experience is published or clinically approved by saving it.

## Try the core flow

1. Open **Tous mes outils → Muse assistant** and ask for today’s briefing, recorded items needing attention, or an owner handoff. Muse lists the loaded dogs with today’s note counts and counts today’s active saved bookings; it is not connected to a remote AI service.
2. Use a quick action or open **Capture update** from the dashboard or navigation.
3. Choose a dog and type a note, or use **Dictate** to see a voice note transcribed live into the care-note field.
4. Edit the text if needed, review the detected tags, and save the observation.
5. The new structured card appears in the dog's timeline and the owner story preview updates immediately.
6. Open **Handoff** to review a care-continuity summary for either the owner or next carer, follow its evidence links back to today's observations, and check the suggested next-care actions.

Health-watch content is deliberately phrased as factual observation rather than diagnosis. The handoff reminds carers to keep observing and contact the owner or a veterinarian when concerned.

Capture keeps a separate unsaved draft for each dog while the tab remains open. Switching dogs, language, or views preserves each draft; a successful save clears only that dog's draft. Save before reloading or closing the tab: drafts are not persisted, and the browser warns when leaving with unsaved work. If browser storage fails, capture remains editable and displays a persistent failure message; retrying after storage is available saves the note once.

New observations store their local calendar date as `YYYY-MM-DD`. Today's handoff uses that day, while older observations stay in the timeline. Existing app-created records that stored the literal `Today` are dated using their epoch-millisecond ID when read, without rewriting stored history. Low-numbered demo records retain their illustrative Today/Yesterday labels.

## Try the invite preview flow

This preview form is available only in static mode. In account mode, **Inviter** provides [real access grants](docs/client-portal.md#accounts-and-access) and a read-only disclosure of previously saved previews.

1. Open **Invite** (**Inviter** in French) from **Tous mes outils** (All my tools).
2. Choose **Owner** or **Trusted carer**, add a demo name and email, and select share areas.
3. Review the invite-ready summary and create a **pending invite preview**.
4. The pending invite is saved in this browser. No email, WhatsApp, SMS, or notification is sent, and no account access is granted.

## Try dictation, retained recordings, and sharing

1. Open **Capture update**, add written care context, then choose **Dictate**. Microphone permission is requested only at that point.
2. Choose **Stop**, edit the transcript, and save the care update. The current **Dictate** control transcribes text only; it does not create a new audio attachment. The separate recording helper in `app.js` is not wired to that control.
3. Existing supported audio attachments remain playable on the dog's timeline and in **Gallery**. Static mode reads inline audio from browser storage; account mode uploads imported recordings to the business's server store and plays them through authenticated URLs.
4. In **Gallery**, preview the clearly labelled Instagram, Facebook, and YouTube access states. These controls do not ask for credentials, connect accounts, make network requests, or post content.

Browsers without speech recognition, `file://` pages, and denied speech permission receive an inline explanation; typed care capture remains available. Open the app through the local HTTP launcher for dictation.

Timeline and story **Share** controls can open the device share sheet and attach supported audio when file sharing is available. In account mode, fetching that audio requires the current session; an expired/switched session shows a sharing error instead of sharing the unavailable recording. Fallback controls open WhatsApp, Telegram, or Facebook, or copy text for Instagram. These are user-initiated sharing actions; they are separate from the Gallery's connection previews and do not provide automatic owner delivery.

## Product boundaries

Static mode is a local demo with fictional care moments around the named pilot profiles. Account mode provides persisted private workflows with role-based access and an empty real-owner bootstrap. Muse and AI structuring use deterministic, on-device parsing; neither connects to a remote AI service. Assistant questions stay in the browser. Account daily stories quote saved notes without the static demo's illustrative meals, mood or exercise statistics.

- **Static mode** (`python3 -m http.server`, no `DOGCARE_API`): care records and retained recordings are saved in this browser, with no API upload.
- **Account mode** (`python3 api/server.py`, flag on): care records and recordings are stored in the business’s own account store on the server the business runs. API access is restricted to signed-in members of that business. The one-time recording import shows a notice before moving existing audio.

Static invitation previews grant no access. Owner-created account memberships grant access without sending an invitation; members request their own sign-in links. Login delivery is disabled by default, writes a private outbox only in explicit loopback development mode, or uses configured TLS-protected SMTP for known members. See [client access and delivery](docs/client-portal.md). Social connections, automatic owner delivery and cross-device synchronization for static storage remain unavailable; social connection previews never collect credentials or post to a network. Explicit sharing can pass selected care content to the app you choose. Accounting can issue and print invoices and record manually entered payments/reimbursements, but does not send invoices, execute payments, reconcile a bank account or file taxes. Payment processing and subscriptions remain unimplemented. Operational rates are user supplied. [Deployment and backup templates](docs/private-beta-release.md) require a separate operator action; their presence does not establish a deployed service or successful email receipt.

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

Account photo/video albums and owner artwork settings are documented in [Photos, vidéos et personnalisation](docs/media.md), including supported formats, private/public boundaries and backup behavior. The API and backup tools require Python 3.11 or later. Phone-media conversion also requires local FFmpeg/ffprobe and libheif’s `heif-convert`; the [media runtime gate](docs/private-beta-release.md#media-runtime-gate) checks real decoding before production startup.

For focused API checks, all Node regressions and JavaScript syntax checks:

```bash
python3 -m unittest tests.test_api_server tests.test_tenant_isolation tests.test_daily_api tests.test_knowledge_api tests.test_finance_api tests.test_crawl_site -v
node --test tests/*.js
for file in *.js; do node --check "$file" || exit 1; done
```

The full Python discovery command below also includes portal, professional-access, login-delivery/rate-limit, account-registry, cancellation, billing, media, backup and static-boundary regressions. Browser checks need Playwright and its matching Chromium binary; Crawl4AI is not required. Real media checks need FFmpeg/ffprobe with the codecs described in [media verification](docs/media.md), including the test-only libx265 encoder for synthetic HEVC fixtures. Real HEIC conversion checks need `heif-convert`; a skipped check does not establish support. Using `uv` and the Playwright version in `requirements-crawler.txt` (reuse matching cached Chromium when available):

```bash
uv run --python 3.12 --with playwright==1.61.0 python -m playwright install chromium
uv run --python 3.12 --with playwright==1.61.0 python -m unittest discover -s tests -v
```

The suite starts its own local servers and temporary account storage. It covers both static and account modes, authentication, tenant isolation, safe migration and replacement writes, stale-tab/timeout recovery, protected recordings, robots/origin/output boundaries, the Muse briefing-to-handoff journey, dictated text editing, and mobile overflow. Daily-workflow checks cover booking create/reload/edit, original-rate extensions, cross-month allocation, unknown rates, private document download and renewal follow-up, and failed-save recovery in both storage modes.

Dog-registration checks cover the selected profile and empty directory, optional owners, distinct IDs for same-named dogs, duplicate-submit prevention, cancel, failed-save/retry, literal drafts across navigation and five locales, save/reload and later booking association. They also cover keyboard focus, 44px controls and overflow at phone, tablet and desktop sizes; API/model checks cover ownerless records and business/revision guards.

Knowledge checks cover guide search and provider links, topic choices, five locales, private experience save/edit/reload, literal text and Unicode limits, failed-save drafts, and conflicting tabs in both storage modes. API checks cover business isolation, stale/switched-account rejection and atomic validation. External video navigation is intercepted in the fixture; remote playback and live source verification are separate from these tests.

Accounting checks cover invoice/extra/payment save/reload, local receipt OCR and PDF/manual intake, immutable originals, duplicate rejection, ZIP/XLSX contents, literal cells, failed-save recovery and stale-tab protection in both storage modes. Synthetic raster OCR checks also cover sparse card slips with no supplier, conservative invoice references, reviewed values after reload, numeric workbook cells and links to byte-identical originals. Camera file inputs are exercised with synthetic files; physical-camera operation remains unverified. See [accounting checks](docs/comptabilite.md#local-readers-and-checks) for focused commands; the full Python discovery command above includes the finance browser suite.

Navigation checks reach all 12 owner destinations through the primary buttons and tools dialog, in five locales at 1440 × 900, 1024 × 768, and 390 × 844. They cover keyboard activation, active state, 44px targets, a single business brand, heading visibility after switching from scrolled content, and return to the selected tool.

Professional-access checks cover individual grants and file denial, shared note versions, stale selections, dog reassignment/removal, revocation and concurrent authorization changes. The browser journey checks owner selection/review, professional self-login, reload and revocation at desktop and phone widths; see [selected professional access](docs/client-portal.md#selected-professional-access).

Account recovery checks cover French initial copy, all five recovery languages, no account or browser-setting writes when switching languages, and no fallback to demo history. They also check overflow and the reload button's 44px target at the three viewports above.

Speech recognition is simulated; these tests do not verify a real microphone or browser-provider transcription service. Browser tests skip with an installation hint if the Playwright Python package is absent; if the package is installed but Chromium is missing, browser launch fails until the install step above completes. Pure API/crawler tests always run with the standard library, and the Node adapter tests run separately.

Set `DOGCARE_EVIDENCE_DIR` to an allowed evidence directory to retain the browser suite's selected screenshots and migration-state JSON; when unset it does not write those evidence files. Browser checks await `#app-content[data-ready="true"]` and rendered content, since adapter hydration alone does not establish that the UI is ready.

Private beta operator procedure and reviewed local templates: [docs/private-beta-release.md](docs/private-beta-release.md). No deployment is performed by the application or these templates.
