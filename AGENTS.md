# AGENTS.md — OpenFlightWall

Guidance for AI coding assistants (and human contributors) working on this repo: a local Python/Flask dashboard that shows nearby flights using only free APIs — keyless by default, with an optional free OpenSky account for a higher rate limit. Two views: a flight-card grid and a Leaflet/OpenStreetMap map.

## Hard Constraints

- **NEVER** suggest paid APIs or services (no FlightAware AeroAPI, no aviation data subscriptions).
- **NEVER** add API keys or credentials to the codebase.
- **All data sources must be free** (keyless preferred): OpenSky (optional free OAuth), hexdb.io, adsbdb.com, Kiwi.com logos, OpenStreetMap tiles, GitHub API (update check only).
- There is no config file for location/radius — those live in the browser. The only optional server config is OpenSky OAuth via `OPENSKY_CLIENT_ID`/`OPENSKY_CLIENT_SECRET` and the update-check opt-out `OFW_UPDATE_CHECK=0` (env or `.env`).
- Before adding a new data source, confirm it is free and requires no key. (Hosted dark map styles such as CARTO and Stadia now require a key, which is why the dark map recolours OSM tiles with CSS instead.)

## Project Layout

```
OpenFlightWall/
├── app.py              # Flask server + data pipeline (edit for backend changes)
├── pyproject.toml      # uv project config (deps: flask, requests, python-dotenv)
├── uv.lock             # Reproducible dependency lockfile
├── site/               # GitHub Pages: landing page + replay demo (see "GitHub Pages" below)
├── .env.example        # Committed template for optional OpenSky OAuth creds
├── .env                # Local secrets — git-ignored, never committed (optional)
└── templates/
    └── index.html      # Single-file frontend (vanilla HTML/CSS/JS + Leaflet CDN)
```

Location and radius are chosen in the browser and passed to `/api/flights` as query params. `.env` (git-ignored) optionally holds OpenSky OAuth credentials; `.env.example` is the committed template.

## Data Pipeline

```
OpenSky anonymous  →  state vectors  (lat/lon/callsign/icao24/alt/speed/heading/vertical_rate/squawk)
hexdb.io           →  aircraft type code from ICAO24 (fallback: adsbdb icao_type)
adsbdb.com route   →  origin/destination airports, IATA flight number, airline name + telephony + IATA
adsbdb.com aircraft→  registration, manufacturer, owner, photo
Kiwi.com CDN       →  airline logo by IATA code (client-side image URL)
computed           →  distance travelled/remaining, progress %, rough ETA
GitHub API         →  latest release / tags (update check only, cached 6 h, OFW_UPDATE_CHECK=0 disables)
```

## Key Functions in app.py

