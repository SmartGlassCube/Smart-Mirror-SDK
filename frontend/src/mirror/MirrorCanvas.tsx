import './mirror.css'
import { useCallback, useState } from 'react'
import { useWebSocket } from '../services/useWebSocket'
import type { BackendMessage, MirrorState } from '../types/mirror'
import PageView from './PageView'

function MirrorCanvas() {
  const [state, setState] = useState<MirrorState>({ nodeId: null, nodeIds: [], widgets: [] })
  const onMessage = useCallback((message: BackendMessage) => setState(message.state), [])
  const { isConnected } = useWebSocket(onMessage)

  const pageIndex = state.nodeId === null ? -1 : state.nodeIds.indexOf(state.nodeId)

  return (
    <div className="mirror-canvas">
      <div className="mirror-status">
        {isConnected ? 'Connected to backend' : 'Connecting to backend...'}
        {state.nodeId ? ` | Page: ${state.nodeId}` : ''}
        {pageIndex >= 0 ? ` (${pageIndex + 1}/${state.nodeIds.length})` : ''}
      </div>
      <PageView key={state.nodeId ?? 'none'} widgets={state.widgets} />
    </div>
  )
}

export default MirrorCanvas
