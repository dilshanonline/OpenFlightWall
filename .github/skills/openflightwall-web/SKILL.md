---
name: openflightwall-web
description: "OpenFlightWall local web UI. Use when working on the Flask backend in app.py, flight data pipeline, OpenSky API (keyless by default, optional free OAuth for higher limits), hexdb.io aircraft lookup, adsbdb.com route lookup, uv pyproject.toml, or the HTML/Leaflet flight UI in templates/index.html (card + map views, hero banner, overhead alert, sound, filters). Zero-cost constraint: no paid APIs."
---

# OpenFlightWall Web UI

Local Python/Flask dashboard that shows nearby flights using only free APIs — keyless by default, with an optional free OpenSky account for a higher rate limit. Two views: a flight-card grid and a Leaflet/OpenStreetMap map.

## Project Layout

```
web/
├── app.py              # Flask server + data pipeline (edit for backend changes)
├── pyproject.toml      # Poetry dependencies (package-mode = false; deps: flask, requests, python-dotenv)
├── .env.example        # Committed template for optional OpenSky OAuth creds
├── .env                # Local secrets — git-ignored, never committed (optional)
└── templates/
    └── index.html      # Single-file frontend (vanilla HTML/CSS/JS + Leaflet CDN)
```

Location and radius are chosen in the browser and passed to `/api/flights` as query params. `web/.env` (git-ignored) optionally holds OpenSky OAuth credentials; `web/.env.example` is the committed template.

## Data Pipeline

```
OpenSky anonymous  →  state vectors  (lat/lon/callsign/icao24/alt/speed/heading/vertical_rate/squawk)
hexdb.io           →  aircraft type code from ICAO24 (fallback: adsbdb icao_type)
adsbdb.com route   →  origin/destination airports, IATA flight number, airline telephony + IATA
adsbdb.com aircraft→  registration, manufacturer, owner, photo
Kiwi.com CDN       →  airline logo by IATA code (client-side image URL)
computed           →  distance travelled/remaining, progress %, rough ETA
```

## Key Functions in app.py

| Function | Purpose |
|---|---|
| `haversine_km(...)` | Great-circle distance (ported from `GeoUtils.h`) |
| `bearing_deg(...)` | Compass bearing (ported from `GeoUtils.h`) |
| `bounding_box(lat, lon, radius_km)` | lat/lon bounds for OpenSky query |
| `fetch_state_vectors(center_lat, center_lon, radius_km)` | GET OpenSky, parse states (incl. squawk), filter by radius |
| `extract_airline_icao(callsign)` | `"UAL123"` → `"UAL"` |
| `get_aircraft_type(icao24)` | hexdb.io lookup → ICAO type code |
| `get_route(callsign)` | adsbdb.com → `{origin, destination, flight_iata, airline_callsign, airline_iata}` (1 h cached) |
| `get_aircraft_details(icao24)` | adsbdb.com → `{registration, manufacturer, type_code, owner, owner_country, photo, photo_thumb}` (1 h cached) |
| `compute_progress(origin, dest, lat, lon, speed_kmh)` | → `{route_total_km, travelled_km, remaining_km, progress_pct, eta_min}` |
| `_airport_summary(ap)` | Reduce adsbdb airport to iata/icao/name/city/country/country_iso/lat/lon |
| `fetch_flights(center_lat, center_lon, radius_km)` | Orchestrates full pipeline |

## Caching

- `_cache` — full flight list, keyed by rounded (lat, lon, radius), `CACHE_TTL = 30` s.
- `_route_cache` / `_aircraft_cache` — per-callsign / per-icao24, `ROUTE_CACHE_TTL = 3600` s.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Serves `templates/index.html`; injects `DEFAULT_RADIUS_KM` via a `data-default-radius` body attribute |
| `GET` | `/api/flights?lat&lon&radius` | Enriched JSON array. `lat`/`lon` **required** (400 if missing); `radius` defaults to `DEFAULT_RADIUS_KM` |
| `GET` | `/api/config` | OpenSky auth status `{configured, client_id_masked, source, rate:{anonymous, authenticated, last_mode, retry_after}}` (never returns the secret) |
| `POST` | `/api/config` | Body `{client_id, client_secret}` — validates via a token request, then persists to `opensky_creds.json` |
| `DELETE` | `/api/config` | Clears UI-saved creds (reverts to env/anonymous) |

## Frontend Features (templates/index.html)

