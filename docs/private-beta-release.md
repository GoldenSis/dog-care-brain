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

## Media runtime gate

The Python API remains stdlib-only. Phone media conversion additionally requires maintained local executables `ffmpeg`, `ffprobe` and `heif-convert` on the service PATH, with HEVC/H.264 decoders, libx264/AAC/JPEG encoders and JPEG output from libheif. On Ubuntu 24.04, install `libheif-examples` for `heif-convert` and the matching `libheif-plugin-libde265` for HEVC decoding; the plugin brings the required `libde265-0` library. `libheif1` alone supplies neither the command nor a guaranteed HEVC decoder: its HEVC plugin is only a suggested dependency in the reviewed package metadata. Review `apt-get -s --no-install-recommends install libheif-examples libheif-plugin-libde265` and install that minimal package set only during the separately authorized deployment.

The reviewed host probe found FFmpeg 6.1.1 and libheif1 but no `heif-convert`, and its FFmpeg could not decode the synthetic HEIC. A later isolated probe decoded the synthetic photo to a validated 320 × 240 JPEG using extracted official `libheif-examples` and `libheif-plugin-libde265` packages, both version `1.17.6-1ubuntu4.9`, with `libde265-0` version `1.0.15-1ubuntu0.1`. The libheif packages must match the installed `libheif1` version. This was decoder-only proof using private plugin/library paths, not a system installation or a successful API upload. After installation, run the committed runtime gate in the service sandbox and verify a synthetic HEIC API upload, reload and display before DNS handover.

`deploy/dogcare.service` runs `scripts/check_media_runtime.py` before starting the API. This converts the repository's tiny synthetic HEIC photo and HEVC MOV clip through the actual production pipeline and fully validates the generated JPEG/MP4. It fails when dependencies or decoding fail; a version banner is insufficient. The check needs no account, SMTP, network or real media and cleans its private temporary directory. It uses no HEVC encoder, only the required production decoders and output encoders. Run the same check in the intended service sandbox before release:

```sh
sudo systemd-run --wait --pipe --collect --unit=dogcare-media-check \
  --property=User=dogcare --property=Group=dogcare \
  --property=UMask=0077 --property=NoNewPrivileges=true \
  --property=PrivateTmp=true --property=ProtectSystem=strict \
  --property=ProtectHome=true --property=ReadWritePaths=/var/lib/dogcare \
  --working-directory=/opt/dogcare/current \
  /usr/bin/python3 scripts/check_media_runtime.py --directory /var/lib/dogcare
```

The sandbox keeps the release read-only and permits conversion scratch only beneath the private data directory. Decoder subprocesses inherit these restrictions, receive no SMTP environment, and run with file/CPU/descriptor limits plus a 2 GiB address-space limit on Linux. The API allows one media validation or conversion at a time, a total 120-second conversion deadline, a 200 MiB scratch budget, and bounded photo/video inputs; the exact formats are in [media documentation](media.md). Keep the distribution decoder packages updated. A failed runtime gate must be resolved before claiming HEIC/HEVC support on the host; ordinary JPEG/PNG/WebP and existing WebM behavior do not prove phone normalization works.

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

This creates an empty owner business and sends no email. It preserves an existing owner. Record the returned business ID and set `DC_PUBLIC_BUSINESS` to that approved owner business for explicitly published homepage/service artwork and service presentation, even when every rate is unknown. Missing amounts remain “Tarif à convenir”; zero is a real configured free amount. Confirm the actual rates, currency and overnight billing basis with the business before public pricing. Do not use browser-test rates.

The owner registers each family and dog, then links access in **Tous mes outils → Inviter → Accès aux comptes**. A family signs in using **Mon espace**; no invitation email is sent by the linking operation. Unknown email submission never creates an owner or reveals account membership. A first-time visitor can use the verified public Instagram contact route with a selected-service message to copy and send themselves. The app does not claim that external message was sent or that a booking exists.

## Backup and recovery

Install `dogcare-backup.service` and `dogcare-backup.timer`; enable the timer after verifying its first run. It keeps 14 verified complete local snapshots. Local copies protect against a bad edit; they do not protect against host loss. A separately secured off-host backup location is an operational follow-up, not configured by this branch.

```sh
sudo -u dogcare /usr/bin/python3 /opt/dogcare/current/scripts/private_backup.py backup \
  --data-dir /var/lib/dogcare --backup-dir /var/lib/dogcare/backups --keep 14
sudo -u dogcare /usr/bin/python3 /opt/dogcare/current/scripts/private_backup.py verify \
  /var/lib/dogcare/backups/<snapshot>
```

The helper uses SQLite's online backup API, including committed WAL records, then copies the immutable recordings referenced by that copied database. Upload staging files and unreferenced recordings are excluded. Missing referenced recordings fail verification before publishing or pruning snapshots, even if the manifest omits those files. Recording bytes must also match the original SHA-256 prefix in their filenames, so a fresh manifest cannot legitimize preexisting audio corruption. Client, health and accounting documents, private dog media and owner artwork are stored in SQLite and included. Media byte lengths, hashes, cover references and published artwork references are verified before publication or pruning. Each snapshot has an inventory and SHA-256 checksums. Credentials, app code and development outbox are excluded. Symlinks in copied content are rejected. Unknown or corrupt backup directories are retained for inspection rather than pruned.

