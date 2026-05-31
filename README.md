# lmToMyOwnDevices — public schema reference

Everything an AI coding assistant needs to expose a Raspberry Pi project
(or any Linux device on your LAN) as a live widget in the
**Leave Me to My Own Devices** visionOS app for Apple Vision Pro.

> If you arrived here from the App Store: this is the "schema reference"
> the app's description mentions. Hand the URL to a coding AI along with
> a one-sentence description of what you want to expose, and the AI has
> everything it needs to write a working device agent for you.

---

## How to use this document

1. Pick a coding AI (Claude Code, Claude in your editor, Cursor, Aider,
   anything that can read a URL).
2. Hand it this URL: <https://github.com/gcullie/lmToMyOwnDevices-public>.
3. Tell it what you want exposed in plain English — e.g.
   *"My Pi runs a 3D printer over Klipper. Expose hotend temperature,
   bed temperature, and the current job's elapsed time as a widget, and
   add a button that pauses the print."*
4. Have it produce a single `app.py` and `requirements.txt`, drop them on
   your Pi, run them, and the Vision Pro app will discover the device on
   the LAN automatically.

The schema below is the entire surface area an agent needs to understand.

---

## What you're building

A **shop-agent**: a small Python process (FastAPI + a Bonjour publisher)
running on your Pi that:

1. **Advertises** itself on the LAN via Bonjour as service type
   `_shopwidget._tcp`.
2. **Serves a catalog** — a list of widgets this device offers
   (`GET /catalog`).
3. **For each widget**, serves a JSON manifest describing the widget's
   layout (`GET /widget/{id}/manifest`) and a live WebSocket data stream
   (`WS /widget/{id}/stream`).
4. **Receives action POSTs** — when the user taps a toggle/button/slider
   in the widget, the app POSTs back to a URL you nominated in the
   manifest.

That's it. No SDK, no client library, no cloud — just HTTP + WebSocket
spoken over the LAN.

---

## 5-minute quickstart

A complete, runnable starting point lives in
[`EXAMPLES/minimal_app.py`](EXAMPLES/minimal_app.py) — one widget
showing live CPU usage and SoC temperature read straight from `/proc`
and `/sys`. Drop it on a Pi (or a Mac, or any Linux box) on the same
LAN as your Vision Pro:

```sh
# on the Pi
mkdir ~/shop-agent && cd ~/shop-agent
curl -O https://raw.githubusercontent.com/gcullie/lmToMyOwnDevices-public/main/EXAMPLES/minimal_app.py
curl -O https://raw.githubusercontent.com/gcullie/lmToMyOwnDevices-public/main/EXAMPLES/requirements.txt
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python minimal_app.py
```

Then on the Vision Pro:

1. Open **Leave Me to My Own Devices**.
2. Your Pi appears under **Discovered on network** within a few seconds.
3. Tap **Add**, then **Browse widgets**, then **Place** the widget.

