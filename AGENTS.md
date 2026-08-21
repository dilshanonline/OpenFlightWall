# AGENTS.md — OpenFlightWall

Guidance for AI coding assistants (and human contributors) working on this repo: a local Python/Flask dashboard that shows nearby flights using only free APIs — keyless by default, with an optional free OpenSky account for a higher rate limit. Two views: a flight-card grid and a Leaflet/OpenStreetMap map.

## Hard Constraints

- **NEVER** suggest paid APIs or services (no FlightAware AeroAPI, no aviation data subscriptions).
- **NEVER** add API keys or credentials to the codebase.
- **All data sources must be free** (keyless preferred): OpenSky (optional free OAuth), hexdb.io, adsbdb.com, Kiwi.com logos.
- There is no config file for location/radius — those live in the browser. The only optional server config is OpenSky OAuth via `OPENSKY_CLIENT_ID`/`OPENSKY_CLIENT_SECRET` (env or `.env`).
- Before adding a new data source, confirm it is free and requires no key.

## Project Layout

```
OpenFlightWall/
├── app.py              # Flask server + data pipeline (edit for backend changes)
├── pyproject.toml      # uv project config (deps: flask, requests, python-dotenv)
├── uv.lock             # Reproducible dependency lockfile
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
adsbdb.com route   →  origin/destination airports, IATA flight number, airline telephony + IATA
adsbdb.com aircraft→  registration, manufacturer, owner, photo
Kiwi.com CDN       →  airline logo by IATA code (client-side image URL)
computed           →  distance travelled/remaining, progress %, rough ETA
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
| `get_route(callsign)` | adsbdb.com → `{origin, destination, flight_iata, airline_callsign, airline_iata}` (1 h cached) |
| `get_aircraft_details(icao24)` | adsbdb.com → `{registration, manufacturer, type_code, owner, owner_country, photo, photo_thumb}` (1 h cached) |
| `compute_progress(origin, dest, lat, lon, speed_kmh)` | → `{route_total_km, travelled_km, remaining_km, progress_pct, eta_min}` |
| `_airport_summary(ap)` | Reduce adsbdb airport to iata/icao/name/city/country/country_iso/lat/lon |
| `fetch_flights(center_lat, center_lon, radius_km)` | Orchestrates full pipeline |

## Caching

- `_cache` — full flight list, keyed by rounded (lat, lon, radius), `CACHE_TTL = 30` s. Protects the OpenSky rate limit (~1 req/10s).
- `_route_cache` / `_aircraft_cache` — per-callsign / per-icao24, `ROUTE_CACHE_TTL = 3600` s.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Serves `templates/index.html`; injects `DEFAULT_RADIUS_KM` via a `data-default-radius` body attribute |
| `GET` | `/api/flights?lat&lon&radius` | Enriched JSON array. `lat`/`lon` **required** (400 if missing); `radius` defaults to `DEFAULT_RADIUS_KM` |
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
- **Location** (no config file): `requestLocation()` (geolocation) → on failure `showLocPrompt()` reveals manual lat/lon entry (`manualLocation()`); map click also calls `setLocation()`. `applyUserLocation()` centres the map. Polling starts only once a location is set (`beginPolling()`).
- **Radius**: `radiusKm` seeded from `document.body.dataset.defaultRadius`; header input calls `onRadiusChange()` (re-fetches + resizes map circle).
- **Hero banner**: `renderHero()` spotlights `closestFlight()`.
- **Overhead alert**: `checkOverhead()` / `dismissOverhead()`, fires within `OVERHEAD_KM` (3 km). Optional **auto-dismiss**: header dropdown labelled "Overhead alert" (options: Stays open / Dismiss in 30s/1/2/5 min) — `onAutoDismissChange()` sets `autoDismissMs` (default 0/off); `startOverheadCountdown()`/`clearOverheadCountdown()` show a live "Dismiss in M:SS" next to the button and close it at 0.
- **Sound**: `beep()` / `toggleSound()` / `checkNewFlights()` — WebAudio ping on new ICAO24 (**on by default**; first ping needs a user gesture).
- **Browser notifications**: `notifyMode` ('off'|'new'|'overhead'|'both', **default 'both'**), `initNotify()` syncs the dropdown + requests permission on load (falls back to 'off' if blocked/unsupported), `onNotifyChange()` requests permission, `sendNotification()` fires; hooked into `checkNewFlights` (mode 'new'/'both') and `checkOverhead` (mode 'overhead'/'both').
- **OpenSky settings**: ⚙ modal (`openSettings`/`saveConfig`/`clearConfig`/`loadConfig`/`renderConfigStatus`) talks to `/api/config` to set/clear credentials live. The header badge shows both buckets (e.g. `387 free · 3986 key`), updated each poll.
- **Filter/sort**: `getVisibleFlights()`, `onSortChange()`, `onHideGround()`.
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

## Running / Testing

```bash
uv sync
uv run python app.py                                        # starts on port 5000
curl 'localhost:5000/api/flights?lat=51.47&lon=-0.45&radius=6'   # verify JSON array
```

## External API URLs

| Service | URL Pattern |
|---|---|
| OpenSky states | `https://opensky-network.org/api/states/all?lamin=…&lamax=…&lomin=…&lomax=…` |
| hexdb.io aircraft | `https://hexdb.io/api/v1/aircraft/{icao24}` |
| adsbdb.com route | `https://api.adsbdb.com/v0/callsign/{callsign}` |
