# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.2.1] - 2026-10-21

### Removed
- The Render-hosted "Live demo" and the README's **Deploy to Render** section. OpenSky blocks Render's datacenter IPs, so that demo often failed to load flights; the [GitHub Pages replay demo](https://dilshanonline.github.io/OpenFlightWall/demo/) replaces it. The underlying caveat (OpenSky blocks some cloud IPs) is kept as a general **Hosting in the cloud** note.

### Fixed
- Plane icons on the map pointed 90° away from their real direction (for example, westbound planes faced north), because the ✈ symbol faces east before it is rotated. They now point the way each plane is flying.

## [1.2.0] - 2026-10-20

### Added
- **Project website on GitHub Pages** (`https://dilshanonline.github.io/OpenFlightWall/`) with a **replay demo** that runs the real dashboard in the browser on a recorded snapshot of real flights near London, with no server. Planes keep flying along their headings, and the demo banner can trigger the overhead alert or wall mode. It is built by `site/build.py` (Python stdlib only) and deployed by a new GitHub Pages workflow. The dashboard gained a small `window.OFW_DEMO` hook that is inactive in the normal app.
- **Wall mode** — a full-screen display for a TV, Raspberry Pi or spare monitor: a big clock and date, the nearest flights shown in turn (every 12 s) with large aircraft art, route and live stats, and a scrolling ticker of every other flight. It keeps the screen awake where the browser supports it, and the overhead alert still appears on top. Open it with the new 🖥 header button (which also goes full screen) or by loading `/?wall=1`; leave with Esc or ✕.
- **New-version alert.** The app now checks GitHub for a newer release (on load and then daily while the page stays open, so wall-mode screens hear about it too; the server caches GitHub's answer for 6 hours) and shows a small dismissible notice with a "What's new" link and the update command; dismissing it hides it until the next release. `uv run python app.py` also prints a one-line notice at startup, and the ⚙ settings panel shows the running version. Set `OFW_UPDATE_CHECK=0` to never contact GitHub. New `GET /api/version` endpoint.
- **Plane trails and smooth motion on the map.** Each plane leaves a short trail through its recent positions, and between the 30-second updates planes glide along their heading at their ground speed instead of jumping. Turned off when the OS asks for reduced motion.
- **Dark map** by default, matching the rest of the UI, with a layer button to switch back to the standard OpenStreetMap style (the choice is remembered). It recolours the same free OSM tiles in the browser, so no new map service or API key is involved.

### Changed
- Redesigned the full-screen **Overhead now** alert. Instead of a bobbing emoji and a line of grey text, it now shows a vector drawing of an airliner with the airline's logo painted on the tail fin (or the airline's ICAO code if no logo is available), the airline name and registration on the fuselage, and the nose pointing in the plane's direction of travel. Below it are the full route with cities and flags, the progress bar and ETA, and live tiles for altitude (with climb/descent), speed, distance, heading and squawk. Clouds drift in the background; motion is turned off when the OS asks for reduced motion.
- The **Closest flight** banner above the cards now shows the same vector aircraft with the airline logo on its tail, alongside the route, progress bar and ETA, registration, and a climb/descent arrow on the altitude.
- The vector aircraft art now **matches the aircraft type**: four-engine jumbos (with the 747's upper deck), longer wide-bodies, narrow-bodies, rear-engine regional jets, business jets, turboprops with spinning propellers, light aircraft (registration on the fin) and helicopters.
- The full-screen overhead alert now **dismisses itself after 1 minute** by default (it used to stay open until clicked). Choose **Stays open** from the header's "Overhead alert" dropdown to keep the old behaviour.
- **Works on phones.** Below about 1320 px wide, the header controls fold into a ☰ panel instead of overflowing the screen (the page used to be more than twice as wide as a phone screen); on very narrow screens the page margins shrink.
- Map popups **stay open** across the 30-second refresh. Plane markers used to be thrown away and recreated on every poll, which closed any popup you had open.
- Releases are now published as **GitHub Releases** automatically: pushing a `vX.Y.Z` tag builds and pushes the Docker image, then creates the release with that version's changelog notes. The workflow also refuses a tag that does not match the version in `pyproject.toml`.

### Fixed
- Airline names were never shown: the frontend expected an `airline_name` field that the backend never sent, so cards and the hero showed the ICAO code (e.g. "BAW") instead of "British Airways", and sorting by airline sorted by callsign. `/api/flights` now includes the airline name from adsbdb.com.

## [1.1.1] - 2026-09-22

### Fixed
- Plane icons on the map are now bigger and grow as you zoom in, instead of staying a fixed pixel size. Previously the icon stayed pinned at 20×20px at every zoom level, so relative to the map it looked like it was shrinking the more you zoomed in.

## [1.1.0] - 2026-09-22

### Added
- The **Hide ground** toggle is now remembered across reloads, so it no longer resets to off on every visit.
- **Save location** checkbox in the header. A manually entered lat/lon (or a spot picked on the map) was forgotten on every reload, so it had to be typed in again each time. Tick the box and the location is remembered in this browser and reused on the next visit instead of re-running geolocation; untick it and the stored coordinates are deleted. Off by default, so nothing is stored unless asked for. The coordinates stay in `localStorage` and are never sent to the server. Where the browser blocks site data the checkbox is disabled and explains why.

### Fixed
- Location detection over plain `http://` reported "Location permission denied" even though no permission prompt was ever shown. Geolocation is a secure-context-only API, so over plain `http://` the browser rejects the request instantly with `PERMISSION_DENIED` — the app relayed that raw error code and sent users looking for a dialog that could not appear. `requestLocation()` now checks `window.isSecureContext` first (matching the existing notification diagnostics) and names the real blocker.

## [1.0.2] - 2026-08-22

### Fixed
- Browser notifications could silently never fire while the header dropdown still read "Both". `initNotify()` only fell back to `off` on an explicit `denied`, so when Chrome answered with its quiet permission prompt — leaving the permission at `default` — the app stayed in `both` mode and every notification was dropped with no indication.
- `sendNotification()` swallowed every failure (an empty `catch`, plus a bare return when permission was not granted), so nothing surfaced when a notification could not be delivered.

### Added
- Notification delivery diagnostics: a ⚠ marker beside the **Notify** dropdown names whichever layer is blocking — insecure origin, browser permission, or the OS. `sendNotification()` watches `onshow`/`onerror` and, if the OS never acknowledges the first notification within 4s, points at System Settings → Notifications. This catches the case where the browser reports success but macOS silently drops the banner.
- README troubleshooting section for notifications that never appear.

## [1.0.1] - 2026-08-21

### Changed
- Default port moved from `5000` to `5050` (local dev and Docker/`PORT` default alike) — macOS's AirPlay Receiver squats on port 5000, which was intermittently hijacking the app's port after every dev-server reload.

## [1.0.0] - 2026-08-21

### Added
- Docker image (`Dockerfile`, multi-stage, `python:3.12-slim`) running behind gunicorn, with a `server` optional dependency group for the production WSGI server.
- GitHub Actions workflow (`.github/workflows/docker-publish.yml`) that builds and pushes multi-arch (`linux/amd64` + `linux/arm64`) images to Docker Hub on `v*.*.*` tags, with semantic version tags (`1.2.0`/`1.2`/`1`/`latest`) and GitHub Actions layer caching.
- `README.md` **Docker** and **Deploy to Render** sections.
- This changelog.

## [0.1.0] - Initial extraction

### Added
- Project extracted from a `web/` folder inside a fork of [TheFlightWall_OSS](https://github.com/AxisNimble/TheFlightWall_OSS) into this standalone repository, renamed to OpenFlightWall.
