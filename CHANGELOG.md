# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
