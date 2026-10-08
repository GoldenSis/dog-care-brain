# Private beta release — Le Bus des Toutous by Plus de Fun

This is a reviewable release procedure, not an executed deployment. The API, not a static Pages publish, provides accounts and private records. Keep the existing static site available as a DNS rollback target. Merging a PR does not install this service.

## Candidate and configuration

Use one reviewed, clean commit containing the welcome, client portal and SMTP adapter. Record its full SHA, validation result, archive SHA-256 and previous release in the operator's release record. Export with `git archive --format=tar --output=<private-release.tar> <sha>`. Never copy a working tree, local database, outbox, test evidence or credentials into the release. The deployment templates are in [deploy](../deploy/); they have not been validated against the live host by this code change.

The API publishes only its explicit frontend file allowlist (`api/server.py:STATIC_FILES`). Repository docs, dotfiles, deployment files, tests, scripts and asset provenance metadata are not served, even to signed-in users. Add new intended frontend assets to that list deliberately and run `tests.test_static_boundary`. Protected record downloads remain separate authorized API routes. The development-only plain static server does not provide this boundary and is not the beta server.

The standard layout is:

- `/opt/dogcare/releases/<sha>`: root-owned, read-only application release.
- `/opt/dogcare/current`: symlink to the selected release.
- `/var/lib/dogcare`: private data, owned by the dedicated `dogcare` system user, mode `0700`.
- `/etc/dogcare.env`: root-owned `0600` environment file; never committed, printed or served.
- `127.0.0.1:18847`: API listener. Recheck that it is unused before installation.

Create the system user and directories, extract only the pinned archive into its release directory and install `deploy/dogcare.service`. The service account needs read access to the release and write access only to its private data. It does not need access to another app's secrets. Run only one API service against a store.

Copy `deploy/dogcare.env.example` privately and replace the placeholders. The existing authorized Infomaniak sender uses `mail.infomaniak.com:2525` with `DC_SMTP_TLS=starttls`. Reuse that verified real mailbox for the authenticated user and visible From address; keep **by Plus de Fun** in the display identity. Do not invent a no-reply mailbox. Map the existing transport's host, port, user and password into `DC_SMTP_HOST`, `DC_SMTP_PORT`, `DC_SMTP_USER` and `DC_SMTP_PASSWORD` at installation. Keep the existing sender's password private; do not make this app open the other service's environment file. `EnvironmentFile=` handles the values; do not put passwords in systemd `Environment=` commands or shell history.

SMTP always verifies the TLS certificate. The envelope sender matches the authenticated mailbox. Messages contain Date, Message-ID and Auto-Submitted headers. `DC_PUBLIC_ORIGIN` must be the canonical HTTPS origin and `DC_INSECURE_COOKIE=0`. Leave `DC_ALLOW_DEMO_SIGNUP` unset. Never enable development authentication on this host. Production delivery failure invalidates the new login token; there is no debug-outbox fallback.

The templates use the standard `dogcare.db` and `blobs/` paths. If `DC_DB` or `DC_BLOBS` is overridden, adapt and test the backup contract before deploying; the supplied helper intentionally targets the standard layout.

## Pre-public checks and bootstrap

Install the service and backup units, reload systemd and start the API only as part of the separately authorized host action. Verify loopback `GET /api/health` returns `ok: true`; health alone does not prove mail delivery. Check the service journal without copying credentials or login links into reports.

Create the owner deliberately, with the service's private environment and user. For example, an operator can use a transient systemd unit to load the root-only env file without sourcing it or exposing a password in arguments:

```sh
sudo systemd-run --wait --pipe --collect --unit=dogcare-bootstrap \
  --property=User=dogcare --property=Group=dogcare \
  --property=EnvironmentFile=/etc/dogcare.env \
  --working-directory=/opt/dogcare/current \
  /usr/bin/python3 api/create_owner.py --email '<approved-owner-address>'
```

This creates an empty owner business and sends no email. It preserves an existing owner. Record the returned business ID and set `DC_PUBLIC_BUSINESS` to that ID only when its configured service rates should appear publicly. Missing amounts remain “Tarif à convenir”; zero is a real configured free amount. Confirm the actual rates, currency and overnight billing basis with the business before public pricing. Do not use browser-test rates.

The owner registers each family and dog, then links access in **Tous mes outils → Inviter → Accès aux comptes**. A family signs in using **Mon espace**; no invitation email is sent by the linking operation. Unknown email submission never creates an owner or reveals account membership. A first-time visitor can use the verified public Instagram contact route with a selected-service message to copy and send themselves. The app does not claim that external message was sent or that a booking exists.

## Backup and recovery

