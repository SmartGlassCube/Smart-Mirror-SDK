import './App.css'
import { useCallback, useState } from 'react'
import CalendarWidget from './components/CalendarWidget'
import WeatherWidget from './components/WeatherWidget'
import NewsWidget from './components/NewsWidget'
import TextWidget from './components/TextWidget'
import { useWebSocket } from './hooks/useWebSocket'

type Position = {
  x?: number
  y?: number
}

type MirrorWidget = {
  type: 'calendar' | 'weather' | 'news' | 'text'
  position?: Position
  content?: string
}

type MirrorState = {
  nodeId: string | null
  widgets: MirrorWidget[]
}

type BackendMessage = {
  type: string
  state?: MirrorState
}

function App() {
  const [state, setState] = useState<MirrorState>({ nodeId: null, widgets: [] })

  const onMessage = useCallback((message: BackendMessage) => {
    if (message.type === 'INIT' && message.state) {
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
    }

    if (!component) {
      return null
    }

    return (
      <div key={`${widget.type}-${index}`} className="widget-slot" style={style}>
        {component}
      </div>
    )
  }

  return (
    <div className="mirror-canvas">
      <div className="mirror-status">
        {isConnected ? 'Connected to backend' : 'Connecting to backend...'}
        {state.nodeId ? ` | Node: ${state.nodeId}` : ''}
      </div>
      {state.widgets.map(renderWidget)}
    </div>
  )
}

export default App
