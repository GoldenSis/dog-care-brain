# Balades

Open it through **Tous mes outils → Balades**. It is a separate space from the daily workspace: it holds walk tracks and the spots ("repères") along them. Planning only gains one action per saved walk, described below. Phase 1 is private to the business: in account mode the owner and trusted carers can record, import, edit, delete and export; clients and professionals have no access (the API answers 403). Static mode has no roles, so anyone using that browser can use it. There is no entry on the public site.

## Recording a walk

**Enregistrer une balade** starts `navigator.geolocation.watchPosition` with high accuracy. A fix is kept only when its reported accuracy is 35 m or better and it is at least 4 m from the last kept point. The screen shows distance, elapsed time, kept points and the last accuracy. **Terminer la balade** opens the save form (name, date, dogs picked from the registered dogs); **Abandonner** asks for confirmation and erases the recording.

The page asks for a Screen Wake Lock while recording and says whether it got one. **A web page cannot record with the screen off.** iOS Safari and Chrome pause geolocation when the phone locks or the page goes to the background, so the screen must stay on for the whole walk. For long walks, record with a phone GPS app and import its GPX file. Recording through a locked screen needs a native app.

The in-progress recording is written to this browser every 10 seconds (IndexedDB `dogcare-balades-v1`, store `drafts`, one entry per account or one for static mode). After a reload or crash, the list offers **Reprendre l’enregistrement**, **Terminer maintenant** or **Abandonner**. Elapsed time is wall-clock time since the start, so a resumed recording counts the gap. The draft never leaves the browser; it is deleted when that recording is saved or abandoned. Importing another track preserves it. If local persistence fails, a warning stays visible through recording, finishing and cancelling the save form; the recording remains in memory and can be resumed while the page stays open. Leaving the Balades page does not stop a recording.

## Import and export

**Importer un GPX** reads the file in the browser. Track points (`trk/trkseg/trkpt`) are used; a file without them falls back to route points (`rte/rtept`). All segments become one line, so a gap between segments is drawn and measured as a straight line. Each `wpt` becomes a spot of type **Pause** with its name as the note, unless its `<type>` is one of the Balades types (files exported here), in which case the type, `<desc>` (note) and `<cmt>` (official rule of a **Toléré** spot) come back as they were. The name comes from `metadata/name`, then `trk/name`, then the file name; the date from the first timed point, else today; the duration from the first and last timed points.

Files are refused with a French message when they are larger than 2 MiB, are not well-formed XML, declare a DOCTYPE, are not GPX, have a point without valid coordinates, have fewer than two points, more than 20,000 points or more than 200 waypoints. Notes from foreign files are cut to 500 characters.

**Exporter le GPX** downloads GPX 1.1 with the track (`trkpt` with `time` when known) and every spot as a `wpt` carrying `<time>` (the date noted), `<name>` (type label), `<desc>` (note), `<cmt>` (official rule, Toléré only) and `<type>` (`pause`, `danger`, `interdit`, `laisse` or `tolere`).

## Spots

Open a track, choose **Ajouter un repère**, then tap the map (or **Placer au centre de la carte**). Types: **Pause** (water, lake, shade, bench…), **Danger**, **Chiens interdits**, **Laisse obligatoire** and **Toléré**. Each has a note of up to 500 characters and the date it was noted. A **Toléré** spot also has a **Règle officielle**; the two are shown side by side with "Une pratique constatée sur place, pas une autorisation." Markers use a distinct colour and icon per type, a legend sits under the map, and each marker is a button whose accessible name is the type and note. The list of spots under the map is the keyboard-accessible version. Latitude and longitude can be corrected in the form, which is also how a spot is placed when the map cannot be shown.

## Link to a walk in Planning

Under the walk checklist in **Planning**, each walk saved for the selected day shows **Ajouter le tracé**. It opens Balades for that dog and date: pick an existing track (**Relier à cette balade**), or record or import one; the new track is linked when saved. Afterwards the walk shows **Voir le tracé**. The link is stored on the track as `walkRefs: [{date, dogId}]` and the dog is added to the track's dogs. One track can serve several dogs on the same walk, and a dog's walk on a given day links to one track at most (relinking moves it). The daily snapshot is unchanged; unticking a walk in Planning leaves the link on the track, visible under **Balades du Planning** with **Retirer**.

