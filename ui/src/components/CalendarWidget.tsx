const getToday = () => {
  const today = new Date();
  return { day: today.getDate(), month: today.getMonth(), year: today.getFullYear() };
};

type CalendarWidgetProps = {
  widget?: {
    content?: string;
    data?: {
      events?: Array<{ title?: string; start?: string; location?: string }>;
    };
  };
};

const CalendarWidget = ({ widget }: CalendarWidgetProps) => {
  const today = getToday();
  const daysInMonth = new Date(today.year, today.month + 1, 0).getDate();
  const days = Array.from({ length: daysInMonth }, (_, i) => i + 1);
  const events = widget?.data?.events ?? [];
  return (
    <div className="widget calendar-widget">
      <h2>Calendar</h2>
      {widget?.content ? <div>{widget.content}</div> : null}
      <div>{today.year} - {today.month + 1}</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', width: 210 }}>
        {days.map(day => (
          <div
            key={day}
            style={{
              width: 30,
              height: 30,
              margin: 2,
              background: day === today.day ? '#4caf50' : '#eee',
              color: day === today.day ? '#fff' : '#333',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 4,
            }}
          >
            {day}
          </div>
        ))}
      </div>
      {events.length > 0 ? (
        <div style={{ marginTop: 8, textAlign: 'left' }}>
          {events.slice(0, 3).map((event, index) => (
            <div key={`${event.title ?? 'event'}-${index}`}>
              • {event.title ?? 'Untitled'}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
};

export default CalendarWidget;
