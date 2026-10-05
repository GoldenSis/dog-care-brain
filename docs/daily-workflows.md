# Daily work: bookings, rates, documents and monthly summaries

Planning saves bookings against a dog and client. The existing care-note, history, handoff and gallery journeys remain available. Operational lists start empty; the sample care notes are separate from saved bookings. Booking records describe **planned** services, not completed visits, invoices or payments.

A booking does not record arrival or consent, so profiles show neither status as a badge. Sample timeline entries are labelled separately. Resetting sample observations restores those examples while retaining saved notes, registered dogs and their daily records.

## Bookings and rates

Open **Planning**, choose **New booking**, then a known dog or **New dog**. A known dog's client is reused; a new dog can reuse an existing client by name. Choose a walk, day care or overnight stay, enter the dates and inspect the units and amount before saving. Saved bookings can be reopened and edited after reload.

- Walks and day care count every calendar date from start through end, inclusively, as one service unit per day. Multiple walks on one date require separate bookings.
- Overnight stays count nights from arrival to checkout; checkout is excluded. At least one night is required.
- A booking may contain at most 366 service units. Invalid dates and reversed ranges are rejected.
- Configure base unit rates under **Business**. Empty rates remain unknown, including on summaries; no sample tariffs, discounts or bonuses are supplied. Currency is explicit.
- A booking keeps its saved unit rate and currency. An unknown amount can later receive an explicitly entered agreement; changing configuration alone never fills it. Later configuration changes apply to new agreements. Extending the same service uses the original agreement and shows added units, added amount when known, and the revised total before saving. Changing the service uses the configured rate for that service.

The monthly summary groups actual saved bookings by client, service and currency. Each service date is allocated to its own calendar month. A stay from 30 October to 2 November contributes two October nights and one November night. A booking spanning months appears in each affected month's booking count; counts across months are not a count of unique bookings. Known subtotals and units with unknown rates are shown separately. Nothing is labelled paid or completed.

## Documents and follow-up

Open a dog's profile, add a document label and a PDF, JPEG or PNG, and optionally enter its recorded renewal date. Files must be nonempty, at most 5 MiB, and match the selected supported file signature. The app does not inspect clinical meaning, infer vaccinations or calculate a clinical renewal schedule.

Saved documents can be downloaded after reload. Renewal dates can be edited. Dates before today are overdue; dates from today through the next 30 days appear as due. These follow-ups are visible on the home and planning pages and link back to the dog's documents. No reminder or message is sent.

## Storage and migration

| Mode | Records and documents | Boundary |
| --- | --- | --- |
| Static | `dogcare-daily-v1` in this browser's localStorage; files are base64 within that snapshot. | Origin and browser specific, constrained by browser quota. No server copy or cloud synchronization. |
| Account API | Business-scoped SQLite snapshot and document BLOBs in the private database. | Durable on the configured persistent server disk; session and business scope required for downloads and writes. |

Existing `dogcare-observations`, `dogcare-invites` and `dogcare-language` keys remain intact. The legacy import still imports only those three keys; **daily browser records and documents are not automatically imported into an account**. Switching modes does not copy daily records or update the original browser copy. Keep the original browser records until an explicitly supported transfer is available.

API initialization creates the new tables additively and reads an empty daily state for older businesses without changing their notes. Daily writes and document uploads require the current business and revision headers, increment the revision, and close legacy import eligibility. Documents and their metadata commit atomically. A failed or stale save retains the form; copy it before reloading to reconcile another tab's changes. Tabs do not refresh one another automatically.

Account documents never use public static file paths. Downloads use authenticated `/api/documents/<id>` routes with no-store, attachment, nosniff and sandbox headers. Files belong to a business, including when their contents are identical. There is no document deletion or automatic retention cleanup in this version. The existing recording store and its import rules are unchanged.

## API contract

`GET /api/state` includes `daily` with `version: 1`, `clients`, `dogs`, `bookings`, `rates` and `documents`. `PUT /api/daily` accepts `{ "daily": <snapshot> }` and returns the full account state. It preserves uploaded document identities and file references while allowing their labels and renewal dates to change.

`POST /api/documents` accepts `dogId`, `label`, `renewal` (empty or an ISO calendar date), `name`, `type` and strict base64 `data`; it returns the full account state. Upload the file separately from a daily snapshot. The document must reference a registered daily dog. Download it using `GET /api/documents/<id>` with the account session.

The schemas and exact limits are authoritative in [api/daily.py](../api/daily.py) and [daily-model.js](../daily-model.js). IDs are bounded portable identifiers; names/labels are limited to 120 characters and filenames to 180. Collections have a 5,000-record limit; money uses integer minor units from zero through 100,000,000 or unknown (`null`). Unsupported fields and malformed relationships are rejected.

## Hosting boundary

Static hosting cannot execute the Python API or provide its private persistent database. An account deployment needs a Python runtime, private persistent storage outside the static document root, an HTTPS reverse proxy, secure session cookies, tested backup and restore procedures, and an explicit production sign-in delivery solution.

For a compatible account deployment, run the existing stdlib server behind an HTTPS reverse proxy with private storage outside the document root. Example configuration for an operator to adapt after provisioning:

```bash
DC_HOST=127.0.0.1 DC_PORT=8787 \
DC_ROOT=/srv/dogcare/app DC_DATA_DIR=/srv/dogcare/private \
DC_INSECURE_COOKIE=0 python3 api/server.py
```

The listener itself remains HTTP on loopback; the proxy must preserve the public Host and terminate HTTPS. Keep secure cookies enabled. The development magic-link mailer writes a private local outbox; production needs a configured delivery solution before people can sign in. Back up the private database consistently with SQLite WAL, retain the private audio directory, and verify that both can be restored. Provisioning and external release require separate approval.
