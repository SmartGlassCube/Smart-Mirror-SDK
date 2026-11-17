import { useEffect, useState } from 'react'
import type { BackendMessage } from '../types/mirror'

// Where the backend is, first match wins:
// 1. `?ws=ws://<host>:<port>` in the page URL (a kiosk browser pointed at another machine);
// 2. VITE_SMARTMIRROR_WS_PORT, set when the backend app starts this dev server (backend/smartmirror/app/frontend_dev.py);
// 3. a production build is served by the backend itself (smartmirror/server/static_ui.py): the page's own host and port;
// 4. port 8080 on the page's host.
function backendUrl(): string {
  const override = new URLSearchParams(window.location.search).get('ws')
  if (override) return override
  const host = window.location.hostname || 'localhost'
  const devPort = import.meta.env.VITE_SMARTMIRROR_WS_PORT
  if (devPort) return `ws://${host}:${devPort}`
  if (import.meta.env.PROD && window.location.port) {
    return `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`
  }
  return `ws://${host}:8080`
}

const WS_URL = backendUrl()
const RECONNECT_DELAY_MS = 2000

// Auto-reconnecting connection to the backend. `onMessage` should be stable (useCallback).
export function useWebSocket(onMessage: (message: BackendMessage) => void) {
  const [isConnected, setIsConnected] = useState(false)

  useEffect(() => {
    let socket: WebSocket | null = null
    let reconnectTimer: number | undefined
    let disposed = false

    const connect = () => {
      socket = new WebSocket(WS_URL)
      socket.onopen = () => setIsConnected(true)
      socket.onclose = () => {
        setIsConnected(false)
        if (!disposed) {
          reconnectTimer = window.setTimeout(connect, RECONNECT_DELAY_MS)
        }
      }
      socket.onmessage = (event) => {
        let message: BackendMessage
        try {
          message = JSON.parse(event.data)
        } catch (error) {
          console.error('[WS] Failed to parse message:', error)
          return
        }
        onMessage(message)
      }
    }

    connect()
    return () => {
      disposed = true
      window.clearTimeout(reconnectTimer)
      socket?.close()
    }
  }, [onMessage])

  return { isConnected }
}
