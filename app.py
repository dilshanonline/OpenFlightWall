"""
OpenFlightWall — Local Web UI
Flask server that fetches nearby flight data from free APIs and serves a web
dashboard at http://localhost:5000.

Data pipeline (zero-cost):
  1. OpenSky Network             — real-time ADS-B state vectors
  2. hexdb.io                    — aircraft type from ICAO24 hex code
  3. adsbdb.com                  — flight route (origin / destination airports)

Location and search radius are chosen entirely in the browser (geolocation
with a manual fallback) and passed to /api/flights as query parameters.

OpenSky access:
  • Works anonymously with no setup (but the anonymous rate limit is very low).
  • Set OPENSKY_CLIENT_ID and OPENSKY_CLIENT_SECRET (env vars, or a .env file)
    to authenticate with a free OpenSky account for a much higher rate limit.
"""

import json
import math
import os
import time
from pathlib import Path

import requests
from flask import Flask, jsonify, render_template, request

# Optionally load a local .env (only if python-dotenv is installed).
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

app = Flask(__name__)

# Default search radius (km) offered by the UI; the user can change it live.
DEFAULT_RADIUS_KM = 10.0

OPENSKY_BASE = "https://opensky-network.org"
OPENSKY_TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/"
    "openid-connect/token"
)
HEXDB_BASE = "https://hexdb.io"
ADSBDB_BASE = "https://api.adsbdb.com"

# OpenSky OAuth credentials (client_credentials flow). Keyless by default; can be
# set via env vars, a .env file, or live from the UI (persisted to a local file).
# Load precedence: local file (UI-saved) overrides env vars.
CREDS_FILE = Path(__file__).parent / "opensky_creds.json"
_creds = {"client_id": "", "client_secret": "", "source": "none"}
_opensky_token = {"access_token": "", "expiry": 0.0}

# Last-seen OpenSky rate-limit state, tracked per bucket (free anonymous vs the
# authenticated account key). Each request only touches one bucket, so we keep
# the last-known value for each independently.
_opensky_rate = {
    "anonymous": {"remaining": None, "ts": 0.0},
    "authenticated": {"remaining": None, "ts": 0.0},
    "last_mode": "anonymous",
    "retry_after": None,
}


def _record_rate(bucket: str, resp) -> None:
    """Record remaining credits for a bucket from an OpenSky response's headers."""
    now = time.time()
    rem = resp.headers.get("X-Rate-Limit-Remaining")
    if resp.status_code == 429:
        _opensky_rate[bucket].update(remaining=0, ts=now)
    elif rem is not None and rem.lstrip("-").isdigit():
        _opensky_rate[bucket].update(remaining=int(rem), ts=now)
    ra = resp.headers.get("X-Rate-Limit-Retry-After-Seconds")
    if ra is not None and ra.lstrip("-").isdigit():
        _opensky_rate["retry_after"] = int(ra)


def _load_creds() -> None:
    """(Re)load OpenSky creds: env vars first, then a UI-saved file (which wins)."""
    _creds.update(client_id="", client_secret="", source="none")
    cid, csec = os.getenv("OPENSKY_CLIENT_ID", ""), os.getenv("OPENSKY_CLIENT_SECRET", "")
    if cid and csec:
        _creds.update(client_id=cid, client_secret=csec, source="env")
    try:
        if CREDS_FILE.exists():
            data = json.loads(CREDS_FILE.read_text())
            if data.get("client_id") and data.get("client_secret"):
                _creds.update(
                    client_id=data["client_id"],
                    client_secret=data["client_secret"],
                    source="ui",
                )
    except Exception:
        pass


_load_creds()

# OpenSky anonymous API allows ~1 request per 10 seconds.
# Cache responses for 30 seconds to stay well within the limit.
# Cache is keyed by rounded location so different clients don't collide.
CACHE_TTL = 30
_cache: dict = {}

# Flight routes and aircraft types rarely change, so cache them for much longer
# (keyed by callsign / icao24) to avoid hammering the upstream free APIs.
ROUTE_CACHE_TTL = 3600  # 1 hour
_route_cache: dict = {}
_aircraft_cache: dict = {}


class OpenSkyRateLimit(Exception):
    """Raised when OpenSky returns HTTP 429 (too many requests)."""


