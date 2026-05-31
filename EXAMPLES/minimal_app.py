"""minimal_app.py — the smallest viable shop-agent.

Exposes one widget showing live CPU usage and SoC temperature from /proc
and /sys, advertised on the LAN via Bonjour so the
"Leave Me to My Own Devices" visionOS app discovers it automatically.

Quick start on a Raspberry Pi:

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    .venv/bin/python -m uvicorn minimal_app:app --host 0.0.0.0 --port 8765

Or, equivalently:

    .venv/bin/python minimal_app.py

Then open the Vision Pro app. The Pi shows up under "Discovered on
network" within a few seconds.

To expose your own data:

  1. Replace `snapshot()` with a function that returns a dict of the
     keys your widget needs.
  2. Update the `MANIFESTS["system"]["compact"]/["panel"]` trees so the
     `bind` fields reference those keys.
  3. (Optional) add `@app.post(...)` handlers and `toggle`/`button`/
     `slider` nodes in the manifest to interact with your hardware.

Full schema reference: see ../README.md.
"""
from __future__ import annotations

import asyncio
import json
import socket
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from zeroconf import IPVersion, ServiceInfo
from zeroconf.asyncio import AsyncZeroconf

# ---- Config --------------------------------------------------------------

DEVICE_ID    = socket.gethostname().split(".")[0]
DEVICE_LABEL = f"{DEVICE_ID} (demo)"
PORT         = 8765

# ---- Catalog -------------------------------------------------------------
# One row per widget this device offers.

WIDGETS = [
    {
        "id": "system",
        "name": "System Status",
        "short_name": "System",
        "summary": "CPU usage and SoC temperature for this device.",
        "icon": "cpu",         # any SF Symbol name
        "tint": "blue",        # see README for the palette
    },
]

# ---- SDUI manifest -------------------------------------------------------
# What the widget LOOKS LIKE. The Vision Pro app renders this natively in
# SwiftUI Glass — there is no HTML or web view involved.
#
# Keys named in "bind" come from snapshot(); they're matched on every WS
# frame and the components re-render automatically when values change.

MANIFESTS: dict[str, dict] = {
    "system": {
        "id": "system",
        "title": "System Status",
        "icon": "cpu",
        "tint": "blue",
        "stream_path": "/widget/system/stream",
        "compact": {
            "type": "vstack", "spacing": 10,
            "children": [
                {"type": "stat_grid", "columns": 2, "fields": [
                    {"label": "CPU",  "bind": "cpu_pct", "unit": "%",  "format": "%.0f",
                     "symbol": "cpu",                "tint": "blue"},
                    {"label": "Temp", "bind": "temp_c", "unit": "°C", "format": "%.1f",
                     "symbol": "thermometer.medium", "tint": "orange"},
                ]},
            ],
        },
        "panel": {
            "type": "vstack", "spacing": 22,
            "children": [
                {"type": "stat_grid", "columns": 2, "fields": [
                    {"label": "CPU",  "bind": "cpu_pct", "unit": "%",  "format": "%.0f",
                     "symbol": "cpu",                "tint": "blue"},
                    {"label": "Temp", "bind": "temp_c", "unit": "°C", "format": "%.1f",
                     "symbol": "thermometer.medium", "tint": "orange"},
                ]},
                {"type": "section", "title": "Host", "children": [
                    {"type": "text", "value": DEVICE_LABEL, "style": "headline"},
                ]},
            ],
        },
    },
}

# ---- Live data -----------------------------------------------------------
# Replace this section with whatever you actually want streamed. The
# return-dict keys must match every `bind` in the manifest.

_last_total: int | None = None
_last_idle: int | None = None


def cpu_percent() -> float:
    """Delta-based CPU usage from /proc/stat's aggregate line."""
    global _last_total, _last_idle
    try:
        nums = [int(x) for x in Path("/proc/stat").read_text().splitlines()[0].split()[1:]]
        idle = nums[3] + (nums[4] if len(nums) > 4 else 0)  # idle + iowait
        total = sum(nums)
    except Exception:
        return 0.0

    if _last_total is None:
        _last_total, _last_idle = total, idle
        return 0.0

    d_total = total - _last_total
    d_idle = idle - (_last_idle or 0)
    _last_total, _last_idle = total, idle

    if d_total <= 0:
        return 0.0
    return max(0.0, min(100.0, 100.0 * (d_total - d_idle) / d_total))


def temperature_c() -> float:
    """SoC temperature in °C from thermal zone 0 (works on Pi)."""
    try:
        return int(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000.0
    except Exception:
        return 0.0


def snapshot() -> dict:
    """One frame of live data — keys are the `bind` names in the manifest."""
    return {
        "cpu_pct": round(cpu_percent(), 1),
        "temp_c":  round(temperature_c(), 1),
    }


# ---- HTTP, WebSocket, Bonjour --------------------------------------------

def _lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    azc = AsyncZeroconf(ip_version=IPVersion.V4Only)
    info = ServiceInfo(
        type_="_shopwidget._tcp.local.",
        name=f"{DEVICE_LABEL}._shopwidget._tcp.local.",
        addresses=[socket.inet_aton(_lan_ip())],
        port=PORT,
        properties={
            "device_id":    DEVICE_ID,
            "label":        DEVICE_LABEL,
            "version":      "1",
            "catalog_path": "/catalog",
            "auth":         "none",
        },
        server=f"{socket.gethostname()}.local.",
    )
    await azc.async_register_service(info)
    print(f"[shop-agent] published {info.name} -> {_lan_ip()}:{PORT}", flush=True)
    try:
        yield
    finally:
        await azc.async_unregister_service(info)
        await azc.async_close()


app = FastAPI(lifespan=lifespan, title="shop-agent (minimal)")


@app.get("/")
async def root():
    return {
        "device_id": DEVICE_ID,
        "label":     DEVICE_LABEL,
        "catalog":   "/catalog",
        "auth":      "none",
    }


@app.get("/catalog")
async def catalog():
    return {
        "device_id": DEVICE_ID,
        "label":     DEVICE_LABEL,
        "widgets":   [{**w, "manifest_path": f"/widget/{w['id']}/manifest"} for w in WIDGETS],
    }


@app.get("/widget/{widget_id}/manifest")
async def widget_manifest(widget_id: str):
    return MANIFESTS[widget_id]


@app.websocket("/widget/{widget_id}/stream")
async def widget_stream(ws: WebSocket, widget_id: str):
    await ws.accept()
    try:
        # Send one frame immediately so the widget paints something fast,
        # then a fresh frame every 500 ms.
        await ws.send_text(json.dumps(snapshot()))
        while True:
            await asyncio.sleep(0.5)
            await ws.send_text(json.dumps(snapshot()))
    except WebSocketDisconnect:
        return


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
