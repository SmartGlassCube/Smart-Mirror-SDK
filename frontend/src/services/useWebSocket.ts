import { useEffect, useState } from 'react'
import type { BackendMessage } from '../types/mirror'

// VITE_SMARTMIRROR_WS_PORT is set when the backend app starts this dev server (backend/smartmirror/app/frontend_dev.py).
const WS_PORT = import.meta.env.VITE_SMARTMIRROR_WS_PORT ?? '8080'
const WS_URL = `ws://${window.location.hostname || 'localhost'}:${WS_PORT}`
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