def _opensky_fetch_token(client_id: str, client_secret: str) -> tuple[str, float]:
    """Request a fresh OAuth token. Returns (access_token, expires_in) or ('', 0)."""
    try:
        resp = requests.post(
            OPENSKY_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            j = resp.json()
            return (j.get("access_token", "") or "", float(j.get("expires_in", 1800)))
    except Exception:
        pass
    return "", 0.0


def _opensky_token_get() -> str:
    """
    Return a valid OpenSky OAuth access token, or '' for anonymous access.
    Caches the token until ~60 s before expiry. Any failure falls back to anonymous.
    """
    cid, csec = _creds["client_id"], _creds["client_secret"]
    if not (cid and csec):
        return ""
    now = time.time()
    if _opensky_token["access_token"] and now < _opensky_token["expiry"] - 60:
        return _opensky_token["access_token"]
    token, expires_in = _opensky_fetch_token(cid, csec)
    if token:
        _opensky_token["access_token"] = token
        _opensky_token["expiry"] = now + expires_in
    return token


def _save_creds(client_id: str, client_secret: str) -> None:
    """Persist UI-supplied creds to a local (git-ignored) file and reset the token."""
    _creds.update(client_id=client_id, client_secret=client_secret, source="ui")
    _opensky_token.update(access_token="", expiry=0.0)
    try:
        CREDS_FILE.write_text(json.dumps({"client_id": client_id, "client_secret": client_secret}))
        os.chmod(CREDS_FILE, 0o600)
    except Exception:
        pass


def _clear_creds() -> None:
    """Delete UI-saved creds and revert to env vars (or anonymous)."""
    _opensky_token.update(access_token="", expiry=0.0)
    try:
        CREDS_FILE.unlink(missing_ok=True)
    except Exception:
        pass
    _load_creds()


def _masked_id() -> str:
    cid = _creds["client_id"]
    if not cid:
        return ""
    return (cid[:4] + "…") if len(cid) > 4 else "…"


# ---------------------------------------------------------------------------
# Geo utilities — ported from firmware/utils/GeoUtils.h
# ---------------------------------------------------------------------------

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlon = math.radians(lon2 - lon1)
    lat1r = math.radians(lat1)
    lat2r = math.radians(lat2)
    x = math.sin(dlon) * math.cos(lat2r)
    y = math.cos(lat1r) * math.sin(lat2r) - math.sin(lat1r) * math.cos(lat2r) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def bounding_box(lat: float, lon: float, radius_km: float) -> tuple:
    """Return (lat_min, lat_max, lon_min, lon_max) for the given centre and radius."""
    lat_delta = radius_km / 111.0
    lon_delta = radius_km / (111.0 * math.cos(math.radians(lat)))
    return lat - lat_delta, lat + lat_delta, lon - lon_delta, lon + lon_delta


# ---------------------------------------------------------------------------
# Stage 1 — OpenSky state vectors
# ---------------------------------------------------------------------------

def fetch_state_vectors(center_lat: float, center_lon: float, radius_km: float) -> list[dict]:
    """
    Fetch ADS-B state vectors from OpenSky Network (anonymous, no auth).
    Filters results to within radius_km of the centre point.

    OpenSky states array field indices:
      0  icao24          4  spi             8  on_ground      12  sensors
      1  callsign        5  longitude       9  velocity       13  geo_altitude
      2  origin_country  6  latitude       10  true_track     14  squawk
      3  time_position   7  baro_altitude  11  vertical_rate  15  position_source
                                                              16  category
    """
    lat_min, lat_max, lon_min, lon_max = bounding_box(center_lat, center_lon, radius_km)
    url = (
        f"{OPENSKY_BASE}/api/states/all"
        f"?lamin={lat_min:.6f}&lamax={lat_max:.6f}"
        f"&lomin={lon_min:.6f}&lomax={lon_max:.6f}"
    )

    have_creds = bool(_creds["client_id"] and _creds["client_secret"])

    # Use the free anonymous bucket first to conserve account credits; only fall
    # back to the authenticated (keyed) bucket if anonymous is rate-limited (429).
    resp = requests.get(url, timeout=15)
    _record_rate("anonymous", resp)
    mode = "anonymous"
    if resp.status_code == 429 and have_creds:
        token = _opensky_token_get()
        if token:
            resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=15)
            _record_rate("authenticated", resp)
            mode = "authenticated"
    _opensky_rate["last_mode"] = mode

    if resp.status_code == 429:
        raise OpenSkyRateLimit(
            "OpenSky rate limit reached (429) on both anonymous and authenticated "
            "buckets. Please wait ~1 minute (or add credentials for a higher limit)."
            if have_creds else
            "OpenSky anonymous rate limit reached (429). Add a free OpenSky account "
            "in Settings for a higher limit, or wait ~1 minute."
        )
    resp.raise_for_status()
    states = resp.json().get("states") or []

    result = []
    for s in states:
        if len(s) < 17:
            continue
        lat = s[6]
        lon = s[5]
        if lat is None or lon is None:
            continue
        dist = haversine_km(center_lat, center_lon, lat, lon)
        if dist > radius_km:
            continue
        result.append({
            "icao24": s[0] or "",
            "callsign": (s[1] or "").strip(),
            "origin_country": s[2] or "",
            "lat": lat,
            "lon": lon,
            "altitude_m": s[7],
            "on_ground": bool(s[8]),
            "velocity_ms": s[9],
            "heading_deg": s[10],
            "vertical_rate": s[11],
            "distance_km": round(dist, 1),
            "bearing_deg": round(bearing_deg(center_lat, center_lon, lat, lon), 1),
        })
    return result


