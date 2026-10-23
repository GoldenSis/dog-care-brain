# Second instance: La Laisse Dog Walker

The instance id and web address stay `nicolasdelalaissedogcare`; what visitors see is Nicolas's business, La Laisse Dog Walker. The templates run a second dog-sitter's instance from the same release as a separate process, with his own system user, data directory, environment file, port and subdomain. Account stores and sessions are separate; both use the read-only code in `/opt/dogcare/current` and may use the same authorised SMTP mailbox. These are operator instructions, not an executed deployment; the templates do not establish a running service, DNS record or delivered email. The common [private-beta procedure](private-beta-release.md) still applies.

| | Le Bus des Toutous | nicolasdelalaissedogcare |
|---|---|---|
| Unit | `dogcare.service` | `dogcare-nicolas.service` |
| User | `dogcare` | `dogcare-nicolas` |
| Port | 18847 | 18848 |
| Data | `/var/lib/dogcare` | `/var/lib/dogcare-nicolas` |
| Env | `/etc/dogcare.env` | `/etc/dogcare-nicolas.env` |
| Backup | `dogcare-backup.timer` 03:15 UTC | `dogcare-nicolas-backup.timer` 03:35 UTC |
| Site | live site | `nicolasdelalaissedogcare.plusdefun.ch` |

