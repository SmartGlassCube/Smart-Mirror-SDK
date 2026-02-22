import { useEffect, useRef, useState, useCallback } from 'react';

const WS_URL = 'ws://localhost:8080'; // Adjust port if needed
const RECONNECT_DELAY = 2000;

export function useWebSocket(onMessage: (msg: any) => void) {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current) wsRef.current.close();
    const ws = new WebSocket(WS_URL);
    ws.onopen = () => setIsConnected(true);
    ws.onclose = () => {
      setIsConnected(false);
      reconnectTimeoutRef.current = setTimeout(connect, RECONNECT_DELAY);
    };
    ws.onerror = () => {};
    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        onMessage(message);
      } catch (e) {
        console.error('[WS] Failed to parse message:', e);
      }
    };
    wsRef.current = ws;
  }, [onMessage]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  return { isConnected };
}
