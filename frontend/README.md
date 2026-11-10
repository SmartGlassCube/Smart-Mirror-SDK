# Frontend: the mirror's UI

React 19 + TypeScript + Vite. It renders whatever the backend sends over the WebSocket
([docs/protocol.md](../docs/protocol.md)) and has no other link to the backend.

```bash
npm install
npm run dev        # http://localhost:5173, connects to ws://<host>:8080
npm run lint
npm run build      # into dist/ (wipes it first)
```

Point it at another backend port with `VITE_SMARTMIRROR_WS_PORT=8090 npm run dev`.
`python -m smartmirror` (in `backend/`) starts the dev server for you and sets it.

| Path | |
|---|---|
| `src/mirror/` | `MirrorCanvas` (connection + state) → `PageView` → `WidgetSlot`, hand cursor, camera preview |
| `src/widgets/<type>/` | One folder per backend widget `type`; `index.ts` does `export default defineWidget('<type>', Component)` and `registry.ts` picks it up |
| `src/assistant/` | The Abdo avatar (driven by the `ASSISTANT_*` messages) |
| `src/services/useWebSocket.ts` | Auto-reconnecting WebSocket client |
| `src/types/mirror.ts` | Wire format: keep it in sync with the backend |
