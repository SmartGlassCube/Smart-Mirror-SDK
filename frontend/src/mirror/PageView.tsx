import type { MirrorWidget } from '../types/mirror'
import WidgetSlot from './WidgetSlot'

type PageViewProps = {
  widgets: MirrorWidget[]
}

// The active page (backend graph node): every widget placed at its position.
function PageView({ widgets }: PageViewProps) {
  return (
    <div className="mirror-page">
      {widgets.map((widget) => (
        <WidgetSlot key={widget.id} widget={widget} />
      ))}
    </div>
  )
}

export default PageView
