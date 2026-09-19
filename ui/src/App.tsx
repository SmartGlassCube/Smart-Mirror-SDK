import './App.css'
import { useCallback, useState } from 'react'
import CalendarWidget from './components/CalendarWidget'
import WeatherWidget from './components/WeatherWidget'
import NewsWidget from './components/NewsWidget'
import TextWidget from './components/TextWidget'
import QrGalleryWidget from './components/QrGalleryWidget'
import { useWebSocket } from './hooks/useWebSocket'

type Position = {
  x?: number
  y?: number
}

type MirrorWidget = {
  type: 'calendar' | 'weather' | 'news' | 'text' | 'qr_gallery'
  position?: Position
  content?: string
  data?: Record<string, unknown>
  metadata?: Record<string, unknown>
  dragging?: boolean
}

type MirrorState = {
  nodeId: string | null
  widgets: MirrorWidget[]
  nodes?: Array<{
    id: string | null
    widgets: MirrorWidget[]
  }>
}

type BackendMessage = {
  type: string
  state?: MirrorState
}

function App() {
  const [state, setState] = useState<MirrorState>({ nodeId: null, widgets: [], nodes: [] })

  const onMessage = useCallback((message: BackendMessage) => {
    if ((message.type === 'INIT' || message.type === 'STATE_UPDATE') && message.state) {
      setState(message.state)
    }
  }, [])

  const { isConnected } = useWebSocket(onMessage)

  const renderWidget = (widget: MirrorWidget, index: number) => {
    const position = widget.position ?? {}
    const x = (position.x ?? 0.1) * 100
    const y = (position.y ?? 0.1) * 100
    const style = {
      left: `${x}%`,
      top: `${y}%`,
    }

    let component = null

    if (widget.type === 'calendar') {
      component = <CalendarWidget widget={widget} />
    } else if (widget.type === 'weather') {
      component = <WeatherWidget widget={widget} />
    } else if (widget.type === 'news') {
      component = <NewsWidget widget={widget} />
    } else if (widget.type === 'text') {
      component = <TextWidget widget={widget} />
    } else if (widget.type === 'qr_gallery') {
      component = <QrGalleryWidget widget={widget} />
    }

    if (!component) {
      return null
    }

    const draggingClass = widget.dragging ? 'widget-slot--dragging' : ''

    return (
      <div key={`${widget.type}-${index}`} className={`widget-slot ${draggingClass}`} style={style}>
        {component}
      </div>
    )
  }

  const nodes = state.nodes ?? []
  const pages = nodes.length > 0
    ? nodes
    : [{ id: state.nodeId, widgets: state.widgets }]
  const activePageIndex = pages.findIndex((page) => page.id === state.nodeId)

  return (
    <div className="mirror-canvas">
      <div className="mirror-status">
        {isConnected ? 'Connected to backend' : 'Connecting to backend...'}
        {state.nodeId ? ` | Node: ${state.nodeId}` : ''}
        {pages.length > 0 ? ` | Page: ${(activePageIndex >= 0 ? activePageIndex : 0) + 1}/${pages.length}` : ''}
      </div>
      {pages.map((page, pageIndex) => {
        const pageId = page.id ?? `page-${pageIndex}`
        const isActive = page.id === state.nodeId || (!state.nodeId && pageIndex === 0)

        return (
          <div
            key={pageId}
            className={`mirror-page ${isActive ? 'mirror-page--active' : 'mirror-page--inactive'}`}
          >
            {isActive ? page.widgets.map(renderWidget) : null}
          </div>
        )
      })}
    </div>
  )
}

export default App
