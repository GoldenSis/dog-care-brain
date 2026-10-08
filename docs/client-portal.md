# Public welcome and private client space

The API app opens on a public French welcome for **Le Bus des Toutous · by Plus de Fun**. Day care, an overnight stay and a walk each reveal their own explanation and configured price. Contact links to the already documented public Instagram profile. **Mon espace** requests a personal sign-in link. The anonymous API homepage loads only the welcome scripts; the workspace `app.js` requires authentication. No private snapshot is fetched before authentication. First-time visitors also have a first-contact route in the request dialog: a selected-service message they can copy and send themselves through the verified public Instagram profile. This is an external conversation, not a saved in-app request or an account grant.

The service choice travels in the login link, so a link opened in a fresh tab returns to the request form. A client chooses their dog, service and dates; the API calculates the estimate. Submission records a **request awaiting confirmation**, not a confirmed reservation or a payment. The owner sees the request and can accept or decline it. Acceptance creates an ordinary saved booking, retaining the quoted service rate. A missing rate remains unknown until the owner explicitly completes it.

The owner can [cancel a saved booking](daily-workflows.md#bookings-and-rates) from Planning. Its history and agreed amounts remain visible to the owner with **Annulée** status, and to the original family while the dog is still linked to that family. Cancellation neither changes invoices/payments nor sends a message. Cancelled bookings cannot be edited or reactivated.

After a dog is reassigned, its original pending request can still be declined; acceptance stays blocked. The original family retains that pending or declined request and its quoted amounts in reservation history, even with no dogs currently assigned. This history does not grant access to the dog's current profile or the new family's records.

## Accounts and access

Public email submission only signs in known active members. It never grants owner status or creates a new business. Existing owners and language preferences are retained. Newly bootstrapped owners start in French. Bootstrap a new, empty owner account deliberately with `python3 api/create_owner.py --email <owner-email>` against the intended private `DC_DATA_DIR`; this does not send mail. Disable demo signup first.

The owner registers a client and their dog in the existing daily records, then opens **Tous mes outils → Inviter → Accès aux comptes**. An email can be linked to that client's dogs or added as a trusted carer. Saving an access grant does not send an email. The person then requests their own login link from **Mon espace**. Revocation and reassignment invalidate that member's existing sessions. An account belonging to another business or an existing owner cannot be reassigned through this control.

| Role | Available records and actions |
| --- | --- |
| Visitor | Public descriptions and explicitly published service rates; no private account state. |
| Client | Their linked dogs, bookings, family requests and quotes, explicitly shared news and client documents. Can request a booking, change their language and manage their authorized dog albums. |
| Trusted carer | Internal care records and planning; can accept/decline requests and share client news/documents. Cannot manage access, set prices/extras, cancel bookings, read accounting originals or access private dog albums. |
| Professional | Only explicitly selected dogs and individual shared note versions, documents, photos/videos. Read-only, with their own language preference. No family details, bookings, quotes, accounting, raw audio or general internal records. |
| Owner | All existing care functions plus access grants, prices/extras, cancellation, private accounting, dog albums and public artwork settings. |

Authorization is enforced by the API for reads, writes and attachment downloads, including direct/guessed URLs. Client news and documents are separate from internal notes, health documents and accounting originals. Saved client-facing records retain their family audience; moving a dog to another client does not transfer the former family’s requests, quotes or shared files. Existing daily bookings acquire their saved client association during the additive schema upgrade. In account mode, Inviter opens real membership controls. Previously saved invitation previews remain in a read-only disclosure and do not grant access. Static mode retains its explicitly labeled preview form. Account settings show the account and access/rate actions; the demo reset exists only in static mode. Static mode retains the existing local workspace, without a simulated client login or server membership system.

Staff share news and files through **Chiens → Partager au client**, choosing a dog linked to a family. Publishing here explicitly makes that item available in the family's **Nouvelles** or **Documents** section; internal notes and health documents are not copied automatically. [Photos, videos and public artwork](media.md) have separate album permissions and publication controls.

## Selected professional access

For a veterinarian or osteopath, use **Inviter → Accès professionnel**, not the business-wide trusted-carer role. The owner enters the email, selects dogs and ticks each note, document or image to share. **Enregistrer l’accès** grants sign-in access without sending mail; the invited person requests their own personal link from **Mon espace**. An existing owner, client, trusted carer or another business's account cannot be converted through this control.

The professional's **Dossiers partagés** contains only the selected dog names and records. Notes are explicit copies of the version selected by the owner; later edits stay private. A version key rejects a stale selection if the note changed before saving. Owners can inspect **Version partagée**, then use **Revoir la sélection** to edit the grant. Only still-current record keys are checked in that form. The saved older note remains shared until the grant changes; saving replaces the entire dog/record selection, dropping omitted versions. To share a later edit, explicitly tick the current note. Downloads recheck the individual grant on the server; raw recording URLs and all accounting routes remain forbidden.

**Retirer l’accès** removes all professional grants and invalidates sessions and pending login links. Changing a selection also ends existing sessions/links, requiring a new sign-in. Removing a dog or assigning it to another family removes its grants permanently, including if its identifier is reused. Previously downloaded files cannot be recalled. A read already authorized inside a transaction may finish its original snapshot; later reads use the current grant.

`POST /api/portal/professionals` accepts `{email, dogIds, recordKeys}` from an owner under the existing business/revision contract. At least one and at most 100 unique dogs, and at most 500 unique current record keys, are accepted; an empty `recordKeys` list shares dog names only. Keys must come from the current `portal.shareCatalog` and belong to selected dogs; do not construct them from IDs. Every save replaces that professional's full selection. Only the owner projection includes `portal.shareCatalog` and `portal.professionals`; the professional projection exposes `portal.sharedRecords`. The catalogue includes daily notes, internal dog documents, family-shared documents and dog photos/videos, but no raw audio, accounting or knowledge drafts. Files retain their selected metadata and reference the stored bytes; deleting a media file makes its download unavailable. Professionals can only write their own language preference or sign out. Additive `professional_dog` and `professional_record` tables are included in the existing whole-database backup/restore. No clinical credentials or professional record-writing privileges are implied by this role.

The isolated `tests.test_professional_access` suite covers projection, direct API/file denial, stale versions, dog reassignment, revocation and deterministic concurrent access changes. `tests.test_professional_browser` covers owner selection/review, the professional's own login, desktop/phone rendering, reload and revocation, with synthetic records and a local development outbox only.

## Login transport

Delivery is disabled unless configured. No production request falls back to a debug outbox.

| Configuration | Behavior |
| --- | --- |
| `DC_AUTH_MODE=disabled` (default) | Login requests fail with 503 until delivery is configured. |
| `DC_AUTH_MODE=development` | Loopback bind only. Writes a local, private outbox; never sends email. |
| `DC_ALLOW_DEMO_SIGNUP=1` | Only effective with development mode on loopback. The legacy `/api/auth/request` can create isolated demo businesses. The public `/api/auth/access` still accepts known members only. Never enable this for a beta or production service. |
| `DC_AUTH_MODE=smtp` | Acknowledges requests before checking membership or sending through certificate-verified SMTP. Delivery errors invalidate the new token and are logged privately. |
| `DC_PUBLIC_ORIGIN` | Required HTTPS origin for SMTP links; never inferred from the request's Host header. |
| `DC_INSECURE_COOKIE=0` | Required with SMTP so sessions use secure cookies. |
| `DC_TRUSTED_PROXY=127.0.0.1` | Opts into the dedicated Caddy client-IP header only on a matching loopback bind and peer. Unset by default; other values do not enable trust. Follow the [deployment trust contract](private-beta-release.md#https-browser-permissions-and-public-verification). |
| `DC_SMTP_HOST`, `DC_SMTP_USER`, `DC_SMTP_PASSWORD`, `DC_SMTP_FROM` | Required SMTP connection and sender configuration. Supply secrets through the deployment's private environment. |
| `DC_SMTP_TLS` / `DC_SMTP_PORT` | `ssl` / 465 by default; `starttls` / 587 also supported; the deployment template explicitly selects the authorized Infomaniak transport on port 2525. Unencrypted delivery is not supported. |

Links are single-use with a 15-minute lifetime. Production attempts are bounded per address and source IP. Two delivery workers handle at most 128 queued or active requests; an exhausted queue is logged privately and keeps the same public acknowledgment. Tokens remain unusable until delivery succeeds. Messages use the authenticated mailbox as envelope sender, matching the visible From address, with Date, Message-ID and Auto-Submitted headers. Unknown addresses receive the same conditional acknowledgment as known members without receiving a token or acquiring an account. SMTP latency and delivery failure never change that acknowledgment. Tokens, credentials and SMTP response details are not returned in API bodies. Tests mock both TLS transports; they do not establish that an actual host can deliver email. Deployment, real credentials, sender authorization, mailbox receipt and HTTPS must be verified separately before inviting real users.

## Prices and options

Existing **Comptabilité → Réservations et tarifs** remains the rate editor. `DC_PUBLIC_BUSINESS=<business-id>` explicitly selects the business whose three base rates may be published by `/api/public/services`. Without this binding no account's rates are published. This endpoint contains only currency and the three rate values, never dogs or financial records. No prices are bundled with this design.

Money reuses the daily/accounting integer-hundredths contract, displayed with two decimal places. Unknown is distinct from zero. Day/walk ranges count inclusive calendar dates; nights count departure minus arrival. The UI makes no promised schedule or availability. A request snapshots the configured unit rate; changing the rate list does not reprice existing requests or bookings. Completing an unknown rate requires an explicit owner action. The amount is a quoted price, not an automatic charge.

Trusted carers create bookings with the owner's configured rate applied by the server. Their form shows a read-only estimate and submits a null price for new bookings; an unconfigured service stays unknown. They cannot supply prices, change base rates, or change an existing booking's dog, service or saved monetary values. They can edit dates and extend a stay at its saved unit rate.

Booking family attribution comes from the saved `booking_client` association. Reassigning the dog does not move historical monthly totals or invoice defaults to the new family. The frontend uses current dog ownership only for legacy bookings without a saved association; an unavailable historical family name stays unknown.

**Options et tarif** lets the owner add a named option immediately, with unit price, currency and integer quantity. Line and revised totals are visible, saved and editable; options can be removed. **Garder pour une prochaine fois** saves a reusable choice but does not change previous options. Each quote uses one currency; unlike currencies are never added together. Clients see the options and total for their own linked booking/request, without owner controls or accounting records.

The quoted total is separate from issued invoices. Copying a booking into a new invoice copies its current options into editable lines. Later changes do not alter that invoice. Existing monthly service summaries still count service units/base rates; extras appear on their individual quotes and on invoice lines once copied, not as extra service days.

## API additions

All `/api/portal/*` writes use the business/revision contract from the README and return the projected account snapshot. Failed validation rolls back the mutation and revision.

Protected requests read the session, active role, family membership and protected data in one transaction. Writes recheck session, role and business binding inside `BEGIN IMMEDIATE`, before advancing the revision, changing data or projecting the response. An early upload check does not authorize its later save: media authorization is repeated after normalization. An already authenticated read may finish with its original snapshot during revocation; it cannot combine that old session with a newly assigned family's records.

| Protected transaction scope | Endpoints under `/api` |
| --- | --- |
| Account and family reads | `GET /state`, `/dogs`, `/dogs/<id>`, `/observations`, `/invites`, `/portal/estimate` |
| Private downloads and albums | `GET /documents/<id>`, `/finance-documents/<id>`, `/client-documents/<id>`, `/blobs/<ref>`, `/media`, `/media/content/<id>` |
| Writes returning account state | `PUT /prefs`, `/observations`, `/invites`, `/daily`, `/knowledge`, `/finance`; `POST /import`, `/documents`, all `/portal/*` actions |
| Other protected writes | `POST /dogs`, `/blobs`, `/auth/logout`, `/media/upload`, `/media/cover`, `/media/delete`, `/media/branding` |

The deterministic races in `tests.test_client_portal` cover reassignment and revocation between early authentication and mutation, predicted revisions, consistent read snapshots, and revocation after media normalization. Public endpoints have no private family projection; `/auth/me` reads only the session and user in a single query.

- `GET /api/public/services`: public price projection, or `rates: null` when unbound.
- `POST /api/auth/access`: `{email, service?}`; service is `day`, `night` or `walk`. `/api/auth/request` has the same closed membership rule outside explicit development signup.
- `GET /api/portal/estimate?dogId=…&service=…&start=…&end=…`: client-owned dog and server-calculated units/base total.
- `POST /api/portal/requests`: `{dogId, service, start, end, note}` from a client.
- `POST /api/portal/decide`: `{id, status}` where status is `accepted` or `declined`; staff only.
- `POST /api/portal/cancel-booking`: `{id}`; owner only. Retains the booking and quote history; see the [cancellation contract](daily-workflows.md#api-contract).
- `POST /api/portal/members`: `{email, role, clientId}`; owner only. Roles are `client` or `trusted-carer`. `revoke` takes `{userId}`.
- `POST /api/portal/professionals`: `{email, dogIds, recordKeys}`; owner only, replaces the [selected professional grant](#selected-professional-access). `POST /api/portal/revoke` also accepts a professional's `{userId}`.
- `POST /api/portal/updates`: `{dogId, text}`; deliberately shared client news. `documents` uses the existing daily upload contract but stores a separate client attachment.
- `GET /api/client-documents/<id>`: client-scoped download, staff within the business, or a professional with an individual grant; internal health/accounting downloads remain forbidden to clients.
- `POST /api/portal/quote`: `{targetId, unitMinor, currency}` completes an unknown base price; owner only.
- `POST /api/portal/extras`: `{targetId, id, label, unitMinor, currency, quantity, reusable}`; empty `id` creates a line. Owner only. `extra-remove` takes `{targetId,id}`.

`portal` in the staff/client state contains requests, shared news/documents, quote totals, visible bookings' `bookingClients` associations, and owner-only member/reusable-option lists. Owners also receive the professional catalogue and selections; professionals receive their selected `sharedRecords` with empty request, quote and family collections. Requests and extras use additive tables. Existing care, daily and finance snapshot formats are retained.

Request dates must produce 1–366 service units; the note is required as a string but may be empty, up to 2,000 characters. Shared news accepts up to 4,000 characters. Shared documents follow the [daily upload fields and 5 MiB PDF/JPEG/PNG limit](daily-workflows.md#api-contract). Quote actions target pending requests or active bookings. Option labels have at most 160 characters, `quantity` is an integer from 1 through 10,000, and `reusable` is a boolean. Unit amounts are integer hundredths from zero through 100,000,000; currencies use the daily contract. A target allows 100 option lines; the reusable list allows 500 choices. Saving an option rejects a base-plus-options total above 1,000,000,000,000 hundredths. These limits and validation are defined in [api/portal.py](../api/portal.py) and [api/quotes.py](../api/quotes.py).

After `DogCareAPI.ready` succeeds, `getPortal()` returns a copy of the projected portal state. `savePortal(action, payload)` queues a guarded mutation and resolves to a success boolean after accepting the returned account state. `estimateRequest({dogId, service, start, end})` resolves to the server quote or `null` on failure; it saves nothing. `getUser()` returns the loaded email/role or `null`. When readiness is false, `isAnonymous()` distinguishes the public welcome from account-load recovery. `logout()` resolves to a success boolean and reloads the page after clearing the session. The [adapter recovery contract](../README.md#mutation-contract) applies to portal saves.

`reloadPortal()` queues an owner-only catalogue refresh from `/api/state` and updates only the portal cache. It resolves to `false` on failure, a changed business/revision or a missing `shareCatalog`, leaving the cache unchanged; it does not reconcile stale account state. Inviter loads this catalogue before showing professional selection controls, so newly saved notes and media are available. A failed refresh offers **Réessayer**; a changed revision requires a full reload after copying unsaved work.

## Isolated verification

Start a disposable loopback API with `DC_DATA_DIR` outside the static root, `DC_AUTH_MODE=development` and `DC_ALLOW_DEMO_SIGNUP=1`. `scripts/seed_private_preview.py --url <loopback-url> --data-dir <temporary-dir>` creates synthetic owner/family access and private local review links. It rejects external hosts, non-temporary stores and stores with non-test email addresses. Seed rates remain unknown. Do not use this helper with real accounts.

The portal regression suites are `tests.test_client_portal`, `tests.test_login_delivery` and `tests.test_welcome_browser`. They cover client isolation, forbidden endpoints, sign-in return in a fresh tab, all service requests, persistence, owner visibility, price snapshots, priced options and mocked delivery failures. `tests.test_booking_cancellation`, `tests.test_login_rate_limit` and `tests.test_static_boundary` cover retained cancellation history, proxy-aware login limits and the frontend allowlist. `tests/test_quote_ui.js` covers quote rendering, option selection and retained request history. Existing care, daily, knowledge, finance, browser and adapter suites remain required; run the [full acceptance checks](../README.md#acceptance-checks). Browser evidence uses real API sessions with synthetic data; it does not verify real-device microphone operation or deployed email delivery.

See [private-beta-release.md](private-beta-release.md) for pinned releases, environment configuration, proxy permissions, backup/restore and the unexecuted deployment checks.

Muse derives its briefing from the loaded dogs, today’s notes and saved planning, including an honest empty state. Account daily stories quote the saved observation without invented meals, mood or exercise statistics. Obsolete personal/clinic/sample-medication details have been removed from the shared application source.
