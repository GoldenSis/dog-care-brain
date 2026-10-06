# Daily work: bookings, rates, documents and monthly summaries

Planning saves bookings against a dog and client. The existing care-note, history, handoff and gallery journeys remain available. Operational lists start empty; the sample care notes are separate from saved bookings. Booking records describe **planned** services, not completed visits, invoices or payments.

A booking does not record arrival or consent, so profiles show neither status as a badge. Sample timeline entries are labelled separately. Resetting sample observations restores those examples while retaining saved notes, registered dogs and their daily records.

## Registering a dog

Open **Dogs / Chiens** and choose **＋ Add a dog / Ajouter un chien**, above the current profile. The same action remains available with no dogs. **All dogs / Tous les chiens** opens the dog list without leaving the section. Enter the required dog name; optionally select an existing owner or enter a new one. Only those entered facts are saved; an omitted owner stays unknown. Saving opens the new profile and makes it available to the other dog selectors after reload. Different dogs may share a name; each has a separate stable ID. Cancel changes no saved records. Failed saves keep the form; drafts survive internal navigation and locale changes, but must be saved before closing/reloading.

The daily dog record uses `clientId: null` when no owner is recorded. A later booking requires a client and links that same dog without duplicating it. Existing client associations and recorded booking agreements are preserved. Registration itself creates no booking, care note, price, arrival or consent fact.

## Bookings and rates

Open the dashboard's **Planning** shortcut or **Schedule** in English navigation (**Planning** in French), choose **New booking**, then a known dog or **Add a dog**. A registered daily dog's saved client is reused, even when clients share a name, and cannot be changed in the booking form. For an ownerless or new dog, select an existing client or choose **New owner** and enter a name. Existing clients are selected by stable ID; names are retained literally and never used to merge identities. Choose a walk, day care or overnight stay, enter the dates and inspect the units and amount before saving. Saved bookings can be reopened with **Edit** after reload. The month selector shows bookings with service dates in that month; it is shared with the **Bookings & rates** summary under Accounting, independently of the accounting journal's month filter. **New booking** is hidden while its form is open.

- Walks and day care count every calendar date from start through end, inclusively, as one service unit per day. Multiple walks on one date require separate bookings.
- Overnight stays count nights from arrival to checkout; checkout is excluded. At least one night is required.
- A booking may contain at most 366 service units. Invalid dates and reversed ranges are rejected. The booking, renewal-date and month controls cover 2000–2199.
- Configure base unit rates under **Accounting → Bookings & rates** (**Comptabilité → Réservations et tarifs** in French), or use the rates shortcut in Planning. Rates start unknown with CHF selected; the currency selector also offers EUR, GBP and USD and retains any other already-saved currency code. Enter nonnegative amounts with at most two decimal places (a decimal point or comma), up to 1,000,000 per unit. Known amounts display exactly two decimal places in every currency. Empty rates remain unknown, including on summaries; zero is a known free rate. No sample tariffs, discounts or bonuses are supplied.
- New bookings start with the configured service rate and currency; the agreed unit price can be edited or left blank before saving. A booking keeps its saved unit rate and currency. An unknown price can later be entered once in the booking form, retaining its saved currency; changing configuration alone never fills it. Once recorded, the price is read-only for that service. To extend a stay, reopen it and move the end date later without changing the service or start date: the preview shows added units, added amount when known, and the revised total before saving. Changing the service starts a new agreement with the current configured currency and rate, which can be edited before saving.

Open **Accounting → Bookings & rates**, or the dashboard's monthly-summary shortcut, to view the monthly summary and choose a month. It groups actual saved bookings by client, service and currency. Each service date is allocated to its own calendar month. A stay from 30 October to 2 November contributes two October nights and one November night. A booking spanning months appears in each affected month's booking count; counts across months are not a count of unique bookings. Wholly unpriced totals remain unknown; mixed totals show known subtotals excluding unpriced units, with those units counted separately. Currencies are never combined or converted. **How counts work** expands the allocation explanation. Nothing in this booking summary is labelled paid or completed; there is no booking deletion control or occupancy calculation. [Accounting](comptabilite.md) separately supports copying saved agreements into invoice lines and recording actual payments.

