"""
Severe Weather Monitor - backend (V1, steps 0-1)

Polls the National Weather Service active-alerts API, filters to storm-based
warnings that carry map polygons, caches them, and serves them to the dashboard.

This is the "brain" half of the brain/screen split we planned. Later steps
extend THIS file and leave the frontend dumb:
  - Step 2 (radar): no backend change needed; radar tiles are added client-side.
  - Step 3 (engine): add ranking + a /api/focus endpoint that names the warning
    to fly to. The frontend just reads it.
  - Step 4-6 (cameras / station obs / LSRs): add lookups keyed off the focus.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# NWS REQUIRES a User-Agent that identifies your app plus a contact. EDIT THIS
# before running - put your real email or site. Requests with a generic or
# missing User-Agent may be throttled or blocked.
USER_AGENT = "SevereWeatherMonitor/0.1 (tristanace2@gmail.com)"

NWS_ACTIVE_ALERTS = "https://api.weather.gov/alerts/active"
POLL_SECONDS = 45

# Storm-based warnings that carry polygon geometry. Add or remove freely - drop
# Flood Warning if it's too noisy, or add advisory/watch events later. Zone-based
# products (most winter/heat advisories) usually have no polygon and won't draw.
WARNING_EVENTS = {
    "Tornado Warning",
    "Severe Thunderstorm Warning",
    "Flash Flood Warning",
    "Flood Warning",
    "Special Marine Warning",
    "Snow Squall Warning",
    "Dust Storm Warning",
    "Extreme Wind Warning",
}

# Keep only the properties the dashboard uses, to slim the payload.
KEEP_PROPS = ("event", "severity", "certainty", "headline",
              "areaDesc", "onset", "expires", "ends")

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger("monitor")

STATIC_DIR = Path(__file__).parent / "static"

# ---------------------------------------------------------------------------
# In-memory state (the cache the API serves)
# ---------------------------------------------------------------------------

_state: dict = {
    "type": "FeatureCollection",
    "features": [],
    "updated": None,   # ISO timestamp of the last SUCCESSFUL poll
    "count": 0,
}


def _slim(feature: dict) -> dict:
    props = feature.get("properties") or {}
    return {
        "type": "Feature",
        "geometry": feature.get("geometry"),
        "properties": {k: props.get(k) for k in KEEP_PROPS},
    }


async def _poll_once(client: httpx.AsyncClient) -> None:
    resp = await client.get(
        NWS_ACTIVE_ALERTS,
        params={"status": "actual"},
        headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    features = []
    for f in data.get("features", []):
        # Many alerts (zone-based watches/advisories) have geometry=None - we
        # can't draw those as polygons, so skip them in V1.
        if not f.get("geometry"):
            continue
        event = (f.get("properties") or {}).get("event")
        if event in WARNING_EVENTS:
            features.append(_slim(f))

    _state["features"] = features
    _state["count"] = len(features)
    _state["updated"] = dt.datetime.now(dt.timezone.utc).isoformat()
    log.info("polled NWS: %d active storm-based warnings", len(features))


async def _poll_loop() -> None:
    async with httpx.AsyncClient() as client:
        while True:
            try:
                await _poll_once(client)
            except Exception as exc:  # keep last-good data on ANY failure
                log.warning("NWS poll failed (serving last-good data): %s", exc)
            await asyncio.sleep(POLL_SECONDS)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_poll_loop())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title="Severe Weather Monitor", lifespan=lifespan)


@app.get("/api/alerts")
async def alerts() -> JSONResponse:
    """Current active storm-based warnings as a GeoJSON FeatureCollection."""
    return JSONResponse(_state)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


# Mounted for any future local assets; the frontend currently uses CDNs only.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)