- **Views**: `setView('cards'|'map')`; map uses Leaflet + OpenStreetMap tiles.
- **Location** (no config file): `requestLocation()` (geolocation) → on failure `showLocPrompt()` reveals manual lat/lon entry (`manualLocation()`); map click also calls `setLocation()`. `applyUserLocation()` centres the map.
- **Radius**: `radiusKm` seeded from `document.body.dataset.defaultRadius`; header input calls `onRadiusChange()` (re-fetches + resizes map circle).
- **Hero banner**: `renderHero()` spotlights `closestFlight()`.
- **Overhead alert**: `checkOverhead()` / `dismissOverhead()`, fires within `OVERHEAD_KM` (3 km). Optional **auto-dismiss**: header dropdown labelled "Overhead alert" (options: Stays open / Dismiss in 30s/1/2/5 min) — `onAutoDismissChange()` sets `autoDismissMs` (default 0/off); `startOverheadCountdown()`/`clearOverheadCountdown()` show a live "Dismiss in M:SS" next to the button and close it at 0.
- **Header controls**: all use a consistent label-outside layout (Radius, Sort, Hide ground, Notify, Overhead alert) followed by 🔔 sound + ⚙ settings buttons.
- **Sound**: `beep()` / `toggleSound()` / `checkNewFlights()` — WebAudio ping on new ICAO24 (**on by default**; first ping needs a user gesture).
- **Browser notifications**: `notifyMode` ('off'|'new'|'overhead'|'both', **default 'both'**), `initNotify()` syncs the dropdown + requests permission on load (falls back to 'off' if blocked/unsupported), `onNotifyChange()` requests permission, `sendNotification()` fires; hooked into `checkNewFlights` (mode 'new'/'both') and `checkOverhead` (mode 'overhead'/'both'). Uses `flightLabel()` + airline logo icon.
- **OpenSky settings**: ⚙ modal (`openSettings`/`saveConfig`/`clearConfig`/`loadConfig`/`renderConfigStatus`) talks to `/api/config` to set/clear credentials live. `fetch_state_vectors` tries the **anonymous bucket first**, falling back to the authenticated (keyed) bucket only on 429; `_record_rate()` stores remaining credits **per bucket** (`_opensky_rate.anonymous` / `.authenticated`). The header badge shows both (e.g. `387 free · 3986 key`), updated each poll.
- **Filter/sort**: `getVisibleFlights()`, `onSortChange()`, `onHideGround()`.
- **Flags**: `flagEmoji(iso2)` from `country_iso`.
- **Flight number**: `flight_iata` (adsbdb `callsign_iata`) shown next to the callsign.
- **Speed units**: server sends `speed_kts` and `speed_kmh`; both shown in cards/hero/popup.
- **Progress/ETA**: `renderProgress()` bar (travelled/remaining/`progress_pct`), `fmtDuration()`/`etaClock()` for `eta_min`.
- **Aircraft photo/registration**: `photo`/`photo_thumb`/`registration` on cards, popup, hero.
- **Airline logo**: `logoUrl(iata)` → `images.kiwi.com/airlines/64/{IATA}.png` (from `airline_iata`), shown on cards/hero/popup with `onerror` hide.
- **Climb/descent + squawk**: `vrateHtml()` (▲/▼ from `vertical_rate`); `squawk` shown when present.
- **Great-circle arcs**: `greatCircle(a, b)` used by `drawRoute()` on the map.
- **Polling** starts only once a location is set (`beginPolling()`).

## Configuration

Location (geolocation / manual / map click) and search radius are chosen in the browser. `DEFAULT_RADIUS_KM` in `app.py` (10) seeds the UI radius input.

**Optional OpenSky OAuth** (higher rate limit): credentials can be set three ways — the ⚙ **Settings** modal in the UI (validated live, persisted to git-ignored `web/opensky_creds.json`), `OPENSKY_CLIENT_ID`/`OPENSKY_CLIENT_SECRET` env vars, or `web/.env`. Load precedence: UI file > env. `_load_creds()`/`_save_creds()`/`_clear_creds()` manage runtime `_creds`; `_opensky_fetch_token()` validates + fetches; `_opensky_token_get()` caches and adds the Bearer header in `fetch_state_vectors`. Startup prints `OpenSky access: anonymous|authenticated (OAuth)`.

## Known Limitations

- **OpenSky rate limit** — anonymous is very low; the 30 s `_cache` and debounced radius help. `429` raises `OpenSkyRateLimit`; the API serves stale cache if available, else returns a friendly 429. Add OpenSky OAuth creds for a higher limit.
- **hexdb.io / adsbdb.com** are community-run — may be slow or return nothing; UI falls back to ICAO code / "Route unavailable".
- **On-ground aircraft** are included (Hide-ground toggle filters them client-side).

## How to Run

```bash
cd web
poetry install
poetry run python app.py
# → http://localhost:5000  (allow location, or enter it manually)
```

## External API URLs

| Service | URL Pattern |
|---|---|
| OpenSky states | `https://opensky-network.org/api/states/all?lamin=…&lamax=…&lomin=…&lomax=…` |
| hexdb.io aircraft | `https://hexdb.io/api/v1/aircraft/{icao24}` |
| adsbdb.com route | `https://api.adsbdb.com/v0/callsign/{callsign}` |