| Function | Purpose |
|---|---|
| `haversine_km(...)` | Great-circle distance (originally ported from TheFlightWall firmware's `GeoUtils.h`) |
| `bearing_deg(...)` | Compass bearing (originally ported from TheFlightWall firmware's `GeoUtils.h`) |
| `bounding_box(lat, lon, radius_km)` | lat/lon bounds for OpenSky query |
| `fetch_state_vectors(center_lat, center_lon, radius_km)` | GET OpenSky, parse states (incl. squawk), filter by radius |
| `extract_airline_icao(callsign)` | `"UAL123"` → `"UAL"` |
| `get_aircraft_type(icao24)` | hexdb.io lookup → ICAO type code |
| `get_route(callsign)` | adsbdb.com → `{origin, destination, flight_iata, airline_name, airline_callsign, airline_iata}` (1 h cached) |
| `get_aircraft_details(icao24)` | adsbdb.com → `{registration, manufacturer, type_code, owner, owner_country, photo, photo_thumb}` (1 h cached) |
| `compute_progress(origin, dest, lat, lon, speed_kmh)` | → `{route_total_km, travelled_km, remaining_km, progress_pct, eta_min}` |
| `_airport_summary(ap)` | Reduce adsbdb airport to iata/icao/name/city/country/country_iso/lat/lon |
| `fetch_flights(center_lat, center_lon, radius_km)` | Orchestrates full pipeline |
| `APP_VERSION` / `_read_app_version()` | Running version, read from `pyproject.toml` (the single source of truth; the Docker image copies it in) |
| `get_latest_version()` | GitHub `/releases/latest`, falling back to the highest `vX.Y.Z` tag while the repo has no releases → `(version, url)`; cached 6 h (30 min on failure) in `_version_cache` |
| `version_info()` | `{current, latest, update_available, url}`; skips GitHub entirely when `update_check_enabled()` is false (`OFW_UPDATE_CHECK=0`) |

## Caching

- `_cache` — full flight list, keyed by rounded (lat, lon, radius), `CACHE_TTL = 30` s. Protects the OpenSky rate limit (~1 req/10s).
- `_route_cache` / `_aircraft_cache` — per-callsign / per-icao24, `ROUTE_CACHE_TTL = 3600` s.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Serves `templates/index.html`; injects `DEFAULT_RADIUS_KM` via a `data-default-radius` body attribute |
| `GET` | `/api/flights?lat&lon&radius` | Enriched JSON array. `lat`/`lon` **required** (400 if missing); `radius` defaults to `DEFAULT_RADIUS_KM` |
| `GET` | `/api/version` | `version_info()` — powers the in-app update toast and the version line in ⚙ Settings |
| `GET` | `/api/config` | OpenSky auth status `{configured, client_id_masked, source, rate:{anonymous, authenticated, last_mode, retry_after}}` (never returns the secret) |
| `POST` | `/api/config` | Body `{client_id, client_secret}` — validates via a token request, then persists to `opensky_creds.json` |
| `DELETE` | `/api/config` | Clears UI-saved creds (reverts to env/anonymous) |

Other backend facts:
- **OpenSky states array** field indices: `0=icao24, 1=callsign, 5=lon, 6=lat, 7=baro_alt, 8=on_ground, 9=velocity, 10=heading, 11=vertical_rate, 14=squawk`.
- **Unit conversions server-side**: altitude m → ft (`* 3.28084`), speed m/s → kts (`* 1.94384`) and km/h (`* 3.6`, field `speed_kmh`).
- **Airline ICAO extraction**: first 3 alpha chars of callsign, e.g. `"UAL123"` → `"UAL"`.
- **Flight number**: `flight_iata` (adsbdb `callsign_iata`) shown next to the callsign in cards/hero/popup.
- **OpenSky auth**: keyless by default; optional free OAuth via ⚙ Settings modal (`/api/config` GET/POST/DELETE, validated live, persisted to git-ignored `opensky_creds.json`), or `OPENSKY_CLIENT_ID`/`OPENSKY_CLIENT_SECRET` env/`.env`. Load precedence: UI-saved file > env. `fetch_state_vectors` uses the **anonymous bucket first** and only falls back to the keyed bucket on 429 (conserves account credits). `OpenSkyRateLimit` (429) is served stale-cache or a friendly 429. `_record_rate()` tracks remaining credits **per bucket** (`_opensky_rate.anonymous`/`.authenticated`), exposed via `/api/config` as `rate:{anonymous, authenticated, last_mode, retry_after}` and shown as a header badge (both buckets).

## Frontend Features (templates/index.html)

- **Views**: `setView('cards'|'map')`; map uses Leaflet + OpenStreetMap tiles.
- **Map**: base layers `Dark` (OSM tiles with the `.dark-tiles` CSS filter, default) and `Standard`, switched via `L.control.layers`, persisted to `ofw:mapStyle`. Plane markers persist in `mapMarkers` (icao24 → `{f, marker, trail, path, shown, from, t0, fixT}`); `renderMap()` updates/adds/removes instead of clearing, so popups survive polls (`planeIcon()`, `updatePlaneIcon()` only swaps the icon when heading/ground/size change, `planePopupHtml()`). `glideFrame()` (rAF, ~10 fps, only in map view with the tab visible) dead-reckons airborne planes with `destinationPoint()` for up to `GLIDE_MAX_S` and eases onto each new fix over `GLIDE_BLEND_MS`; `placePlane()` also extends the trail (`TRAIL_POINTS` recent fixes). `prefers-reduced-motion` disables gliding.
- **Header on narrow screens**: below 1320 px `.controls` becomes a drop-down panel toggled by the ☰ `#controls-btn` (`toggleControls()`; outside click / Esc closes). A `ResizeObserver` keeps `--header-h` in sync so `#map` fills `100dvh - header`. `setStatus()` mirrors the status text into the dot's `title` (the text is hidden there).
- **Location** (no config file): `requestLocation()` (geolocation) → on failure `showLocPrompt()` reveals manual lat/lon entry (`manualLocation()`); map click also calls `setLocation()`. `applyUserLocation()` centres the map. Polling starts only once a location is set (`beginPolling()`).
- **Saved location** (opt-in): header **Save location** checkbox → `onSaveLocation()`. `initSavedLocation()` runs from `start()` in place of a bare `requestLocation()`: it restores `ofw:location` when `ofw:saveLocation` is set (skipping geolocation and pre-filling the manual inputs), else falls back to `requestLocation()`. `setLocation()` re-writes the store on every location change while the box is ticked; unticking deletes it. Every `localStorage` call is wrapped — it *throws* where site data is blocked — and `storageAvailable()` disables the checkbox in that case. Browser-only: the coordinates are never sent to the server.
- **Radius**: `radiusKm` seeded from `document.body.dataset.defaultRadius`; header input calls `onRadiusChange()` (re-fetches + resizes map circle).
- **Vector aircraft**: `planeSvg(f, id)` draws a side profile picked by `aircraftClass(aircraft_code)` (`quad`/`wide`/`narrow`/`rearjet`/`bizjet`/`turboprop`/`light`/`heli`; unknown → `narrow`). Fixed-wing shapes come from the `AIRFRAMES` profile table via `jetBody()`; helicopters use `heliBody()`. `isWestbound()` mirrors the drawing. `id` must be unique per copy on the page (`oh`, `hero`, `wall`).
- **Hero banner**: `renderHero()` spotlights `closestFlight()`. It reuses `planeSvg(f, 'hero')` + `loadTailLogo(f, 'hero')` (the `id` argument prefixes every SVG element id so the hero and overhead copies don't collide) plus `renderRoute()`/`renderProgress()`; the plane is only rebuilt when the closest aircraft or its direction changes (`hero.dataset.key`).
- **Overhead alert**: `checkOverhead()` / `dismissOverhead()`, fires within `OVERHEAD_KM` (3 km). The overlay draws a side-view SVG airliner via `planeSvg(f, 'oh')` (mirrored for westbound headings, lettering counter-flipped), paints the airline logo onto the tail fin with `loadTailLogo(f, 'oh')` (probes the Kiwi.com URL with `new Image()`, falls back to the ICAO code), and `renderOverheadInfo(f)` fills `#oh-detail` with the shared `flightDetailHtml(f)` (title, route, progress, stat tiles; also used by wall mode) on every poll; the SVG is only rebuilt when the overhead aircraft changes. Optional **auto-dismiss**: header dropdown labelled "Overhead alert" (options: Stays open / Dismiss in 30s/1/2/5 min) — `onAutoDismissChange()` sets `autoDismissMs` (**default 60 s / "Dismiss in 1 min"**; 0 = stays open); `startOverheadCountdown()`/`clearOverheadCountdown()` show a live "Dismiss in M:SS" next to the button and close it at 0.
- **Sound**: `beep()` / `toggleSound()` / `checkNewFlights()` — WebAudio ping on new ICAO24 (**on by default**; first ping needs a user gesture).
- **Browser notifications**: `notifyMode` ('off'|'new'|'overhead'|'both', **default 'both'**), `initNotify()` syncs the dropdown + requests permission on load (falls back to 'off' unless permission is explicitly *granted* — Chrome's quiet prompt leaves it at 'default'), `onNotifyChange()` requests permission, `sendNotification()` fires; hooked into `checkNewFlights` (mode 'new'/'both') and `checkOverhead` (mode 'overhead'/'both'). Delivery can fail at three layers — insecure origin, browser permission, or the OS silently dropping a notification the browser accepted — so `notifyBlockReason()` names the blocking layer and `setNotifyWarn()` surfaces it as a ⚠ next to the Notify dropdown. `sendNotification()` also watches `onshow`/`onerror`: if the OS never acknowledges the first notification within 4s, the ⚠ points at System Settings → Notifications.
- **Wall mode**: `toggleWall(on, fromButton)` adds `body.wall-mode` (not `wall` — that would match the `.wall` panel's own `display:none` rule) to show `#wall`; the 🖥 button also requests fullscreen, `?wall=1` (read in `start()`) only switches the layout. `renderWall(advance)` (called from `refreshUI()` while active, and every `WALL_CYCLE_MS` with `advance`) features one of the `WALL_FEATURED` nearest flights with `planeSvg(f, 'wall')` + `flightDetailHtml()`, crossfading only when the aircraft changes; `renderWallTicker()` rebuilds the seamless marquee only when the set changes; `tickWallClock()` runs the clock; `requestWakeLock()` keeps the screen on (re-acquired on `visibilitychange`). Esc exits.
- **Update notice**: `checkForUpdate()` (from `start()`, then every `UPDATE_RECHECK_MS` = 24 h so long-running/wall-mode pages still see new releases) reads `/api/version`, fills `#app-version` in the ⚙ modal and shows `#update-toast` unless that version is stored in `ofw:dismissedVersion` (`dismissUpdate()`).
- **OpenSky settings**: ⚙ modal (`openSettings`/`saveConfig`/`clearConfig`/`loadConfig`/`renderConfigStatus`) talks to `/api/config` to set/clear credentials live. The header badge shows both buckets (e.g. `387 free · 3986 key`), updated each poll.
- **Filter/sort**: `getVisibleFlights()`, `onSortChange()`, `onHideGround()`. Hide ground persists to `ofw:hideGround` via `lsSet()` and is restored by `initHideGround()` from `start()`; no opt-in, since it is a display preference rather than personal data.
- **Flags**: `flagEmoji(iso2)` from `country_iso`.
- **Airline logo**: `logoUrl(iata)` → `images.kiwi.com/airlines/64/{IATA}.png` (from `airline_iata`), shown on cards/hero/popup with `onerror` hide.
- **Climb/descent + squawk**: `vrateHtml()` (▲/▼ from `vertical_rate`); `squawk` shown when present.
- **Great-circle arcs**: `greatCircle(a, b)` used by `drawRoute()` on the map.
- **Progress/ETA**: `renderProgress()` bar (travelled/remaining/`progress_pct`), `fmtDuration()`/`etaClock()` for `eta_min`.

## Known Limitations

- **OpenSky rate limit** — anonymous is very low; the 30 s `_cache` and debounced radius help. `429` raises `OpenSkyRateLimit`; the API serves stale cache if available, else returns a friendly 429. Add OpenSky OAuth creds for a higher limit.
- **hexdb.io / adsbdb.com** are community-run — may be slow or return nothing; UI falls back to ICAO code / "Route unavailable".
- **On-ground aircraft** are included (Hide-ground toggle filters them client-side).

## Approach for Changes

1. Read the relevant file(s) before editing.
2. Preserve the zero-cost constraint in all suggestions.
3. Keep the cache mechanisms intact when modifying `fetch_flights()` or `get_route()`.
4. For frontend changes, keep everything in `index.html` — no build step, no npm (Leaflet is loaded from CDN).
5. Test by running `uv run python app.py` and hitting `/api/flights?lat=..&lon=..&radius=..`.
6. **Update `CHANGELOG.md`** for any user-facing change — add an entry under `## [Unreleased]` (create the section if it's missing), using the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) categories (Added/Changed/Fixed/Removed/Security). When releasing, `[Unreleased]` gets renamed to the new version + date (see [Release Process](#release-process); the release workflow copies that section into the GitHub Release notes).

## Docker

- `Dockerfile` — multi-stage build (`python:3.12-slim`): a `builder` stage uses `uv sync --extra server` to install deps (incl. gunicorn) into `.venv`, then a `runtime` stage copies just `.venv` + `app.py` + `pyproject.toml` (for `APP_VERSION`) + `templates/` and runs as a non-root user.
- The container's `CMD` runs **gunicorn** (`gunicorn --bind 0.0.0.0:${PORT} ... app:app`), importing the Flask `app` object directly — it never executes the `if __name__ == "__main__":` block, so local dev (`uv run python app.py`, Flask's own dev server) is completely separate and unaffected by Docker changes.
- `PORT` env var controls the bind port (default `5050`) — required for platforms like Render that inject their own port.
- `.github/workflows/docker-publish.yml` builds and pushes multi-arch (`linux/amd64`+`linux/arm64`) images to Docker Hub (`dilshanonline/openflightwall`) on `v*.*.*` git tags only — pushing to `main` does **not** trigger a build. Its first step fails the run if the tag differs from `pyproject.toml`'s version; a second `release` job (after the image is pushed, `contents: write` scoped to that job) creates the GitHub Release with that version's `CHANGELOG.md` section as notes (`--prerelease` for tags containing `-`).
- **Releasing**: see [Release Process](#release-process).
- Local test build: `docker buildx build --load -t openflightwall:test .` then `docker run -p 5050:5050 openflightwall:test`.
- If you add a new Python dependency needed at runtime, add it to `dependencies` (or the `server` extra in `[project.optional-dependencies]` if Docker-only) in `pyproject.toml`, then run `uv lock` to update `uv.lock` — the Docker build uses `uv sync --frozen`, so a stale lockfile will fail the build.
- Live demo deployed on Render (free tier): https://openflightwall.onrender.com/ — built directly from this repo's `Dockerfile`, redeploys on push to `main`. **Known issue**: OpenSky Network sometimes blocks/throttles anonymous requests from cloud/datacenter IPs (Render, AWS, GCP, Heroku, etc.), which can surface as a `500` from `/api/flights` there — it's an upstream restriction (already caught and reported cleanly by the `except Exception` handler around `fetch_flights()` in `app.py`, not an app bug). Don't "fix" this by suppressing the error; a real fix would involve auth-first requests or a fallback data source.

## Release Process

Releases follow [Semantic Versioning](https://semver.org/): **patch** (`1.2.1`) for fixes, **minor** (`1.3.0`) for new features, **major** (`2.0.0`) for breaking changes. `pyproject.toml`'s `version` is the single source of truth: the in-app update alert compares against it, and the workflow refuses a tag that doesn't match it.

**One-time setup:**
- Docker Hub secrets `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` in the repo's Actions secrets (in place; earlier releases were published with them).
- Settings → Pages → Source: **GitHub Actions**, needed before the website workflow can deploy (added in 1.2.0, so do this once before the first release that includes it).

**Steps** (on a feature branch, e.g. `rewamp-v1.2`):
1. **Finish the work.** Every user-facing change has an entry under `## [Unreleased]` in `CHANGELOG.md`; README/AGENTS.md are up to date; screenshots retaken if the UI changed.
2. **Check it runs.** `uv run python app.py` → load the dashboard and `curl 'localhost:5050/api/flights?lat=51.47&lon=-0.45&radius=10'`; `python3 site/build.py` succeeds; optionally `docker buildx build --load -t openflightwall:test .`.
3. **Bump the version.** Set `version = "X.Y.Z"` in `pyproject.toml`, then run `uv lock` so `uv.lock` records the same version (the Docker build installs with `uv sync --frozen`).
4. **Date the changelog.** Rename `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD` and add a fresh empty `## [Unreleased]` above it. The release workflow copies the `[X.Y.Z]` section into the GitHub Release notes, so write it for users.
5. **Commit and open a PR.** e.g. `git commit -am "Release X.Y.Z"`, push the branch, open a PR to `main`, merge it.
6. **Tag the merged commit on `main`** (not the feature branch):
   ```bash
   git checkout main && git pull
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
   Pushing to `main` alone builds nothing; the tag is what releases.
7. **Watch the workflows** (Actions tab):
   - *Docker Publish* → version check → multi-arch image to Docker Hub (`X.Y.Z`, `X.Y`, `X`, `latest`) → **`release` job creates the GitHub Release** (tags containing `-`, e.g. `v2.0.0-beta.1`, become pre-releases).
   - *GitHub Pages* redeploys the website/demo if `site/`, `templates/index.html` or `docs/screenshots/` changed in the merge.
8. **Verify.** The release appears at github.com/dilshanonline/OpenFlightWall/releases with the right notes; `docker pull dilshanonline/openflightwall:X.Y.Z` works; the website's version badge shows `vX.Y.Z`; Render redeploys from `main` automatically.

**If something goes wrong:**
- *Tag/version mismatch*: the workflow fails before building. Delete the tag (`git tag -d vX.Y.Z && git push origin :refs/tags/vX.Y.Z`), fix `pyproject.toml` on `main`, and tag again.
- *Docker build fails*: no release is created (the `release` job only runs after a successful push), so users are never told about a version without an image. Fix on `main`, delete and re-push the tag.
- Never re-use a version number that has already been published to Docker Hub or announced as a release; bump to the next patch instead.

Running apps notice the new release within about a day (server cache 6 h, browser re-check daily); see README → Update notifications.

## GitHub Pages (website + replay demo)

- Live at `https://dilshanonline.github.io/OpenFlightWall/` (landing page) and `/demo/` (replay demo). Pages can't run Flask, and OpenSky only sends CORS headers for its own origin, so the demo **replays a recorded snapshot** instead of fetching live data.
- `site/index.html` — hand-written landing page (no framework). `site/demo.js` — replay engine + demo banner; sets `window.OFW_DEMO = {center, pollMs, flights(loc, radiusKm)}`, advancing airborne planes along their heading (6-minute loop) and recomputing distance/bearing. `site/snapshot.json` — the recording.
- `site/build.py` (stdlib) writes `_site/` (git-ignored): copies the landing page and `docs/screenshots/`, and renders `templates/index.html` into `_site/demo/index.html` by replacing `{{ default_radius }}` and injecting the snapshot JSON + `demo.js` before the main `<script>`. It **fails loudly** if those anchors change. Preview with `python3 site/build.py --serve` (http://localhost:8000/); opening `site/index.html` directly shows no images and no demo, because those only exist in `_site/`.
- **Demo hooks in `templates/index.html`** — `const DEMO = window.OFW_DEMO || null`; `POLL_MS` uses `DEMO.pollMs`; `start()` calls `startDemo()` (adds `body.demo`, sound/notifications off, no config/update/saved-location calls, `setLocation(DEMO.center…)`); `loadFlights()` takes `DEMO.flights(...)` instead of `/api/flights`. `body.demo` hides ⚙, Save location and the credits badge. When editing `start()`/`loadFlights()`, keep these branches working and rebuild the site to check the demo.
- Refresh the recording: run the dev server, then `python3 site/capture_snapshot.py [--lat --lon --radius --label]` (keeps airborne flights only).
- `.github/workflows/pages.yml` builds and deploys on pushes to `main` touching `site/**`, `templates/index.html` or `docs/screenshots/**` (plus manual dispatch). Requires Settings → Pages → Source: **GitHub Actions** (one-time).

## Running / Testing

```bash
uv sync
uv run python app.py                                        # starts on port 5050
curl 'localhost:5050/api/flights?lat=51.47&lon=-0.45&radius=6'   # verify JSON array
```

## External API URLs

| Service | URL Pattern |
|---|---|
| OpenSky states | `https://opensky-network.org/api/states/all?lamin=…&lamax=…&lomin=…&lomax=…` |
| hexdb.io aircraft | `https://hexdb.io/api/v1/aircraft/{icao24}` |
| adsbdb.com route | `https://api.adsbdb.com/v0/callsign/{callsign}` |
| GitHub latest release | `https://api.github.com/repos/dilshanonline/OpenFlightWall/releases/latest` (fallback `/tags`) |