Both backup timers allow up to ten minutes of random delay, catch up missed runs, and retain 14 verified local snapshots in their own data directory. Neither configures off-host copies; see [backup and recovery](private-beta-release.md#backup-and-recovery).

## Brand

The brand comes from the API process environment, not from a business record or the artwork settings. Values are trimmed. An unset or blank `DC_BRAND_NAME`, or the exact case-sensitive name `Le Bus des Toutous`, keeps the original brand, owner, Instagram handle, paw and orange palette; the other `DC_BRAND_*` overrides are then ignored. Default CSS/JS responses are the checked-in bytes, and no `window.DOGCARE_BRAND` is injected. Both HTML shells load `brand.js`; its default text mapping leaves copy unchanged.

The plain static server (`python3 -m http.server`) does not read these variables or apply the media exclusion. Use `python3 api/server.py` for a custom instance. Restart the API process after changing its environment file, then reload the browser. A brand change alone does not isolate data: keep the separate store and origin shown above.

| Variable | Effect |
|---|---|
| `DC_BRAND_NAME` | Header, page titles, welcome page, login email subject and signature, GPX creator. |
| `DC_BRAND_SHORT` | Optional short form for both headers, so the name fits a 390 px phone on one line (`La Laisse`). Titles, emails and GPX keep the full name. |
| `DC_BRAND_OWNER` | Name used where the copy names the dog-sitter (greeting, service details, first contact). Blank/unset falls back to the brand name. |
| `DC_BRAND_TAGLINE` | Optional line above the welcome heading, displayed literally in every language. Blank/unset uses the localized owner line, e.g. `Avec <owner> · votre dog-sitter` in French. |
| `DC_BRAND_INSTAGRAM` | Handle, not a URL, for Contact and first-contact links; a leading `@` is removed. Blank/unset omits those links; the copyable contact draft remains. |
| `DC_BRAND_MARK` | `dog` draws an original dog-head silhouette in profile; `sun` draws a sixteen-ray sun. Neither copies a logo file. Other values, including blank/unset, keep the paw. |
| `DC_BRAND_LOGO` | Path to the instance's own logo (`.png`, `.jpg`, `.jpeg`, `.webp`) outside the release, readable by the service user. When the file exists it replaces the mark in both headers and is served at `/brand/logo`; otherwise that URL is 404. |
| `DC_BRAND_CONTENT` | Path to a JSON file with the instance's public copy (see below). Read on every page load. |
| `DC_BRAND_PRIMARY`, `DC_BRAND_DARK`, `DC_BRAND_SECONDARY` | Six-digit `#rrggbb` colours, case-insensitive. Both primary and dark must be valid or the orange palette is retained; missing/invalid secondary falls back to dark. Buttons on the primary use dark text. Secondary supplies decoration and a darkened variant for links, reaching at least 4.5:1 on white. |

The palette remaps the known orange literals listed in `api/brand.py`, including `%23`-encoded hex colours, in served CSS, HTML and JS outside `assets/`. It does not rewrite files on disk, vendored assets, photographs or arbitrary colours. The server adds contrast styles to the HTML shell; it does not check the dark-on-primary contrast of arbitrary supplied palettes. Check that pair and the rendered UI when choosing other colours.

For custom instances, `api/server.py` injects the public object `window.DOGCARE_BRAND` with `name`, `short`, `owner`, `tagline`, `instagram`, `mark`, `logo` and `content` into both HTML shells before `brand.js`. It contains no palette or secrets. `brand.js` exposes `window.DogCareBrand` with the display values `name`, `short`, `owner`, `tagline` and `instagram`, plus `custom`, `markSvg`, `content`, `text()` and `map()`. `map()` transforms interface-copy values recursively (mutating object properties); it must not receive account records. Palette application stays server-side. The workspace favicon receives a generated monogram; the anonymous shell keeps its empty favicon. Neither this object nor `DC_BRAND_NAME` changes the business selected by `DC_PUBLIC_BUSINESS` or the configured SMTP sender/origin.

Any other brand name hides Adine-Sophie's bundled media. The server refuses all `assets/photos/*` and `assets/films/*` (404), the dashboard drops the outdoor journal and photo credits, and the gallery drops her film and photographs while keeping authorised private albums, retained audio and social-access previews. The welcome photo is hidden until the owner publishes a homepage image from Réglages for the business bound by `DC_PUBLIC_BUSINESS`. The settings preview is blank without an image; resetting the artwork restores the welcome without a photo. The bundled files remain in the read-only release on disk but are never served by that instance. See [media publication](media.md).

Brand substitutions apply only to interface copy. Saved dog names, observation titles/text/tags, handoff evidence, shared updates and invoices are not rebranded when they mention another dog-sitter or brand. Observation display and sharing retain the existing translation-dictionary lookup (`tr()` in `app.js`), including localized generated titles such as `Care moment`; stored wording is unchanged. Interface copy uses `t()` to translate and then apply the brand. Muse headings use the configured owner in all five languages, falling back to the brand name. This is text substitution, not a full rewrite of locale grammar; Italian and German gendered dog-sitter wording remains as supplied.

## Instance content

`DC_BRAND_CONTENT` points to a JSON file of public copy, displayed literally in every language. Nicolas's is [`deploy/dogcare-nicolas.content.json`](../deploy/dogcare-nicolas.content.json); edit it and reload, no restart. Every key is optional, and a missing, unreadable or malformed file (or section) falls back to the default interface copy, with one stderr line from the API.

| Key | Effect |
|---|---|
| `hero.heading`, `hero.text` | Welcome heading and line under it. |
| `services[]` | Up to six welcome cards: `id` (lowercase slug, unique), `label`, `detail`, `face` (`terrier`, `pug`, `dalmatian`) and `request`. `request` is the booking kind it creates (`day`, `night` or `walk`); the client request form then only offers the kinds listed. A card whose `id` is `day`, `night` or `walk` also takes the illustration published from Réglages. If any card is invalid, all three default cards are shown. |
| `price` | Shown for every card instead of the account's public rates, e.g. `Tarif à convenir`. |
| `shop.label`, `shop.text` | One line under the services, e.g. what the owner sells. No prices. |
| `about.kicker`, `about.heading`, `about.paragraphs[]`, `about.steps[]` | The "Faisons connaissance" block; up to four paragraphs and steps. |
| `contact.phone`, `contact.email`, `contact.reviews` | A Contact section with `tel:`, `mailto:` and an HTTPS reviews link (plus Instagram). The header's Contact link then scrolls there, and the first-contact dialog offers the phone. |
| `gallery.empty` | The line on the gallery page, which otherwise invites the owner to add photos to each dog's album. |

Nicolas's copy uses only his own public material: the WhatsApp Business profile (most recent, so 2011, 14 years, 3 000+ walks, Tuesday to Friday forest walks, his approach, his name and email), his Instagram accounts and an older Aladom listing (group size, pick-up area, Patagonia, certificate, pack energy, basic training). The old listing's hourly rate is outdated and not shown. Both Google review links seen (`…EEB0` on Instagram, `…EEBM` on WhatsApp) resolved to the same place on 2026-10-24; the file uses the newer one. Balades has no named-place model, so no Bois de Boulogne preset was added.

His palette follows his black-on-white wordmark with one accent, the Sol de Mayo gold `#F6B40E` from his avatar. Near-black `#1A1A1A` on gold measures 9.5:1 and on white 17.4:1, both above WCAG AA; white on gold (1.83:1) is never used for text. A selected service card has a dark border for any custom palette. Screenshots at 390 × 844, before and after: [welcome](review/brand-instance/brand-nicolas-welcome-390.png), [services](review/brand-instance/brand-nicolas-services-390.png), [about](review/brand-instance/brand-nicolas-about-390.png), [contact](review/brand-instance/brand-nicolas-contact-390.png), [dashboard](review/brand-instance/brand-nicolas-dashboard-390.png), [whole page](review/brand-instance/brand-nicolas-welcome-full-390.png); `brand-nicolas-before-*` show the earlier Sol de Mayo version, and `brand-default-*` / `brand-default-before-*` the unchanged default.

## Checks

With the [acceptance prerequisites](../README.md#acceptance-checks) already installed:

```sh
uv run --python 3.12 --with playwright==1.61.0 python -m unittest tests.test_brand_instance -v
```

The nine browser tests use a synthetic account at 390 × 844. They cover unchanged default responses/no brand injection, a custom welcome and gallery without bundled-media requests, the film URL's 404, gold button colour, owner headings in five locales, blank/special-character owner values, literal saved dog names, and observation/generated-title translations without brand substitution or storage changes. They also check overflow and browser errors in the multilingual journeys, the La Laisse content (cards, price text, contact links, request kind, one-line short header), the logo hook and the fallback for an invalid content file. The full discovery command includes this module.

Set `DOGCARE_EVIDENCE_DIR` to retain the five `brand-*-390.png` captures; leave it unset to avoid writing evidence files. The committed default [welcome](review/brand-instance/brand-default-public-390.png) and [dashboard](review/brand-instance/brand-default-dashboard-390.png) are unchanged by the La Laisse work. These local checks do not prove deployed isolation, actual email delivery, every possible palette's contrast or device behavior.

## Server steps

Run on pdf-server as an authorised host action after the PR is merged and released with `release-dogcare.sh`, so `/opt/dogcare/current` contains this change. Copy the templates from the release itself. Check port 18848 is unused and use the common [media runtime gate](private-beta-release.md#media-runtime-gate): `dogcare-nicolas.service` runs the same HEIC/HEVC conversion check before startup, under its own user and private data path.

```sh
R=/opt/dogcare/current/deploy

# 1. User and private data directory
sudo useradd --system --home-dir /var/lib/dogcare-nicolas --shell /usr/sbin/nologin dogcare-nicolas
sudo install -d -o dogcare-nicolas -g dogcare-nicolas -m 0700 /var/lib/dogcare-nicolas

# 2. Environment: copy the authorised SMTP settings privately, never print them
# Replace both mailbox placeholders (DC_SMTP_USER and DC_SMTP_FROM) and the password.
sudo install -o root -g root -m 0600 $R/dogcare-nicolas.env.example /etc/dogcare-nicolas.env
sudoedit /etc/dogcare-nicolas.env
# DC_BRAND_CONTENT already points to the release's deploy/dogcare-nicolas.content.json.
# For his real logo later: sudo install -d -o dogcare-nicolas -m 0700 /var/lib/dogcare-nicolas/brand,
# copy the file there, set DC_BRAND_LOGO and restart.

# 3. Units
sudo install -m 0644 $R/dogcare-nicolas.service $R/dogcare-nicolas-backup.service \
  $R/dogcare-nicolas-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dogcare-nicolas.service
curl -sf http://127.0.0.1:18848/api/health && echo

# 4. Owner for one email (no mail is sent); note the business id it prints
sudo systemd-run --wait --pipe --collect --unit=dogcare-nicolas-bootstrap \
  --property=User=dogcare-nicolas --property=Group=dogcare-nicolas \
  --property=EnvironmentFile=/etc/dogcare-nicolas.env \
  --working-directory=/opt/dogcare/current \
  /usr/bin/python3 api/create_owner.py --email '<nicolas-email>'
# then set DC_PUBLIC_BUSINESS=<business id> in /etc/dogcare-nicolas.env
sudo systemctl restart dogcare-nicolas.service

# 5. Backups: run once, verify, then enable the timer
sudo systemctl start dogcare-nicolas-backup.service
sudo ls /var/lib/dogcare-nicolas/backups
# Replace <snapshot> with the completed snapshot directory listed above.
sudo -u dogcare-nicolas /usr/bin/python3 /opt/dogcare/current/scripts/private_backup.py verify \
  '/var/lib/dogcare-nicolas/backups/<snapshot>'
sudo systemctl enable --now dogcare-nicolas-backup.timer

# 6. Complete the isolated restore drill below before public DNS handover.
# Add the site block only once; on repeat runs, edit the existing block instead.
sudo sh -c "cat $R/dogcare-nicolas.caddy >> /etc/caddy/Caddyfile"
sudo caddy validate --config /etc/caddy/Caddyfile && sudo systemctl reload caddy
# After the approved DNS A/AAAA records point here and the certificate is ready:
curl -s -o /dev/null -w "%{http_code}\n" https://nicolasdelalaissedogcare.plusdefun.ch/
```

The SMTP sender can stay the existing authorised mailbox; set its display name in `DC_SMTP_FROM` separately from the brand. The subject and signature use `DC_BRAND_NAME` automatically. Keep `DC_ALLOW_DEMO_SIGNUP` unset. Follow the [backup verification and isolated restore drill](private-beta-release.md#backup-and-recovery), substituting user `dogcare-nicolas` and data path `/var/lib/dogcare-nicolas`. Each instance needs its own verified snapshot and restore check; neither backup contains the environment file or code.

After DNS, apply the common [public HTTPS checks](private-beta-release.md#https-browser-permissions-and-public-verification) to this origin, including real login delivery and browser permissions. Verify that the welcome page shows La Laisse's services, about text and contact links (if it shows the three default cards, the content file was not read: check the API log). Verify that built-in rendered copy contains no Adine-Sophie, Le Bus des Toutous or `@bus_destoutous`, no bundled-photo/film requests occur, and direct bundled-media URLs return 404. Confirm authorised albums and retained audio work, and that publishing/resetting homepage artwork never restores the original operator's photo. User-authored records may legitimately contain other names; the shared JS source still contains default copy. Verify the default instance separately with its original brand, palette and media, and confirm records and sessions do not cross between the two origins.

## Releases

Both units run from `/opt/dogcare/current`, so one release affects both. Once the second instance is installed, the release procedure must back up both stores before switching that symlink, restart both API units afterwards and verify both origins. Proposed additions to `~/BrainShared/setup/dogcare/release-dogcare.sh` (not applied; these are insertion points, not a standalone release script):

```sh
# Before switching current, next to the existing dogcare pre-release backup.
# Abort the release if either backup fails.
ssh pdf-server "sudo systemctl start dogcare-nicolas-backup.service" || exit 1

# After switching current, alongside the existing dogcare restart/health check.
ssh pdf-server "sudo systemctl restart dogcare-nicolas.service && sleep 2 && curl -fsS http://127.0.0.1:18848/api/health && echo" || exit 1
curl -fsS -o /dev/null -w "nicolas %{http_code}\n" https://nicolasdelalaissedogcare.plusdefun.ch/ || exit 1
```

Rollback must likewise check compatibility with both stores, restore the reviewed code symlink and restart/check both units; preserve both current stores and their snapshots. Do not roll a custom instance back to code without brand support: that would restore the default identity and bundled media. Follow the common [rollback procedure](private-beta-release.md#rollback).

If his beta needs a separate release, use a second symlink, `/opt/dogcare/current-nicolas`, and change `WorkingDirectory` in both `dogcare-nicolas.service` and `dogcare-nicolas-backup.service`, plus `DC_ROOT` in his environment file, to that path. Reload systemd after unit changes, and back up, move, restart and verify that instance independently. No external release script, host or symlink is changed by these instructions.