## Map and privacy

The map uses MapLibre GL JS 6.13.0, bundled under `assets/vendor/balades/` (see its README and checksums) and loaded only when the Balades page needs a map. The basemap is OpenFreeMap's `liberty` style (`https://tiles.openfreemap.org/styles/liberty`, no key). The browser fetches the style, fonts and tiles for the area being viewed from OpenFreeMap, which therefore learns the approximate area shown and the viewer's IP address. Tracks, spots, notes and dog names are never sent there. If WebGL is missing, the page says the map cannot be shown; tracks and spots still work. The deployment's `Permissions-Policy` must allow `geolocation=(self)` (see `deploy/dogcare.caddy`).

## Storage and API contract

`balades-model.js` and `api/balades.py` validate the same snapshot:

```json
{ "version": 1, "tracks": [ {
  "id": "…", "name": "Parc de Saint-Cloud", "date": "2026-10-21", "dogs": ["billie"],
  "points": [[48.8402, 2.219, 1792900000]], "durationSec": 3600, "source": "record",
  "walkRefs": [{ "date": "2026-10-21", "dogId": "billie" }],
  "spots": [{ "id": "…", "type": "tolere", "lat": 48.84, "lon": 2.22, "note": "…", "rule": "…", "noted": "2026-10-20" }]
} ] }
```

All fields are required and extra fields are rejected. IDs follow the accounting identifier format (1–81 ASCII letters, digits, `_` or `-`). `name` is nonblank, at most 120 code points; text follows the accounting control-character rules. `points` are `[latitude, longitude, unix seconds or null]`, 2 to 20,000 per track. `durationSec` is `null` or 0–604,800. `source` is `record` or `import`. Up to 50 dogs and 50 walk links per track; each link's dog must be among the track's dogs, and a date/dog pair appears once in the whole snapshot. Up to 200 spots per track; `rule` must be empty unless the type is `tolere`. Limits per business: 500 tracks, 600,000 points and 30 MiB of compact UTF-8 JSON in total, including all spot notes and rules. Both validators enforce the aggregate size; the browser reports the capacity error before sending. This leaves room for the request envelope under the API's 32 MiB body cap.

Static mode stores the snapshot in IndexedDB `dogcare-balades-v1` (store `state`). A save compares the stored text with the version this tab loaded inside one readwrite transaction, so a stale tab cannot overwrite another tab's work.

Account mode uses the additive table `business_balades (business_id, snapshot, revision)`. Balades have their own revision so recording a walk never conflicts with Planning or care edits, and the shared care revision is untouched.

- `GET /api/balades` (session cookie) → `{ "ok": true, "business_id", "revision", "balades" }` for owner and trusted carer; 403 for client and professional; 401 when signed out. Balades are not part of `/api/state`.
- `PUT /api/balades` with `{ "balades": <full snapshot> }`, `X-DogCare-Business: <business_id>` and `If-Match: "<balades revision>"`. Success returns the same shape with the next revision. A stale revision returns 409 (428 without `If-Match`) with `"conflict": true`; invalid snapshots return 400; nothing is written in either case. The UI then offers **Recharger et réessayer**, which reloads and reapplies the pending change to its original target. Reload and replay share one busy state; navigating away cancels an unsubmitted retry. Failed saves retain form values, and a target deleted elsewhere produces an explicit message without discarding unsaved input.

## Checks

```sh
node --test tests/test_balades_model.js
python3 -m unittest tests.test_balades_api -v
uv run --python 3.12 --with playwright==1.61.0 python -m unittest tests.test_balades_browser -v
```

The browser tests run both modes at 390 × 844 with mocked geolocation and a stubbed map style (no network): they record a walk, place a **Toléré** spot by tapping the map, reload, export and import GPX, link a Planning walk, and check overflow and the console. Regressions cover abandoned conflict retries, deleted targets, failed-save input, protected recording drafts, failed draft persistence, delayed map loading and snapshot reuse in Planning. Node and Python checks include aggregate UTF-8 capacity below the individual count limits. Headless Chromium needs `--use-angle=swiftshader --enable-unsafe-swiftshader` for WebGL. A real phone, a real GPS fix, wake-lock behaviour and live OpenFreeMap tiles are not exercised.
