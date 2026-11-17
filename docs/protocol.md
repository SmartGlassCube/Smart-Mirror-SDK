# Backend ↔ frontend protocol

The backend (`backend/`) and the frontend (`frontend/`) share no code. This page is
the whole contract between them. When you change a message, update both sides:

- backend: `glasscube/server/websocket.py` (`ClientHub`) and the senders listed below
- frontend: `src/types/mirror.ts` (`BackendMessage`) and `src/services/useWebSocket.ts`

## Connection

- The frontend connects to `ws://<page host>:<VITE_GLASSCUBE_WS_PORT>` (default `8080`)
  and reconnects every 2 s.
- `VITE_GLASSCUBE_WS_PORT` is set when `python -m glasscube` starts the Vite dev
  server, from `GLASSCUBE_WS_PORT`. Start the frontend by hand on another port with
  `VITE_GLASSCUBE_WS_PORT=8090 npm run dev`.
- A production build served by the backend itself (a pip install, see
  `glasscube/server/static_ui.py`) connects to the page's own host and port instead.
  `?ws=ws://<host>:<port>` in the page URL overrides all of this.
- Server → client only. Client messages are logged and ignored.

## Server → client messages

All messages are JSON objects with a `type`.

| `type` | Payload | Sent by | When |
|---|---|---|---|
| `WIDGET_TYPES` | `widgetTypes`: `[{type, name, code}]` | `ClientHub.handle_client` | Once, on connect before `INIT`, when the server has custom widgets (a Smart Mirror Studio project's). `code` is a CommonJS module whose default export is the React component; it may import only `react`. The frontend registers them (`widgets/customWidgets.ts`) |
| `INIT` | `state` | `ClientHub.handle_client` | Once, on connect |
| `STATE_UPDATE` | `state` | `ClientHub.broadcast_state` | The page or a widget changed (gesture, or new provider data) |
| `CAMERA_FRAME` | `image`, `events` | `server/camera_preview.py` | At most 10×/s while a client is connected |
| `POINTER` | `position`, `pinching` | `server/hand_pointer.py` | The pointing hand moved, or started/stopped pinching |
| `ASSISTANT_HEARD` | `text` | `SmartMirrorServer.assistant_heard` | The voice assistant heard a question (`""` = only the wake word) |
| `ASSISTANT_WAKE` | none | `SmartMirrorServer.assistant_wake` | Right after `ASSISTANT_HEARD`; wakes the Abdo avatar |
| `ASSISTANT_SAY` | `text` | `SmartMirrorServer.assistant_say` | The assistant's reply, typed into Abdo's speech bubble |

### `state` (`StateManager.get_state_snapshot()`)

```json
{
  "nodeId": "home",
  "nodeIds": ["home", "games", "events", "draw"],
  "widgets": [
    {
      "id": "text-4",
      "type": "text",
      "position": {"x": 0.5, "y": 0.5},
      "content": "...",
      "data": null,
      "metadata": {},
      "draggable": true,
      "dragging": false
    }
  ]
}
```

Only the active page's widgets are sent. A widget's `type` picks the React component
(`frontend/src/widgets/<type>/index.ts`). `position` is a 0–1 fraction of the screen.

### `CAMERA_FRAME`

```json
{"type": "CAMERA_FRAME", "image": "data:image/jpeg;base64,...", "events": [{"name": "pinch_start", "hand": "right"}]}
```

`image` is about 240 px wide, annotated. `events` holds the gestures of the last 1.5 s, with repeats collapsed.

### `POINTER`

```json
{"type": "POINTER", "position": {"x": 0.42, "y": 0.31}, "pinching": false}
```

`position` uses the same 0–1 screen fractions as widget positions, and is `null` once the hand is lost.
It is the index fingertip, or while `pinching`, the point between the thumb and index tips: the
drawing widget's pen (`frontend/src/widgets/drawing/`), which draws while `pinching` is true.

## HTTP: the bundled UI and event images

When the package carries a prebuilt UI (`glasscube/ui/`, built by
`backend/scripts/build_frontend.py`), every plain HTTP `GET` on the WebSocket port that
isn't a WebSocket handshake is served from it: `/` is `index.html`.


The WebSocket port also answers `GET /content-images/<file>` with an event image that
content sync downloaded from the dashboard (404 for anything else). Event cards
reference these URLs in their `data`, so the frontend only uses them as `<img src>`.
