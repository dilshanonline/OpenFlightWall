"""
Record aircraft positions for the GitHub Pages replay demo.

Start the dev server first (`uv run python app.py`), then:

    python3 site/capture_snapshot.py [--lat 51.46 --lon -0.30 --radius 25 --label "Richmond, London"]

Writes site/snapshot.json, which site/build.py embeds into the demo page.
On-ground aircraft are dropped: they never move in the replay and only add weight.

Routes and flight numbers are removed. adsbdb's route data "may not be copied,
published, or incorporated into other databases" without its owner's permission,
and this file is published on GitHub Pages. To show routes in the demo, add
hand-written samples afterwards: replace each callsign and flight_iata, then set
origin, destination and the progress fields, using airport details from elsewhere.
"""

import argparse
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).with_name("snapshot.json")
ROUTE_FIELDS = ("origin", "destination", "route_total_km", "travelled_km",
                "remaining_km", "progress_pct", "eta_min")


def strip_route(flight: dict) -> dict:
    """Return the flight without adsbdb route data."""
    return {**flight, **dict.fromkeys(ROUTE_FIELDS), "flight_iata": ""}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lat", type=float, default=51.46)
    ap.add_argument("--lon", type=float, default=-0.30)
    ap.add_argument("--radius", type=float, default=25)
    ap.add_argument("--label", default="Richmond, London")
    ap.add_argument("--server", default="http://localhost:5050")
    args = ap.parse_args()

    query = urllib.parse.urlencode({"lat": args.lat, "lon": args.lon, "radius": args.radius})
    with urllib.request.urlopen(f"{args.server}/api/flights?{query}", timeout=60) as resp:
        flights = json.load(resp)
    if not isinstance(flights, list):
        raise SystemExit(f"Unexpected response from /api/flights: {flights}")

    airborne = [strip_route(f) for f in flights if not f.get("on_ground")]
    snapshot = {
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "center": {"lat": args.lat, "lon": args.lon, "label": args.label},
        "radius_km": args.radius,
        "flights": airborne,
    }
    OUT.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(airborne)} airborne flights ({len(flights)} total) to {OUT}")


if __name__ == "__main__":
    main()