# ---------------------------------------------------------------------------
# Stage 2 — hexdb.io aircraft type lookup
# ---------------------------------------------------------------------------

def get_aircraft_type(icao24: str) -> str:
    """Return ICAO type code (e.g. 'B738') for the given ICAO24 hex, or ''."""
    if not icao24:
        return ""
    try:
        resp = requests.get(f"{HEXDB_BASE}/api/v1/aircraft/{icao24}", timeout=5)
        if resp.status_code == 200:
            return resp.json().get("ICAOTypeCode", "") or ""
    except Exception:
        pass
    return ""


def extract_airline_icao(callsign: str) -> str:
    """
    Extract 3-letter ICAO airline prefix from callsign.
    e.g. 'UAL123' -> 'UAL', 'BAW456' -> 'BAW'
    Returns '' if the callsign has fewer than 3 leading alpha characters.
    """
    prefix = ""
    for ch in callsign:
        if ch.isalpha():
            prefix += ch
        else:
            break
    return prefix[:3].upper() if len(prefix) >= 3 else ""


# ---------------------------------------------------------------------------
# Stage 4 — adsbdb.com flight route (origin / destination)
# ---------------------------------------------------------------------------

def _airport_summary(ap: dict) -> dict:
    """Reduce an adsbdb airport object to the fields the UI needs."""
    return {
        "iata": ap.get("iata_code", "") or "",
        "icao": ap.get("icao_code", "") or "",
        "name": ap.get("name", "") or "",
        "city": ap.get("municipality", "") or "",
        "country": ap.get("country_name", "") or "",
        "country_iso": ap.get("country_iso_name", "") or "",
        "lat": ap.get("latitude"),
        "lon": ap.get("longitude"),
    }


def get_route(callsign: str) -> dict:
    """
    Look up a flight's route + IATA flight number from adsbdb.com (free, keyless).
    Returns {"origin", "destination", "flight_iata", "airline_callsign"}.
    Cached per callsign for ROUTE_CACHE_TTL to limit upstream calls.
    """
    empty = {"origin": None, "destination": None, "flight_iata": "", "airline_callsign": "", "airline_iata": ""}
    if not callsign:
        return empty

    now = time.time()
    cached = _route_cache.get(callsign)
    if cached is not None and (now - cached["ts"]) < ROUTE_CACHE_TTL:
        return cached["data"]

    result = dict(empty)
    try:
        resp = requests.get(f"{ADSBDB_BASE}/v0/callsign/{callsign}", timeout=5)
        if resp.status_code == 200:
            route = resp.json().get("response", {}).get("flightroute", {})
            origin = route.get("origin")
            destination = route.get("destination")
            airline = route.get("airline") or {}
            result = {
                "origin": _airport_summary(origin) if origin else None,
                "destination": _airport_summary(destination) if destination else None,
                "flight_iata": route.get("callsign_iata", "") or "",
                "airline_callsign": airline.get("callsign", "") or "",
                "airline_iata": airline.get("iata", "") or "",
            }
    except Exception:
        pass

    _route_cache[callsign] = {"data": result, "ts": now}
    return result


