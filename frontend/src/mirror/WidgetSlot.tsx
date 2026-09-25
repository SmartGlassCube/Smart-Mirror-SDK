import type { MirrorWidget } from '../types/mirror'
import { widgetRegistry } from '../widgets/registry'

type WidgetSlotProps = {
  widget: MirrorWidget
}

// Places one widget on the mirror; position x/y are 0..1 fractions of the screen.
function WidgetSlot({ widget }: WidgetSlotProps) {
  const Widget = widgetRegistry[widget.type]
  if (!Widget) {
    return null
  }

  const style = {
    left: `${(widget.position?.x ?? 0.1) * 100}%`,
    top: `${(widget.position?.y ?? 0.1) * 100}%`,
  }

  return (
    <div className={`widget-slot${widget.dragging ? ' widget-slot--dragging' : ''}`} style={style}>
      <Widget widget={widget} />
    </div>
  )
}

export default WidgetSlot
