# Severe Weather Monitor - V1 (steps 0-1)

The first runnable slice: a full-screen dark US map that renders **live national
storm-based warnings** from the National Weather Service, captured by OBS and
pushed to YouTube. This is the pipe plus the warning layer - everything else
(radar, the focus engine, cameras, station obs, LSRs) builds on top of it.

Architecture is split brain / screen, as planned:
- `server.py` - the brain. Polls NWS every 45s, filters to storm-based warnings
  with polygons, caches them, serves them at `/api/alerts`.
- `static/index.html` - the screen. MapLibre dashboard that renders whatever the
  API reports, with a live color-keyed warning tally, clock, and freshness state.

## Setup

```bash
cd weather-stream
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

**Before first run, edit `USER_AGENT` near the top of `server.py`** - put your
real email or site. NWS requires a meaningful User-Agent and may block generic
ones.

## Run

```bash
python server.py          # or: uvicorn server:app --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000>. You'll see the map immediately; warning polygons
appear on the next poll. (If the country is quiet, the tally reads 0 - that's
correct, not a bug. Test during active weather, or temporarily widen
`WARNING_EVENTS`.)

## Point OBS at it

1. **Sources -> + -> Browser**. URL `http://localhost:8000`, Width `1920`,
   Height `1080`, FPS `30`.
2. **Settings -> Video**: Base and Output resolution `1920x1080`.
3. **Settings -> Stream**: Service `YouTube`, paste your stream key from
   YouTube Studio -> Go Live -> Stream.
4. **Start Streaming.** (Encoder/desktop streaming has no subscriber minimum -
   you just need a verified channel with live streaming enabled.)

The dashboard is a fixed 1920x1080 broadcast canvas, so capture it at that size
for a pixel-perfect result.

## Tuning

- `WARNING_EVENTS` in `server.py` - which event types to show. Zone-based
  products (most winter/heat advisories) have no polygon and won't draw.
- `POLL_SECONDS` - how often the backend hits NWS (45s is polite; don't go below
  ~30s).
- `EVENT_COLORS` in `index.html` - warning colors (kept to NWS convention).

## Where the next steps plug in

- **Step 2 (radar):** add a radar raster source/layer in `index.html` at the
  marked spot, below the warning fill. No backend change.
- **Step 3 (engine):** add ranking + a `/api/focus` endpoint in `server.py`; the
  frontend reads it and calls `map.flyTo()`.
- **Steps 4-6 (cameras / station obs / LSRs):** backend lookups keyed off the
  focused warning.

Unofficial project - not an official source of weather warnings. Always defer to
the NWS.