# ---------------------------------------------------------------------------
# Stage 5 — adsbdb.com aircraft details (registration / owner / photo)
# ---------------------------------------------------------------------------

def get_aircraft_details(icao24: str) -> dict:
    """
    Look up aircraft metadata from adsbdb.com by ICAO24 (Mode-S) hex.
    Returns registration, manufacturer, type code, owner, owner country, photo.
    Cached per icao24 for ROUTE_CACHE_TTL (registrations rarely change).
    """
    empty = {
        "registration": "", "manufacturer": "", "type_code": "",
        "owner": "", "owner_country": "", "photo": "", "photo_thumb": "",
    }
    if not icao24:
        return empty

    now = time.time()
    cached = _aircraft_cache.get(icao24)
    if cached is not None and (now - cached["ts"]) < ROUTE_CACHE_TTL:
        return cached["data"]

    result = dict(empty)
    try:
        resp = requests.get(f"{ADSBDB_BASE}/v0/aircraft/{icao24}", timeout=5)
        if resp.status_code == 200:
            ac = resp.json().get("response", {}).get("aircraft", {}) or {}
            result = {
                "registration": ac.get("registration", "") or "",
                "manufacturer": ac.get("manufacturer", "") or "",
                "type_code": ac.get("icao_type", "") or "",
                "owner": ac.get("registered_owner", "") or "",
                "owner_country": ac.get("registered_owner_country_name", "") or "",
                "photo": ac.get("url_photo", "") or "",
                "photo_thumb": ac.get("url_photo_thumbnail", "") or "",
            }
    except Exception:
        pass

    _aircraft_cache[icao24] = {"data": result, "ts": now}
    return result


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def compute_progress(origin, destination, lat, lon, speed_kmh) -> dict:
    """
    Derive flight progress from route endpoints, current position and speed.
    All values are approximate (great-circle, constant speed). Returns keys:
    route_total_km, travelled_km, remaining_km, progress_pct, eta_min.
    Any value that can't be computed is None.
    """
    out = {
        "route_total_km": None, "travelled_km": None,
        "remaining_km": None, "progress_pct": None, "eta_min": None,
    }
    has_o = origin and origin.get("lat") is not None
    has_d = destination and destination.get("lat") is not None
    if has_o:
        out["travelled_km"] = round(haversine_km(origin["lat"], origin["lon"], lat, lon), 1)
    if has_d:
        out["remaining_km"] = round(haversine_km(lat, lon, destination["lat"], destination["lon"]), 1)
    if has_o and has_d:
        out["route_total_km"] = round(haversine_km(
            origin["lat"], origin["lon"], destination["lat"], destination["lon"]), 1)
        denom = out["travelled_km"] + out["remaining_km"]
        if denom > 0:
            out["progress_pct"] = max(0, min(100, round(out["travelled_km"] / denom * 100)))
    if out["remaining_km"] is not None and speed_kmh and speed_kmh > 50:
        out["eta_min"] = round(out["remaining_km"] / speed_kmh * 60)
    return out


