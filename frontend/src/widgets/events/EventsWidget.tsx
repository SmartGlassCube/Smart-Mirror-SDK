import type { WidgetProps } from '../defineWidget'

// One club event or project (from the club database later on).
type EventItem = { id: string; name?: string; description?: string; image?: string }
type EventsData = { items?: EventItem[] }

const EventsWidget = ({ widget }: WidgetProps<EventsData>) => {
  const items = widget.data?.items ?? []

  return (
    <div className="widget events-widget">
      <h2>Events</h2>
      {widget.content ? <div>{widget.content}</div> : null}
      {items.length === 0 ? <div>No events yet</div> : null}
      <div className="events-grid">
        {items.map((item) => (
          <div key={item.id} className="event-card">
            <div className="event-card__image">{item.image ? <img src={item.image} alt="" /> : '?'}</div>
            <div className="event-card__name">{item.name ?? item.id}</div>
            {item.description ? <div className="event-card__description">{item.description}</div> : null}
          </div>
        ))}
      </div>
    </div>
  )
}

export default EventsWidget
