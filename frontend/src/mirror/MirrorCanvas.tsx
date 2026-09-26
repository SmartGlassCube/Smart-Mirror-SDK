import './mirror.css'
import { useCallback, useRef, useState } from 'react'
import Abdo, { type AbdoHandle } from '../assistant/Abdo'
import { useWebSocket } from '../services/useWebSocket'
import type { BackendMessage, CameraFrame, MirrorState } from '../types/mirror'
import CameraPreview from './CameraPreview'
import HandCursor, { type HandCursorHandle } from './HandCursor'
import PageView from './PageView'

function MirrorCanvas() {
  const [state, setState] = useState<MirrorState>({ nodeId: null, nodeIds: [], widgets: [] })
  const [cameraFrame, setCameraFrame] = useState<CameraFrame | null>(null)
  const abdoRef = useRef<AbdoHandle>(null)
  const nodeIdRef = useRef<string | null>(null)
  const cursorRef = useRef<HandCursorHandle>(null)

  const onMessage = useCallback((message: BackendMessage) => {
    if (message.type === 'CAMERA_FRAME') {
      setCameraFrame(message)
    } else if (message.type === 'POINTER') {
      cursorRef.current?.move(message.position)
    } else if (message.type === 'ASSISTANT_WAKE') {
      abdoRef.current?.wake()
    } else {
      // A page change wakes Abdo; the first page after startup doesn't.
      const previousNodeId = nodeIdRef.current
      nodeIdRef.current = message.state.nodeId
      if (previousNodeId !== null && previousNodeId !== message.state.nodeId) {
        abdoRef.current?.wake()
      }
      setState(message.state)
    }
  }, [])
  const { isConnected } = useWebSocket(onMessage)

  const pageIndex = state.nodeId === null ? -1 : state.nodeIds.indexOf(state.nodeId)

  return (
    <div className="mirror-canvas">
      <div className="mirror-status">
        {isConnected ? 'Connected to backend' : 'Connecting to backend...'}
        {state.nodeId ? ` | Page: ${state.nodeId}` : ''}
        {pageIndex >= 0 ? ` (${pageIndex + 1}/${state.nodeIds.length})` : ''}
      </div>
      {isConnected && cameraFrame ? <CameraPreview frame={cameraFrame} /> : null}
      <PageView key={state.nodeId ?? 'none'} widgets={state.widgets} />
      <Abdo ref={abdoRef} />
      {isConnected ? <HandCursor ref={cursorRef} /> : null}
    </div>
  )
}

export default MirrorCanvas