## Documents and follow-up

Open a dog's profile, add a document label and a PDF, JPEG or PNG, and optionally enter its recorded renewal date. Files must be nonempty, at most 5 MiB, and match the selected supported file signature. The app does not inspect clinical meaning, infer vaccinations or calculate a clinical renewal schedule.

The dog must be registered in the daily registry; dogs registered through **Add a dog** can receive documents even while the owner is unknown. For a profile without daily registration, select an existing owner by stable ID or explicitly choose **New owner** during upload. Any recorded profile owner name prefills the new-owner field; names never select or merge clients automatically. Existing daily associations remain unchanged. New profiles show placeholders for unrecorded details; this version has no general profile-detail editor.

Saved documents can be downloaded after reload using **Download document**. **Edit renewal date** lets you change or clear the date, then **Save date** persists it. Dates before today are overdue; dates from today through the next 30 calendar days, inclusive, appear as due, using the device's local date. These follow-ups are visible on the home and planning pages and link back to the dog's documents. No reminder or message is sent. Clinic-call and video-consultation preview controls have been replaced by an unavailable notice; care notes and handoff links remain available.

## Storage and migration

| Mode | Records and documents | Boundary |
| --- | --- | --- |
| Static | `dogcare-daily-v1` in this browser's localStorage; files are base64 within that snapshot. | Origin and browser specific, constrained by browser quota. No server copy or cloud synchronization. |
| Account API | Business-scoped SQLite snapshot and document BLOBs in the private database. | Durable on the configured persistent server disk; session and business scope required for downloads and writes. |

Existing `dogcare-observations`, `dogcare-invites` and `dogcare-language` keys remain intact. The legacy import still imports only those three keys; **daily browser records and documents are not automatically imported into an account**. Switching modes does not copy daily records or update the original browser copy. Keep the original browser records until an explicitly supported transfer is available.

Dogs with imported notes remain selectable in profiles, capture, handoff and stories using their account identities. Their note identifiers and history stay intact. Selecting an existing dog in a booking reuses its identifier, including the literal ID `new`; **Add a dog** creates a fresh identifier. A recovered profile uses the account's recorded name; daily-only names and client details stay in the original browser records. Recovery does not infer health, arrival or consent.

API initialization creates the new tables additively and reads an empty daily state for older businesses without changing their notes. Daily writes and document uploads require the current business and revision headers, increment the revision, and close legacy import eligibility. A document's bytes and metadata commit atomically. The UI may first register a dog/client in a separate daily write; that registration can remain if the subsequent upload fails.

A failed or stale save retains the open form; copy it before reloading to reconcile another tab's changes. Browser-local daily saves require a current browser on HTTPS or localhost. Saves across tabs are coordinated, and an older snapshot cannot replace newer bookings, rates or documents. The rates confirmation clears when you edit an amount or currency and before each save attempt. Booking, rate and document forms are not capture drafts: navigation, language changes and reloads discard unsaved entries, and they do not trigger the care-note draft warning. Save or copy them before leaving. Tabs do not refresh one another automatically. Invalid stored daily data displays a load error and blocks daily saves instead of overwriting the snapshot.

Account documents never use public static file paths. Downloads use authenticated `/api/documents/<id>` routes with no-store, attachment, nosniff and sandbox headers. Files belong to a business, including when their contents are identical. There is no document deletion or automatic retention cleanup in this version. The existing recording store and its import rules are unchanged.

## API contract

