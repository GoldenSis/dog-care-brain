# DogCare Brain

A polished, dependency-free MVP for a small dog-care business. This premium **Muse** edition is branded for Adine-Sophie and Le Bus des Toutous. It follows Billie Blue and Charlie Rose from daily care capture through owner updates, scheduling, media, and lightweight business reporting.

## Run locally

From this directory, start any static file server:

```bash
python3 -m http.server 4173
```

Then open [http://localhost:4173](http://localhost:4173).

No install or build step is required. Demo observations are stored in the browser's `localStorage`; use **Reset demo** in Settings to restore the original data.

Slice 1 (accounts, SQLite, still zero pip deps) — local only, no email keys:

```bash
python3 api/server.py          # http://127.0.0.1:8787  (sets window.DOGCARE_API)
curl -X POST http://127.0.0.1:8787/api/auth/request \
  -H 'Content-Type: application/json' -d '{"email":"you@example.com"}'
# Open the link in ~/.local/share/dogcare-brain/.dev-outbox/*.json
```

To import existing static-mode records, stop the static server and start account mode on the **same hostname and port** before saving anything to the business account. For the static URL above:

```bash
DC_HOST=localhost DC_PORT=4173 python3 api/server.py
curl -X POST http://localhost:4173/api/auth/request \
  -H 'Content-Type: application/json' -d '{"email":"you@example.com"}'
# Open the outbox link in the same browser profile used for the static app.
```

Use your original scheme, hostname, and port if different. `localhost:4173` and `127.0.0.1:8787` have separate browser storage; the default account URL cannot see records from the static URL. Sign in to an unused business account at the original origin, accept the recording notice if shown, and let the import finish before making account writes. Browser copies stay intact, but an account already used for care writes cannot import them.

The default launcher binds to loopback HTTP; magic links use HTTP and the session cookie is HttpOnly and SameSite=Lax. `DC_INSECURE_COOKIE=0` switches links and cookies to HTTPS for an HTTPS reverse proxy; the stdlib listener itself still serves HTTP.

Private runtime files live under `~/.local/share/dogcare-brain/`: `dogcare.db`, `.dev-outbox/`, and `blobs/`. Set `DC_DATA_DIR` to choose another private directory; `DC_DB`, `DC_OUTBOX`, and `DC_BLOBS` can override individual paths. Every private path must be outside the static document root (`DC_ROOT`, the repository by default); startup rejects paths or symlinks that resolve inside it. If you ran an earlier version, stop it and move `api/dogcare.db` together with any `-wal`/`-shm` files, `.dev-outbox/`, and `api/blobs/` into that private directory before using either launcher. Startup refuses legacy private locations still present in the document root.

Account mode imports populated browser observations, invitation previews, and language once into an unused business account. A one-line notice appears before existing recordings transfer. Cancel leaves browser data intact; reload to continue. Failed imports remain retryable and keep capture disabled until account loading succeeds. Any saved care data closes import eligibility, including existing data from an earlier API version. Audio is uploaded separately before the snapshot; JSON requests allow up to 32 MiB to accommodate existing localStorage snapshots, including UTF-8 text. Local browser copies are retained.

Account saves complete before the app clears a draft or reports success. Each API request has a 15-second deadline, including reading the response; a timeout restores interaction and keeps the draft available to edit, copy, or retry. If another tab changes accounts or saves newer care data, the stale tab cannot overwrite it: copy any unsaved draft, reload, then reapply it to the current records. Protected recordings are served with `Cache-Control: no-store`.

When loading older account history, unsupported recording references are omitted while care text and supported account recordings are retained, so later notes can still be saved.

For CLI writes, first read `/api/state` with your session cookie, then include `X-DogCare-Business: <business_id>` and `If-Match: "<revision>"` from that response along with `Content-Type: application/json`. Each care write advances the revision; use the revision returned by the successful response for your next write. Uploads require the business header but do not advance the revision. Observation recording URLs must be `/api/blobs/<ref>`, using the reference returned by an upload; external URLs and inline recordings are rejected. Browser mutations must come from the server's own origin; CLI requests without an `Origin` header remain supported.

## Try the core flow

1. Open **Muse assistant** and ask for today’s briefing, recorded items needing attention, or an owner handoff. Muse answers from deterministic information already held in the browser; it is not connected to a remote AI service.
2. Use a quick action or open **Capture update** from the dashboard or navigation.
3. Choose a dog and type a note, or use **Dictate** to see a voice note transcribed live into the care-note field.
4. Edit the text if needed, review the detected tags, and save the observation.
5. The new structured card appears in the dog's timeline and the owner story preview updates immediately.
6. Open **Handoff** to review a care-continuity summary for either the owner or next carer, follow its evidence links back to today's observations, and check the suggested next-care actions.

Health-watch content is deliberately phrased as factual observation rather than diagnosis. The handoff reminds carers to keep observing and contact the owner or a veterinarian when concerned.

## Try the invite preview flow

1. Open **Invite** from the sidebar or top bar.
2. Choose **Owner** or **Trusted carer**, add a demo name and email, and select share areas.
3. Review the invite-ready summary and create a **pending invite preview**.
4. The pending invite appears locally; no email, WhatsApp, SMS, or notification is sent.

## Try voice notes and social previews

1. Open **Capture update**, add written care context, then choose **Dictate**. Microphone permission is requested only at that point.
2. Watch the duration, stop, play back, and either discard the recording or save it with the care update. Recordings are limited to two minutes. Static mode retains them in browser storage when capacity allows; account mode saves them in the business’s own server account store.
3. Find retained voice notes on the dog's timeline and in **Gallery**.
4. In **Gallery**, preview the clearly labelled Instagram, Facebook, and YouTube access states. These controls do not ask for credentials, connect accounts, make network requests, or post content.

Browsers without `getUserMedia`/`MediaRecorder`, insecure non-localhost contexts, and denied microphone permission receive an inline explanation; typed care capture remains available.

## Product boundaries

This is a local interactive prototype using fictional demo care moments around the named pilot profiles. Muse and AI structuring use deterministic, on-device keyword parsing; neither connects to a remote AI service. Assistant questions stay in the browser.

- **Static mode** (`python3 -m http.server`, no `DOGCARE_API`): care records and retained recordings stay in this browser; saved recordings are never uploaded.
- **Account mode** (`python3 api/server.py`, flag on): care records and recordings are stored in the business’s own account store on the server the business runs, accessible only to signed-in members of that business, never to a third party. The one-time recording import shows a notice before moving existing audio.

Invitation creation remains a pending preview with no delivery. The magic-link mailer writes local `.dev-outbox` files only. Social connections, owner delivery, payments, and cloud sync remain previews or drafts; social previews never collect credentials or post to a network. Slice 2 remains closed: no deployment, keys, prices, or third-party email provider.

Voice transcription uses the browser's built-in speech-recognition feature. Depending on the browser, microphone audio may be processed by the browser provider's speech service; users should check their browser's privacy terms before recording.

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

The browser acceptance checks need only the optional Playwright test dependency:

```bash
uv run --python 3.12 --with playwright python -m unittest discover -s tests -v
```

The suite covers authentication, tenant isolation, safe migration and replacement writes, robots/origin/output boundaries, the premium Muse briefing-to-handoff journey, live voice transcription through editable text into the timeline, and mobile handoff overflow. Browser tests skip with an installation hint when the optional environment is not present; pure crawler-boundary tests always run with the standard library.
