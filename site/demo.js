/*
 * OpenFlightWall replay demo (GitHub Pages).
 *
 * GitHub Pages cannot run the Flask backend, and OpenSky only accepts browser
 * requests from its own origin, so the demo replays a recorded snapshot of real
 * flights instead (site/snapshot.json, embedded by site/build.py). Airborne
 * planes keep flying along their heading at their ground speed, and the whole
 * replay loops every few minutes.
 *
 * This file runs before the dashboard's own script and sets window.OFW_DEMO,
 * which templates/index.html checks in start() and loadFlights().
 */
(function () {
  const snapshot = JSON.parse(document.getElementById('ofw-snapshot').textContent);
  const LOOP_MS = 6 * 60_000;      // restart the replay so planes do not all fly away
  const startedAt = Date.now();
  const PIN_MS = 65_000;           // a little longer than the alert's 1-minute auto-dismiss
  let pinnedIcao = null, pinnedUntil = 0;

  const toRad = (d) => d * Math.PI / 180;
  const toDeg = (r) => r * 180 / Math.PI;

  // Same maths as haversine_km / bearing_deg in app.py and destinationPoint() in the UI.
  function haversineKm(lat1, lon1, lat2, lon2) {
    const dLat = toRad(lat2 - lat1), dLon = toRad(lon2 - lon1);
    const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
    return 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }
  function bearingDeg(lat1, lon1, lat2, lon2) {
    const y = Math.sin(toRad(lon2 - lon1)) * Math.cos(toRad(lat2));
    const x = Math.cos(toRad(lat1)) * Math.sin(toRad(lat2))
            - Math.sin(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.cos(toRad(lon2 - lon1));
    return (toDeg(Math.atan2(y, x)) + 360) % 360;
  }
  function destination(lat, lon, bearing, km) {
    const d = km / 6371, b = toRad(bearing), p1 = toRad(lat), l1 = toRad(lon);
    const p2 = Math.asin(Math.sin(p1) * Math.cos(d) + Math.cos(p1) * Math.sin(d) * Math.cos(b));
    const l2 = l1 + Math.atan2(Math.sin(b) * Math.sin(d) * Math.cos(p1), Math.cos(d) - Math.sin(p1) * Math.sin(p2));
    return [toDeg(p2), toDeg(l2)];
  }

  // Flights as they would be `elapsed` ms into the replay, relative to `loc`.
  function flights(loc, radiusKm) {
    const hours = ((Date.now() - startedAt) % LOOP_MS) / 3_600_000;
    return snapshot.flights.map((src) => {
      const f = JSON.parse(JSON.stringify(src));
      if (!f.on_ground && f.speed_kmh && f.heading_deg != null) {
        [f.lat, f.lon] = destination(f.lat, f.lon, f.heading_deg, f.speed_kmh * hours);
      }
      f.distance_km = Math.round(haversineKm(loc.lat, loc.lon, f.lat, f.lon) * 10) / 10;
      if (f.icao24 === pinnedIcao && Date.now() < pinnedUntil) f.distance_km = Math.min(f.distance_km, 1.2);
      f.bearing_deg = Math.round(bearingDeg(loc.lat, loc.lon, f.lat, f.lon) * 10) / 10;
      return f;
    }).filter((f) => f.distance_km <= radiusKm);
  }

  window.OFW_DEMO = { center: snapshot.center, pollMs: 10_000, flights };

  // ── Demo banner ──
  const captured = new Date(snapshot.captured_at).toLocaleDateString([], { day: 'numeric', month: 'long', year: 'numeric' });
  const style = document.createElement('style');
  style.textContent = `
    .demo-banner {
      position: fixed; left: 1rem; bottom: 1rem; z-index: 1600; max-width: min(560px, calc(100vw - 2rem));
      background: #161b22; border: 1px solid #30363d; border-left: 3px solid #3fb950; border-radius: 10px;
      padding: 0.75rem 0.9rem; box-shadow: 0 8px 28px #000a; font-size: 0.8rem; color: #e6edf3;
      font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    }
    .demo-banner b { color: #3fb950; }
    .demo-banner .demo-actions { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.6rem; }
    .demo-banner button, .demo-banner a.demo-btn {
      background: #21262d; border: 1px solid #30363d; color: #e6edf3; border-radius: 6px;
      padding: 0.3rem 0.65rem; font-size: 0.75rem; cursor: pointer; text-decoration: none;
    }
    .demo-banner .primary { background: #1f6feb; border-color: #1f6feb; color: #fff; }
    .demo-banner .demo-close { position: absolute; top: 0.35rem; right: 0.45rem; background: none; border: none; color: #8b949e; }
    body.wall-mode .demo-banner { display: none; }
  `;
  document.head.appendChild(style);

  // Feature the nearest airborne plane as if it were overhead, so visitors do
  // not have to wait for one to fly over the snapshot's centre. It stays
  // "overhead" for PIN_MS so the next refresh does not close the alert.
  function showOverhead() {
    const nearest = latestFlights.filter((f) => !f.on_ground && f.distance_km != null)
      .sort((a, b) => a.distance_km - b.distance_km)[0];
    if (!nearest) return;
    pinnedIcao = nearest.icao24;
    pinnedUntil = Date.now() + PIN_MS;
    overheadDismissed = null;
    document.getElementById('overhead').dataset.icao = '';
    latestFlights = latestFlights.map((f) => (f === nearest ? { ...f, distance_km: 1.2 } : f));
    checkOverhead();
  }

  window.addEventListener('DOMContentLoaded', () => {
    const el = document.createElement('div');
    el.className = 'demo-banner';
    el.innerHTML = `
      <button class="demo-close" title="Hide">✕</button>
      <b>Demo</b> · replaying real flights recorded near ${snapshot.center.label} on ${captured}.
      Planes keep flying along their headings; the replay loops every few minutes.
      <div class="demo-actions">
        <button data-act="overhead">Show overhead alert</button>
        <button data-act="wall">Try wall mode</button>
        <a class="demo-btn primary" href="../#quickstart">Run it yourself →</a>
      </div>`;
    el.addEventListener('click', (e) => {
      const act = e.target.closest('[data-act]')?.dataset.act;
      if (act === 'overhead') showOverhead();
      if (act === 'wall') toggleWall(true, true);
      if (e.target.closest('.demo-close')) el.remove();
    });
    document.body.appendChild(el);
  });
})();