def fetch_flights(center_lat: float, center_lon: float, radius_km: float) -> list[dict]:
    """Run the full pipeline: state vectors → aircraft type → display names → progress."""
    vectors = fetch_state_vectors(center_lat, center_lon, radius_km)
    flights = []
    for sv in vectors:
        if not sv["callsign"]:
            continue

        aircraft_code = get_aircraft_type(sv["icao24"])
        airline_icao = extract_airline_icao(sv["callsign"])
        route = get_route(sv["callsign"])
        details = get_aircraft_details(sv["icao24"])
        # Fall back to adsbdb's type code if hexdb has none.
        if not aircraft_code:
            aircraft_code = details["type_code"]

        alt_m = sv["altitude_m"]
        vel_ms = sv["velocity_ms"]
        speed_kmh = round(vel_ms * 3.6) if vel_ms is not None else None

        progress = compute_progress(
            route["origin"], route["destination"], sv["lat"], sv["lon"], speed_kmh)

        flights.append({
            **sv,
            "airline_icao": airline_icao,
            "airline_callsign": route["airline_callsign"],
            "airline_iata": route["airline_iata"],
            "aircraft_code": aircraft_code,
            "flight_iata": route["flight_iata"],
            "origin": route["origin"],
            "destination": route["destination"],
            # Aircraft metadata (adsbdb)
            "registration": details["registration"],
            "manufacturer": details["manufacturer"],
            "owner": details["owner"],
            "owner_country": details["owner_country"],
            "photo": details["photo"],
            "photo_thumb": details["photo_thumb"],
            # Unit conversions for the UI
            "altitude_ft": round(alt_m * 3.28084) if alt_m is not None else None,
            "speed_kts": round(vel_ms * 1.94384, 1) if vel_ms is not None else None,
            "speed_kmh": speed_kmh,
            # Computed flight progress
            **progress,
        })
    return flights


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/api/flights")
def api_flights():
    # Location + radius come from query params (browser geolocation / UI).
    # There is no server-side default — the client must supply them.
    lat_arg = request.args.get("lat")
    lon_arg = request.args.get("lon")
    if lat_arg is None or lon_arg is None:
        return jsonify({"error": "Location required (lat & lon query params)"}), 400
    try:
        lat = float(lat_arg)
        lon = float(lon_arg)
        radius = float(request.args.get("radius", DEFAULT_RADIUS_KM))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid lat/lon/radius"}), 400

    # Cache keyed by rounded location so distinct clients don't collide.
    key = (round(lat, 3), round(lon, 3), round(radius, 1))
    now = time.time()
    cached = _cache.get(key)
    if cached is not None and (now - cached["ts"]) < CACHE_TTL:
        return jsonify(cached["data"])
    try:
        data = fetch_flights(lat, lon, radius)
        _cache[key] = {"data": data, "ts": now}
        return jsonify(data)
    except OpenSkyRateLimit as exc:
        # Serve slightly stale data if we have any; otherwise report the limit.
        if cached is not None:
            return jsonify(cached["data"])
        return jsonify({"error": str(exc), "rate_limited": True}), 429
    except Exception as exc:
        if cached is not None:
            return jsonify(cached["data"])   # fall back to stale data on any error
        return jsonify({"error": str(exc)}), 500


@app.route("/")
def index():
    return render_template("index.html", default_radius=DEFAULT_RADIUS_KM)


@app.route("/api/config", methods=["GET"])
def get_config():
    """Report OpenSky auth status + last-seen rate limit (never returns the secret)."""
    return jsonify({
        "configured": bool(_creds["client_id"] and _creds["client_secret"]),
        "client_id_masked": _masked_id(),
        "source": _creds["source"],
        "rate": {
            "anonymous": _opensky_rate["anonymous"]["remaining"],
            "authenticated": _opensky_rate["authenticated"]["remaining"],
            "last_mode": _opensky_rate["last_mode"],
            "retry_after": _opensky_rate["retry_after"],
        },
    })


@app.route("/api/config", methods=["POST"])
def set_config():
    """Validate and store OpenSky credentials supplied from the UI."""
    body = request.get_json(silent=True) or {}
    cid = (body.get("client_id") or "").strip()
    csec = (body.get("client_secret") or "").strip()
    if not cid or not csec:
        return jsonify({"ok": False, "error": "Both client_id and client_secret are required."}), 400
    token, _ = _opensky_fetch_token(cid, csec)
    if not token:
        return jsonify({"ok": False, "error": "OpenSky rejected these credentials."}), 400
    _save_creds(cid, csec)
    return jsonify({"ok": True, "configured": True, "client_id_masked": _masked_id(), "source": "ui"})


@app.route("/api/config", methods=["DELETE"])
def delete_config():
    """Clear UI-saved credentials (revert to env vars or anonymous)."""
    _clear_creds()
    return jsonify({
        "ok": True,
        "configured": bool(_creds["client_id"] and _creds["client_secret"]),
        "client_id_masked": _masked_id(),
        "source": _creds["source"],
    })


if __name__ == "__main__":
    mode = "authenticated (OAuth)" if (_creds["client_id"] and _creds["client_secret"]) else "anonymous"
    print(f"OpenSky access: {mode}")
    app.run(debug=True, port=5000)
