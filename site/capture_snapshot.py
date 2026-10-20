"""
Record a snapshot of real flights for the GitHub Pages replay demo.

Start the dev server first (`uv run python app.py`), then:

    python3 site/capture_snapshot.py [--lat 51.46 --lon -0.30 --radius 25 --label "Richmond, London"]

Writes site/snapshot.json, which site/build.py embeds into the demo page.
On-ground aircraft are dropped: they never move in the replay and only add weight.
"""

import argparse
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).with_name("snapshot.json")


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

    airborne = [f for f in flights if not f.get("on_ground")]
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
