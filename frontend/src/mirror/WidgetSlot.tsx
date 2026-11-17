import { Component, type CSSProperties, type ReactNode } from 'react'
import type { MirrorWidget } from '../types/mirror'
import { widgetRegistry } from '../widgets/registry'
import DragHandle from './DragHandle'

type WidgetSlotProps = {
  widget: MirrorWidget
}

// A widget that throws (custom code, or bad data) shows its error instead of blanking the mirror.
class WidgetBoundary extends Component<{ children: ReactNode; type: string }, { error: string | null }> {
  state = { error: null as string | null }
  static getDerivedStateFromError(error: Error) {
    return { error: error.message }
  }
  componentDidCatch(error: Error) {
    console.error(`[widgets] "${this.props.type}" crashed:`, error)
  }
  render() {
    if (this.state.error === null) return this.props.children
    return (
      <div className="widget">
        <h2>{this.props.type}</h2>
        <div>{this.state.error}</div>
      </div>
    )
  }
}

// Places one widget on the mirror; position x/y are 0..1 fractions of the screen.
function WidgetSlot({ widget }: WidgetSlotProps) {
  const Widget = widgetRegistry[widget.type]
  if (!Widget) {
    return null
  }

  // mirror.css places the slot from these and keeps it on screen.
  const style = {
    '--x': widget.position?.x ?? 0.1,
    '--y': widget.position?.y ?? 0.1,
  } as CSSProperties

  return (
    <div className={`widget-slot${widget.dragging ? ' widget-slot--dragging' : ''}`} style={style}>
      {widget.draggable !== false ? <DragHandle lit={Boolean(widget.dragging)} /> : null}
      <WidgetBoundary type={widget.type}>
        <Widget widget={widget} />
      </WidgetBoundary>
    </div>
  )
}

export default WidgetSlot