If you want the agent to start on boot, drop it in a systemd unit. (See
[Optional extras](#optional-extras) below.)

### Adapting the example to your project

`minimal_app.py` is the smallest viable shop-agent — about 180
commented lines covering everything: Bonjour publish, catalog,
manifest, WebSocket stream, real data reads. It's structured so a
coding AI (or you) only has to touch three sections:

1. **`WIDGETS`** — one entry per widget you want to offer.
2. **`MANIFESTS`** — one entry per widget, describing layout. The
   [Component reference](#component-reference) below is the full menu.
3. **`snapshot()`** — return a dict where every key matches a `bind`
   field used in your manifest.

If your widget has buttons/toggles/sliders, also add `@app.post(...)`
handlers for the action URLs you nominate. See
[Adding actions](#adding-actions) below for the recipe.

---

## Protocol reference

### Bonjour service

| Field | Value |
|---|---|
| Service type | `_shopwidget._tcp` |
| Port | typically `8765` (you choose; published in the SRV record) |
| TXT keys | `device_id` (string, short id), `label` (string, human name), `version` (string, currently `"1"`), `auth` (`"required"` or `"none"`) |

The Vision Pro app uses `bonjourWithTXTRecord` to surface those TXT
fields when it lists discovered devices.

### `GET /catalog`

Returns the list of widgets this device offers. Required.

```json
{
  "device_id": "my-pi",
  "label": "Workshop Pi",
  "widgets": [
    {
      "id": "system",
      "name": "System Status",
      "short_name": "System",
      "summary": "CPU + temperature.",
      "icon": "cpu",
      "tint": "blue",
      "manifest_path": "/widget/system/manifest"
    }
  ]
}
```

- `id` — must be URL-safe; appears in subsequent endpoint paths.
- `name` — human-readable, shown in the device's widget picker.
- `short_name` — used in compact contexts; falls back to `name`.
- `icon` — any [SF Symbols](https://developer.apple.com/sf-symbols/) name.
- `tint` — `blue`, `orange`, `teal`, `purple`, `green`, `red`, `yellow`,
  `mint`, `pink`, `indigo`, `cyan`, `gray`.
- `manifest_path` — relative URL to the widget's manifest. Convention is
  `/widget/{id}/manifest` but anything works.

### `GET /widget/{id}/manifest`

Returns the SDUI document for one widget — what it looks like and where
its live data comes from. Required.

```json
{
  "id": "system",
  "title": "System Status",
  "icon": "cpu",
  "tint": "blue",
  "stream_path": "/widget/system/stream",
  "compact": { "type": "vstack", "children": [ ... ] },
  "panel":   { "type": "vstack", "children": [ ... ] }
}
```

- `stream_path` — relative URL of the WebSocket endpoint serving live
  telemetry for the widget. Optional but almost always present.
- `compact` — the layout for the floating widget window. Keep it
  small (~360 × 320 effective).
- `panel` — the larger layout shown when the user taps the widget. No
  hard size limit; reasonable bound is ~720 × 600.

The `compact` and `panel` values are recursive trees of "nodes." Every
node has a `type` field; see [Component reference](#component-reference).

### `WS /widget/{id}/stream`

A WebSocket connection. The server pushes a JSON object roughly every
500 ms. Each key is a `bind` name referenced in the manifest:

```json
{ "cpu_pct": 23.4, "temp_c": 48.2 }
```

The app updates every component bound to those keys whenever a new
frame arrives. No client-side timestamping needed — newest frame wins.

### POST actions

A component with an `action` field POSTs back to your agent when the
user interacts with it. Example component:

```json
{
  "type": "toggle",
  "bind": "fan_enabled",
  "label_on": "Fan on",
  "label_off": "Fan off",
  "action": "POST /widget/cooling/fan"
}
```

The app sends:

```
POST /widget/cooling/fan
Content-Type: application/json

{"value": true}
```

- For toggles/sliders, `value` is the new value the user set.
- For buttons, `value` is `null` (the button just fires).
- The server responds with arbitrary JSON; the app doesn't show it,
  but a `200` status code means "applied."

Your handler should mutate state and let the next WS frame reflect the
change. The toggle's UI updates on the next frame (≤ 500 ms).

---

## Component reference

Use only these types in your manifest. The visionOS app renders each
natively as SwiftUI Glass.

| Type | Purpose | Key fields |
|---|---|---|
| `vstack` / `hstack` | Layout container | `spacing` (number), `children` (array of nodes) |
| `section` | Titled group of children | `title` (string), `children` |
| `stat_grid` | N-column grid of stat tiles | `columns` (int), `fields` (array of stat-tile specs) |
| `stat_tile` | One labelled value | `label`, `bind`, `unit`, `format`, `symbol`, `tint`, `scale` |
| `sparkline` | Time-series mini chart | `bind` → an array of numbers, `tint`, `height` |
| `gauge` | Circular meter | `bind`, `max`, `label`, `tint`, `size` |
| `toggle` | On/off switch | `bind`, `label_on`, `label_off`, `symbol_on`, `symbol_off`, `action`, `tint`, `style` (`switch` default, `button` alt) |
| `slider` | Range input | `bind`, `min`, `max`, `label`, `action`, `tint` |
| `button` | Action trigger | `label`, `symbol`, `action`, `role` (`destructive` = red) |
| `status_badge` | Coloured live pill | `bind` (bool — `false` = error, otherwise online) |
| `text` | Static or bound text | `value` *or* `bind`, `style` (`headline`/`caption`/`monospaced`) |
| `video_stream` | Live MJPEG image | `path` (relative URL serving `multipart/x-mixed-replace`), `aspect` (`"4:3"` etc.), `height`, `tint` |

**Tints.** `blue`, `orange`, `teal`, `purple`, `green`, `red`, `yellow`,
`mint`, `pink`, `indigo`, `cyan`, `gray`.

**Symbols.** Any [SF Symbols](https://developer.apple.com/sf-symbols/)
name (`cpu`, `thermometer.medium`, `bolt.fill`, `video.fill`, etc.).

**Formats.** C-style printf — `"%.0f"`, `"%.1f"`, `"%.0f%%"`, etc.

---

## Adding actions

Three small things, in order:

1. Add a `toggle` / `slider` / `button` node to your manifest with an
   `action` like `"POST /widget/foo/bar"`.
2. Add an `@app.post(...)` handler for the path:

   ```python
   @app.post("/widget/cooling/fan")
   async def fan(payload: dict | None = None):
       v = (payload or {}).get("value")
       desired = bool(v) if v is not None else not state["fan_enabled"]
       state["fan_enabled"] = desired
       # actually flip the fan here…
       return {"ok": True}
   ```

3. Make sure the bound key (`fan_enabled` in the example) appears in
   the next WebSocket snapshot so the widget's UI reflects the new
   state.

That's it — same loop for every interactive control.

---

## Optional: video / camera streaming

If your project has a camera, you can pipe its frames into the widget:

1. Serve an MJPEG endpoint at e.g. `/widget/camera/mjpeg`:
   `multipart/x-mixed-replace; boundary=frame` with each part containing
   a JPEG body. Standard MJPEG.
2. Put a `video_stream` node in the manifest pointing at it.

The Vision Pro app decodes each frame natively (no in-browser shim).
For Pi Camera modules, `picamera2` + Pillow handles this in ~80 lines;
for USB webcams, `ffmpeg` or `v4l2-ctl` works. Any AI can wire it up.

---

## Optional: bearer-token auth

For when you don't want every device on your LAN to be able to talk to
the agent:

1. Generate a random token at startup (or read from env).
2. Set the Bonjour TXT key `auth` to `"required"`.
3. On every HTTP route and the WebSocket upgrade, require an
   `Authorization: Bearer <token>` header. 401 = missing, 403 = wrong.

The visionOS app reads the TXT key, sees `auth=required`, and prompts
the user to paste the token when they add the device. Show the token in
the agent's startup logs so the user can grab it.

---

## Optional extras

- **systemd unit** — for boot persistence, write a small unit file that
  runs `uvicorn` under your user account. The reference implementation
  in the main project has an example.
- **Multiple widgets** — repeat the `WIDGETS` entry + `MANIFESTS` entry
  + add the corresponding snapshot keys. Each widget is independent.
- **Multiple devices on one Pi** — run the agent multiple times under
  different ports with different `SHOP_AGENT_DEVICE_ID` env vars.

---

## What's NOT in scope

These are the rough edges to know about:

- **New component types**. The set in [Component reference](#component-reference)
  is fixed by what the app renders natively. You can't ship a new
  component from the device side; that would require an app update.
- **Cross-device aggregations**. Each agent serves its own device. The
  app composes them visually but doesn't merge their data.
- **Long-term metric storage**. This is a *live* monitor; the app
  doesn't keep history beyond the sparkline window (60 samples).

---

## Asking an AI to write your shop-agent

A few prompt seeds that work well:

> *"Read this URL: https://github.com/gcullie/lmToMyOwnDevices-public.
> My Pi runs a Klipper 3D printer with Moonraker exposed at
> http://localhost:7125. Write a `app.py` that exposes hotend temp, bed
> temp, current job progress, and elapsed time as one widget, plus a
> pause/resume button. Save it to ~/shop-agent/ and a `requirements.txt`
> next to it. Then write the commands to set up the venv and run it."*

> *"From the schema at https://github.com/gcullie/lmToMyOwnDevices-public,
> write a shop-agent that controls a single relay attached to GPIO 17
> via `gpiozero`. One widget with a toggle and a status badge."*

> *"Following https://github.com/gcullie/lmToMyOwnDevices-public, add a
> live-camera widget to the agent I already have on ~/shop-agent. Use
> picamera2 to capture at 640×480 and serve it as MJPEG. Add a
> Camera on/off toggle."*

These give the AI exactly what it needs: the schema URL plus what
hardware/library to read from. The minimal example above is its
template.

---

## Issues, bugs, suggestions

Open an issue on this repo:
<https://github.com/gcullie/lmToMyOwnDevices-public/issues>.

For the app itself, support contact is in the App Store listing.
