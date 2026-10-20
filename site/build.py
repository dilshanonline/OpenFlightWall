"""
Assemble the GitHub Pages site into _site/ (Python stdlib only, no npm).

    python3 site/build.py              # build only (what the Pages workflow runs)
    python3 site/build.py --serve      # build, then preview at http://localhost:8000/

Open the built site, not site/index.html directly: the screenshots and the
demo/ page only exist in _site/.

Output:
  _site/index.html          landing page (site/index.html)
  _site/screenshots/*.png   copied from docs/screenshots/
  _site/demo/index.html     the real dashboard (templates/index.html) with the
                            recorded snapshot and site/demo.js injected
  _site/demo/demo.js
"""

import argparse
import functools
import http.server
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
OUT = ROOT / "_site"

# Anchors in templates/index.html the demo build depends on. If the template
# changes so these disappear, fail loudly rather than ship a broken demo.
RADIUS_ANCHOR = "{{ default_radius }}"
SCRIPT_ANCHOR = "\n  <script>\n"   # the dashboard's main inline script


def build_demo(dest: Path) -> None:
    template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    snapshot = json.loads((SITE / "snapshot.json").read_text(encoding="utf-8"))

    for anchor in (RADIUS_ANCHOR, SCRIPT_ANCHOR):
        if template.count(anchor) != 1:
            raise SystemExit(f"build.py: expected exactly one {anchor!r} in templates/index.html "
                             f"(found {template.count(anchor)}); update the demo build anchors.")

    # "</" must not appear inside the inline JSON or it could close the tag.
    data = json.dumps(snapshot, ensure_ascii=False).replace("</", "<\\/")
    inject = (f'\n  <script id="ofw-snapshot" type="application/json">{data}</script>'
              f'\n  <script src="demo.js"></script>{SCRIPT_ANCHOR}')
    page = (template
            .replace(RADIUS_ANCHOR, str(snapshot["radius_km"]))
            .replace(SCRIPT_ANCHOR, inject)
            .replace("<title>OpenFlightWall</title>", "<title>OpenFlightWall · Demo</title>"))

    dest.mkdir(parents=True)
    (dest / "index.html").write_text(page, encoding="utf-8")
    shutil.copy2(SITE / "demo.js", dest / "demo.js")


def serve(port: int) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(OUT))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        print(f"Serving {OUT.relative_to(ROOT)}/ at http://localhost:{port}/  (demo: http://localhost:{port}/demo/)  — Ctrl+C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the GitHub Pages site into _site/.")
    ap.add_argument("--serve", action="store_true", help="preview the built site locally after building")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copy2(SITE / "index.html", OUT / "index.html")
    shutil.copytree(ROOT / "docs" / "screenshots", OUT / "screenshots")
    build_demo(OUT / "demo")
    (OUT / ".nojekyll").touch()   # serve files as-is, no Jekyll processing
    print(f"Built {OUT.relative_to(ROOT)}/: " + ", ".join(
        sorted(str(p.relative_to(OUT)) for p in OUT.rglob("*") if p.is_file() and p.suffix != ".png")))
    if args.serve:
        serve(args.port)


if __name__ == "__main__":
    main()
