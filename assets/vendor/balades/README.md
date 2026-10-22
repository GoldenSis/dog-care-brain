# Map library for Balades

Loaded on the first map display in **Balades** (recording, saving, an open track or a spot). The track list and Planning links do not load this library; leaving Balades removes the active map.

- MapLibre GL JS 6.13.0: https://github.com/maplibre/maplibre-gl-js (BSD-3-Clause, bundled `LICENSE.txt`). Files copied unchanged from the npm package archive `maplibre-gl-6.13.0.tgz` (archive SHA-256 `fa47c3d6e150e22d4e5af1a238b4b13dadbeab7dd0770efa902d512a87034e48`, npm integrity `sha512-ELXk4h+xl0URFQEnVbAN6MGn61P6jq4amUWHiskLVsvHCaKdf1Zq6G8UNOD0AQ3UaXoL5ECc8ovz8yqYEBGPKw==`). The page imports `maplibre-gl.mjs`, which starts `maplibre-gl-worker.mjs` from the same folder.
- Map tiles and the style come from OpenFreeMap (`https://tiles.openfreemap.org/styles/liberty`, no key). The browser fetches the tiles for the area shown on the map. Tracks, spots and dog names are never sent there.

`manifest.json` records the SHA-256 of each bundled file.