Before the first real account, drill restoration into a **new** private directory, not over the running store:

```sh
sudo -u dogcare /usr/bin/python3 /opt/dogcare/current/scripts/private_backup.py restore \
  /var/lib/dogcare/backups/<snapshot> --into /var/lib/dogcare/restore-drill
```

The helper verifies checksums and database integrity, refuses any existing destination and does not start a server. Check restored records/audio with the application in a separate isolated environment; do not send login email as part of a restore drill. Retain the drill until reviewed. Take another backup after owner setup and before client onboarding.

For actual data recovery: stop the API and backup timer; preserve the current store including WAL/SHM and blobs; restore into a new sibling directory outside the release root. Review the restored data, move or bind the restored directory into the configured `DC_DATA_DIR`, preserving ownership and the prior store, then start the API and check health and access. Never copy a database over a running WAL database or delete old sidecars as a shortcut. Restoring a snapshot loses later writes and may restore old sessions/access grants; review and revoke restored access where required before reopening. The helper deliberately does not automate this destructive switchover.

## HTTPS, browser permissions and public verification

Use the dedicated `deploy/dogcare.caddy` site, not a global security snippet that disables camera/microphone. The site allows both for the same origin, retains frame/type/referrer protections and sends host-only HSTS without `includeSubDomains`. Browsers still request the person's own permission. Validate the combined Caddyfile on the host before reloading it; preserve other sites.

Keep `DC_HOST=127.0.0.1`, `DC_PORT=18847` and `DC_TRUSTED_PROXY=127.0.0.1` together with this site configuration. The dedicated Caddy on this host must be the public entry point: its `header_up X-DogCare-Client-IP {http.request.remote.host}` overwrites all caller-supplied values with the connecting IP, never an incoming forwarding chain. This uses Caddy's documented [header overwrite](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy#headers) and [remote-host placeholder](https://caddyserver.com/docs/caddyfile/concepts#placeholders). Do not enable this trust option for direct API access or place another proxy/CDN ahead of Caddy without reviewing the trust contract. Processes on the same host are inside this loopback trust boundary; do not expose or forward port 18847 externally.

The API accepts exactly one valid IP literal in that header only when trust is explicitly enabled, the actual listener is bound to `127.0.0.1`, and the socket peer is also `127.0.0.1`. It normalizes IPv6 spellings and IPv4-mapped addresses. Missing, malformed, scoped or duplicate header values fall back to the socket peer. Unset/unsupported trust configuration, non-loopback listeners and untrusted peers always use the socket peer; `Forwarded`, `X-Forwarded-For` and `X-Real-IP` are never consulted. Reconcile the private environment with these settings before installation, and verify that remote hosts cannot reach the API port.

Only after the service, backups and configuration are verified should the separately authorized DNS action route the public name to this host. Keep the previous Pages DNS target recorded. Allow for the existing DNS TTL and certificate issuance; do not claim a public beta from a loopback screenshot.

Before inviting real users, verify on the final public HTTPS URL:

1. Health comes from the API and the intended release renders with **by Plus de Fun**. The public page loads no private state.
2. A consented synthetic owner/family can receive real mail in a controlled mailbox. Check the canonical link, TLS delivery, single-use/15-minute expiry and Secure/HttpOnly session cookie. SMTP unit tests prove adapter behavior, not inbox receipt.
3. Unknown email gets conditional text and a first-contact route, no account or link. Invited family sees only its dogs, shared files and quotes. Cross-family IDs and direct finance/health originals are forbidden.
4. Each service returns through login to dates/dog, saves a pending request and appears for the owner. Extras persist, total correctly and remain owner-editable only. No payment is taken.
5. On desktop and phone, test navigation and actual microphone/camera permission plus recording/upload. Local automated captures do not prove device permissions under the deployed proxy.
6. The backup timer succeeds and the restored snapshot contains the expected synthetic records and audio.

Production login limits remain 50 attempts/hour per client IP and 5 per email address, shared across both login routes. Before release, use synthetic unknown addresses to verify that two clients through Caddy have separate IP counters, that an exhausted client remains limited, and that forged IP headers do not change its counter. Known and unknown members retain the same public acknowledgment. Local API regressions do not establish the deployed proxy configuration; monitor login failures after that verification.

Existing device-local records stay in that browser. Do not import or overwrite them as part of deployment. Muse suggestions, social/invitation previews and external integrations retain their documented existing limits; release communication must not describe them as automatic external actions.

## Rollback

Keep the preceding code directory and a pre-upgrade private snapshot. For code rollback, verify schema compatibility before repointing `current` to the prior tested release and restarting this service. Do not assume an old static-only or demo-signup commit is an acceptable authenticated backend. For the first install there is no prior API release: stop the new service and use the recorded Pages DNS target. Preserve all private data. Validate Caddy before removing/reloading only this site's block. No Git history rewrite, merge or deletion of private data is part of rollback.

Record actual infrastructure/credential/recovery changes in the operator's established recovery runbook when executed. This document and the templates do not assert that any host, DNS, mailbox or backup has been changed.