`GET /api/state` includes `daily`. Read it first, then send `PUT /api/daily` with `{ "daily": <snapshot> }`, the session cookie, `X-DogCare-Business: <business_id>` and `If-Match: "<revision>"` as described in the [mutation contract](../README.md#mutation-contract). This is a **full replacement**, not a partial update: preserve every client, dog, booking and document you want to retain. It returns the full account state, including the next revision.

Every field below is required; empty lists are allowed. IDs must be unique within each collection.

| Daily field | Value / record fields |
| --- | --- |
| `version` | Integer `1`. |
| `clients` | Array of `{ "id": <client ID>, "name": <name> }`. |
| `dogs` | Array of `{ "id": <dog identifier>, "name": <name>, "clientId": <existing daily client ID or null> }`. |
| `bookings` | Array of `{ "id": <booking ID>, "dogId": <existing daily dog ID>, "service": "walk" / "day" / "night", "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "unitMinor": <integer or null>, "currency": <currency> }`. |
| `rates` | `{ "currency": <currency>, "walk": <integer or null>, "day": <integer or null>, "night": <integer or null> }`; defaults to CHF and three `null` rates. |
| `documents` | Array of `{ "id": <server ID>, "dogId": <existing daily dog ID>, "label": <label>, "renewal": "" / "YYYY-MM-DD", "name": <original filename>, "type": <MIME type>, "href": "/api/documents/<id>" }`. Static snapshots use base64 `data` instead of `href`. |

Daily dog IDs are the case-sensitive care-note identifiers (`slug` in `/api/dogs`), not numeric care-dog row IDs. Saving daily dogs does not create rows in `/api/dogs`; the UI combines both registries. A later observation write creates any missing care-dog row. Daily writes leave observations unchanged.

For an existing booking ID and unchanged service, a known `unitMinor` and its currency must be retained, including zero. A `null` price can be explicitly set with an agreed currency; the server never applies configured rates automatically. A service change permits a new agreement. Daily PUTs must retain the entire set of uploaded document IDs and their `dogId`, `type`, `name` and `href`; only `label` and `renewal` can change. Omitting documents or forging file references is rejected.

`POST /api/documents` requires exactly `dogId`, `label`, `renewal`, `name`, `type` and `data`, plus the same business/revision headers. `renewal` must be present even when no date is recorded: use `""`. `type` is `application/pdf`, `image/jpeg` or `image/png`; `data` is strict base64 without a data-URL prefix. The dog must already exist in the daily registry. The server assigns a 32-character lowercase hexadecimal document ID and returns full account state with metadata and a private `href`, never file bytes. Upload the file separately from a daily snapshot. Download it using `GET /api/documents/<id>` with the account session; direct downloads use a generated `document-<id>.<extension>` filename, while the UI uses the stored original filename.

The schemas and exact limits are authoritative in [api/daily.py](../api/daily.py) and [daily-model.js](../daily-model.js). IDs contain 1–81 ASCII letters, digits, underscores or hyphens and begin with a letter or digit. Names/labels are limited to 120 Unicode code points and filenames to 180; blank values and control characters are rejected. Each collection has a 5,000-record limit. Unit rates use integer hundredths from zero through 100,000,000 or unknown (`null`); calculated totals may exceed that unit-rate limit. Currency codes must be three uppercase ASCII letters; API validation accepts any such code. API/model dates accept valid `YYYY-MM-DD` dates from years 0001–9999; the UI controls have the narrower range above. Unsupported record fields and malformed relationships are rejected. Invalid document contents or files exceeding 5 MiB return 400; the separate 32 MiB JSON request-body cap returns 413. Failed validation leaves the snapshot, document bytes, revision and import eligibility unchanged.

## Hosting boundary

Static hosting cannot execute the Python API or provide its private persistent database. An account deployment needs a Python runtime, private persistent storage outside the static document root, an HTTPS reverse proxy, secure session cookies, tested backup and restore procedures, and an explicit production sign-in delivery solution.

For a compatible account deployment, run the existing stdlib server behind an HTTPS reverse proxy with private storage outside the document root. Example configuration for an operator to adapt after provisioning:

```bash
DC_HOST=127.0.0.1 DC_PORT=8787 \
DC_ROOT=/srv/dogcare/app DC_DATA_DIR=/srv/dogcare/private \
DC_INSECURE_COOKIE=0 python3 api/server.py
```

The listener itself remains HTTP on loopback; the proxy must preserve the public Host and terminate HTTPS. Keep secure cookies enabled. The development magic-link mailer writes a private local outbox; production needs a configured delivery solution before people can sign in. Back up the private database consistently with SQLite WAL, retain the private audio directory, and verify that both can be restored. Provisioning and external release require separate approval.
