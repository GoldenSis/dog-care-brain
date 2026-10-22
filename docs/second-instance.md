# Second instance: nicolasdelalaissedogcare

A second dog-sitter runs the same release as a separate process, with his own system user, data directory, environment file, port and subdomain. Nothing is shared with Le Bus des Toutous except the read-only code in `/opt/dogcare/current`.

| | Le Bus des Toutous | nicolasdelalaissedogcare |
|---|---|---|
| Unit | `dogcare.service` | `dogcare-nicolas.service` |
| User | `dogcare` | `dogcare-nicolas` |
| Port | 18847 | 18848 |
| Data | `/var/lib/dogcare` | `/var/lib/dogcare-nicolas` |
| Env | `/etc/dogcare.env` | `/etc/dogcare-nicolas.env` |
| Backup | `dogcare-backup.timer` 03:15 UTC | `dogcare-nicolas-backup.timer` 03:35 UTC |
| Site | live site | `nicolasdelalaissedogcare.plusdefun.ch` |

## Brand

The brand comes from the environment. Leaving `DC_BRAND_NAME` unset, or setting it to `Le Bus des Toutous`, serves today's site unchanged: the only difference is a `brand.js` script tag that does nothing for the default.

| Variable | Effect |
|---|---|
| `DC_BRAND_NAME` | Header, page titles, welcome page, login email subject and signature, GPX creator. |
| `DC_BRAND_OWNER` | First name used where the copy names the dog-sitter (greeting, service details, first contact). Falls back to the brand name. |
| `DC_BRAND_TAGLINE` | Optional line above the welcome heading. Defaults to "Avec <owner> · votre dog-sitter". |
| `DC_BRAND_INSTAGRAM` | Handle for the Contact links. Without it, the links are left out. |
| `DC_BRAND_MARK` | `sun` draws a plain sixteen-ray sun instead of the paw. |
| `DC_BRAND_PRIMARY`, `DC_BRAND_DARK`, `DC_BRAND_SECONDARY` | `#rrggbb` palette replacing the orange family in served CSS, HTML and JS. Buttons on the primary use the dark colour for text. The secondary is decorative; links in it are darkened until they reach 4.5:1 on white. |

Any other brand name hides Adine-Sophie's content. The server refuses `assets/photos/*` and `assets/films/*` (404), the dashboard drops the outdoor journal and photo credits, the gallery keeps only the instance's own uploaded albums, and the welcome photo stays empty until the owner publishes a homepage image from Réglages. The files remain in the read-only release on disk but are never served by that instance.

Brand substitutions apply only to interface copy. Authored records, including observation text, handoffs, shared updates and invoices, keep their original wording even when they mention another dog-sitter or brand. Muse headings use the configured owner in every language, falling back to the brand name.

Nicolas's palette is the Sol de Mayo: gold `#F6B40E`, sun brown `#85340A`, celeste `#74ACDF`. Brown on gold measures 4.59:1 and passes WCAG AA; white on gold (1.83:1) and celeste text on white (2.41:1) do not, which is why the dark colour carries button text and celeste only appears as decoration. Screenshots at 390 px: [public](review/brand-instance/brand-nicolas-public-390.png), [dashboard](review/brand-instance/brand-nicolas-dashboard-390.png), [gallery](review/brand-instance/brand-nicolas-gallery-390.png).

## Server steps

Run on pdf-server after the PR is merged and released with `release-dogcare.sh`, so `/opt/dogcare/current` contains this change. Copy the templates from the release itself.

```sh
R=/opt/dogcare/current/deploy

# 1. User and private data directory
sudo useradd --system --home-dir /var/lib/dogcare-nicolas --shell /usr/sbin/nologin dogcare-nicolas
sudo install -d -o dogcare-nicolas -g dogcare-nicolas -m 0700 /var/lib/dogcare-nicolas

# 2. Environment: copy SMTP host/user/password from /etc/dogcare.env by hand, never print them
sudo install -o root -g root -m 0600 $R/dogcare-nicolas.env.example /etc/dogcare-nicolas.env
sudoedit /etc/dogcare-nicolas.env

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
sudo systemctl enable --now dogcare-nicolas-backup.timer

# 6. Caddy: append the site block, validate, reload (DNS A/AAAA for the subdomain must point here first)
sudo sh -c "cat $R/dogcare-nicolas.caddy >> /etc/caddy/Caddyfile"
sudo caddy validate --config /etc/caddy/Caddyfile && sudo systemctl reload caddy
curl -s -o /dev/null -w "%{http_code}\n" https://nicolasdelalaissedogcare.plusdefun.ch/
```

The SMTP sender can stay the existing authorised mailbox; only the display name in `DC_SMTP_FROM` changes. Keep `DC_ALLOW_DEMO_SIGNUP` unset. After DNS, check on the public URL that no page or request mentions Adine-Sophie, Le Bus des Toutous or `@bus_destoutous`, and that the gallery shows only his own albums.

## Releases

Both units run from `/opt/dogcare/current`, so one release serves both. The release script needs one more step after it restarts `dogcare.service`. Proposed addition to `~/BrainShared/setup/dogcare/release-dogcare.sh` (not applied):

```sh
ssh pdf-server "sudo systemctl start dogcare-nicolas-backup.service; sudo systemctl restart dogcare-nicolas.service && sleep 2 && curl -sf http://127.0.0.1:18848/api/health && echo"
curl -s -o /dev/null -w "nicolas %{http_code}\n" https://nicolasdelalaissedogcare.plusdefun.ch/
```

The backup line belongs next to the existing pre-release backup, and the rollback line should restart both units. If his beta ever needs to stay on an older release, give him a second symlink, `/opt/dogcare/current-nicolas`, change `WorkingDirectory` and `DC_ROOT` in his unit and env to it, and move that link separately.