Install `dogcare-backup.service` and `dogcare-backup.timer`; enable the timer after verifying its first run. It keeps 14 verified complete local snapshots. Local copies protect against a bad edit; they do not protect against host loss. A separately secured off-host backup location is an operational follow-up, not configured by this branch.

```sh
sudo -u dogcare /usr/bin/python3 /opt/dogcare/current/scripts/private_backup.py backup \
  --data-dir /var/lib/dogcare --backup-dir /var/lib/dogcare/backups --keep 14
sudo -u dogcare /usr/bin/python3 /opt/dogcare/current/scripts/private_backup.py verify \
  /var/lib/dogcare/backups/<snapshot>
```

The helper uses SQLite's online backup API, including committed WAL records, then copies the immutable recordings referenced by that copied database. Upload staging files and unreferenced recordings are excluded. Missing referenced recordings fail verification before publishing or pruning snapshots, even if the manifest omits those files. Client, health and accounting documents, private dog media and owner artwork are stored in SQLite and included. Media byte lengths, hashes, cover references and published artwork references are verified before publication or pruning. Each snapshot has an inventory and SHA-256 checksums. Credentials, app code and development outbox are excluded. Symlinks in copied content are rejected. Unknown or corrupt backup directories are retained for inspection rather than pruned.

Before the first real account, drill restoration into a **new** private directory, not over the running store:

```sh
sudo -u dogcare /usr/bin/python3 /opt/dogcare/current/scripts/private_backup.py restore \
  /var/lib/dogcare/backups/<snapshot> --into /var/lib/dogcare/restore-drill
```

The helper verifies checksums and database integrity, refuses any existing destination and does not start a server. Check restored records/audio with the application in a separate isolated environment; do not send login email as part of a restore drill. Retain the drill until reviewed. Take another backup after owner setup and before client onboarding.

For actual data recovery: stop the API and backup timer; preserve the current store including WAL/SHM and blobs; restore into a new sibling directory outside the release root. Review the restored data, move or bind the restored directory into the configured `DC_DATA_DIR`, preserving ownership and the prior store, then start the API and check health and access. Never copy a database over a running WAL database or delete old sidecars as a shortcut. Restoring a snapshot loses later writes and may restore old sessions/access grants; review and revoke restored access where required before reopening. The helper deliberately does not automate this destructive switchover.

## HTTPS, browser permissions and public verification

Use the dedicated `deploy/dogcare.caddy` site, not a global security snippet that disables camera/microphone. The site allows both for the same origin, retains frame/type/referrer protections and sends host-only HSTS without `includeSubDomains`. Browsers still request the person's own permission. Validate the combined Caddyfile on the host before reloading it; preserve other sites.

Only after the service, backups and configuration are verified should the separately authorized DNS action route the public name to this host. Keep the previous Pages DNS target recorded. Allow for the existing DNS TTL and certificate issuance; do not claim a public beta from a loopback screenshot.

Before inviting real users, verify on the final public HTTPS URL:

1. Health comes from the API and the intended release renders with **by Plus de Fun**. The public page loads no private state.
2. A consented synthetic owner/family can receive real mail in a controlled mailbox. Check the canonical link, TLS delivery, single-use/15-minute expiry and Secure/HttpOnly session cookie. SMTP unit tests prove adapter behavior, not inbox receipt.
3. Unknown email gets conditional text and a first-contact route, no account or link. Invited family sees only its dogs, shared files and quotes. Cross-family IDs and direct finance/health originals are forbidden.
4. Each service returns through login to dates/dog, saves a pending request and appears for the owner. Extras persist, total correctly and remain owner-editable only. No payment is taken.
5. On desktop and phone, test navigation and actual microphone/camera permission plus recording/upload. Local automated captures do not prove device permissions under the deployed proxy.
6. The backup timer succeeds and the restored snapshot contains the expected synthetic records and audio.

The API's IP rate limit currently sees the loopback proxy address, so its 50 attempts/hour limit is shared behind Caddy; address-specific limits still apply. Do not trust an arbitrary forwarded IP header to bypass it. Monitor login failures during the small private beta.

Existing device-local records stay in that browser. Do not import or overwrite them as part of deployment. Muse suggestions, social/invitation previews and external integrations retain their documented existing limits; release communication must not describe them as automatic external actions.

## Rollback

Keep the preceding code directory and a pre-upgrade private snapshot. For code rollback, verify schema compatibility before repointing `current` to the prior tested release and restarting this service. Do not assume an old static-only or demo-signup commit is an acceptable authenticated backend. For the first install there is no prior API release: stop the new service and use the recorded Pages DNS target. Preserve all private data. Validate Caddy before removing/reloading only this site's block. No Git history rewrite, merge or deletion of private data is part of rollback.

Record actual infrastructure/credential/recovery changes in the operator's established recovery runbook when executed. This document and the templates do not assert that any host, DNS, mailbox or backup has been changed.
