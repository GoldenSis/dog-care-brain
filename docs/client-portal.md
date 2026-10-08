# Public welcome and private client space

The API app opens on a public French welcome for **Le Bus des Toutous · by Plus de Fun**. Day care, an overnight stay and a walk each reveal their own explanation and configured price. Contact links to the already documented public Instagram profile. **Mon espace** requests a personal sign-in link. The anonymous API homepage loads only the welcome scripts; the workspace `app.js` requires authentication. No private snapshot is fetched before authentication. First-time visitors also have a first-contact route in the request dialog: a selected-service message they can copy and send themselves through the verified public Instagram profile. This is an external conversation, not a saved in-app request or an account grant.

The service choice travels in the login link, so a link opened in a fresh tab returns to the request form. A client chooses their dog, service and dates; the API calculates the estimate. Submission records a **request awaiting confirmation**, not a confirmed reservation or a payment. The owner sees the request and can accept or decline it. Acceptance creates an ordinary saved booking, retaining the quoted service rate. A missing rate remains unknown until the owner explicitly completes it.

## Accounts and access

Public email submission only signs in known active members. It never grants owner status or creates a new business. Existing owners and language preferences are retained. Newly bootstrapped owners start in French. Bootstrap a new, empty owner account deliberately with `python3 api/create_owner.py --email <owner-email>` against the intended private `DC_DATA_DIR`; this does not send mail. Disable demo signup first.

The owner registers a client and their dog in the existing daily records, then opens **Tous mes outils → Inviter → Accès aux comptes**. An email can be linked to that client's dogs or added as a trusted carer. Saving an access grant does not send an email. The person then requests their own login link from **Mon espace**. Revocation and reassignment invalidate that member's existing sessions. An account belonging to another business or an existing owner cannot be reassigned through this control.

| Role | Available records and actions |
| --- | --- |
| Visitor | Public descriptions and explicitly published service rates; no private account state. |
| Client | Their linked dogs, bookings, family requests and quotes, explicitly shared news and client documents. Can request a booking and change their language. |
| Trusted carer | Internal care records, planning and explicitly shared news/documents. Cannot manage access, set prices/extras, or read accounting originals. |
| Owner | All existing care functions plus access grants, prices/extras and private accounting. |

Authorization is enforced by the API for reads, writes and attachment downloads, including direct/guessed URLs. Client news and documents are separate from internal notes, health documents and accounting originals. Saved client-facing records retain their family audience; moving a dog to another client does not transfer the former family’s requests, quotes or shared files. Existing daily bookings acquire their saved client association during the additive schema upgrade. In account mode, Inviter opens real membership controls. Previously saved invitation previews remain in a read-only disclosure and do not grant access. Static mode retains its explicitly labeled preview form. Account settings show the account and access/rate actions; the demo reset exists only in static mode. Static mode retains the existing local workspace, without a simulated client login or server membership system.

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
| `DC_SMTP_HOST`, `DC_SMTP_USER`, `DC_SMTP_PASSWORD`, `DC_SMTP_FROM` | Required SMTP connection and sender configuration. Supply secrets through the deployment's private environment. |
| `DC_SMTP_TLS` / `DC_SMTP_PORT` | `ssl` / 465 by default; `starttls` / 587 also supported; the deployment template explicitly selects the authorized Infomaniak transport on port 2525. Unencrypted delivery is not supported. |

Links are single-use with a 15-minute lifetime. Production attempts are bounded per address and source IP. Two delivery workers handle at most 128 queued or active requests; an exhausted queue is logged privately and keeps the same public acknowledgment. Tokens remain unusable until delivery succeeds. Messages use the authenticated mailbox as envelope sender, matching the visible From address, with Date, Message-ID and Auto-Submitted headers. Unknown addresses receive the same conditional acknowledgment as known members without receiving a token or acquiring an account. SMTP latency and delivery failure never change that acknowledgment. Tokens, credentials and SMTP response details are not returned in API bodies. Tests mock both TLS transports; they do not establish that an actual host can deliver email. Deployment, real credentials, sender authorization, mailbox receipt and HTTPS must be verified separately before inviting real users.

## Prices and options

Existing **Comptabilité → Réservations et tarifs** remains the rate editor. `DC_PUBLIC_BUSINESS=<business-id>` explicitly selects the business whose three base rates may be published by `/api/public/services`. Without this binding no account's rates are published. This endpoint contains only currency and the three rate values, never dogs or financial records. No prices are bundled with this design.

Money reuses the daily/accounting integer-hundredths contract, displayed with two decimal places. Unknown is distinct from zero. Day/walk ranges count inclusive calendar dates; nights count departure minus arrival. The UI makes no promised schedule or availability. A request snapshots the configured unit rate; changing the rate list does not reprice existing requests or bookings. Completing an unknown rate requires an explicit owner action. The amount is a quoted price, not an automatic charge.

Trusted carers create bookings with the owner's configured rate applied by the server. Their form shows a read-only estimate and submits a null price for new bookings; an unconfigured service stays unknown. They cannot supply prices, change base rates or alter an existing agreement.

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
- `POST /api/portal/members`: `{email, role, clientId}`; owner only. Roles are `client` or `trusted-carer`. `revoke` takes `{userId}`.
- `POST /api/portal/updates`: `{dogId, text}`; deliberately shared client news. `documents` uses the existing daily upload contract but stores a separate client attachment.
- `GET /api/client-documents/<id>`: client-scoped download or staff within the business; internal health/accounting downloads remain forbidden to clients.
- `POST /api/portal/quote`: `{targetId, unitMinor, currency}` completes an unknown base price; owner only.
- `POST /api/portal/extras`: `{targetId, id, label, unitMinor, currency, quantity, reusable}`; empty `id` creates a line. Owner only. `extra-remove` takes `{targetId,id}`.

`portal` in the state contains requests, shared news/documents, quote totals, visible bookings' `bookingClients` associations, and owner-only member/reusable-option lists. Requests and extras use additive tables. Existing care, daily and finance snapshot formats are retained.

## Isolated verification

Start a disposable loopback API with `DC_DATA_DIR` outside the static root, `DC_AUTH_MODE=development` and `DC_ALLOW_DEMO_SIGNUP=1`. `scripts/seed_private_preview.py --url <loopback-url> --data-dir <temporary-dir>` creates synthetic owner/family access and private local review links. It rejects external hosts, non-temporary stores and stores with non-test email addresses. Seed rates remain unknown. Do not use this helper with real accounts.

The new regression suites are `tests.test_client_portal`, `tests.test_login_delivery` and `tests.test_welcome_browser`. They cover client isolation, forbidden endpoints, sign-in return in a fresh tab, all service requests, persistence, owner visibility, price snapshots, priced options and mocked delivery failures. Existing care, daily, knowledge, finance, browser and adapter suites remain required. Browser evidence uses real API sessions with synthetic data; it does not verify real-device microphone operation or deployed email delivery.

See [private-beta-release.md](private-beta-release.md) for pinned releases, environment configuration, proxy permissions, backup/restore and the unexecuted deployment checks.

Muse derives its briefing from the loaded dogs, today’s notes and saved planning, including an honest empty state. Account daily stories quote the saved observation without invented meals, mood or exercise statistics. Obsolete personal/clinic/sample-medication details have been removed from the shared application source.
