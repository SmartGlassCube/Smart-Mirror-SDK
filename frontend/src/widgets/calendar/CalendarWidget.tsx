import type { WidgetProps } from '../defineWidget'

type CalendarEvent = { title?: string; start?: string; location?: string }
type CalendarData = { events?: CalendarEvent[] }

const CalendarWidget = ({ widget }: WidgetProps<CalendarData>) => {
  const today = new Date()
  const year = today.getFullYear()
  const month = today.getMonth()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const days = Array.from({ length: daysInMonth }, (_, i) => i + 1)
  const events = widget.data?.events ?? []

  return (
    <div className="widget calendar-widget">
      <h2>Calendar</h2>
      {widget.content ? <div>{widget.content}</div> : null}
      <div>{year} - {month + 1}</div>
      <div className="calendar-grid">
        {days.map(day => (
          <div key={day} className={`calendar-day${day === today.getDate() ? ' calendar-day--today' : ''}`}>
            {day}
          </div>
        ))}
      </div>
      {events.length > 0 ? (
        <div className="calendar-events">
          {events.slice(0, 3).map((event, index) => (
            <div key={`${event.title ?? 'event'}-${index}`}>
              • {event.title ?? 'Untitled'}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

export default CalendarWidget
