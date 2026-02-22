const getToday = () => {
  const today = new Date();
  return { day: today.getDate(), month: today.getMonth(), year: today.getFullYear() };
};

const CalendarWidget = () => {
  const today = getToday();
  const daysInMonth = new Date(today.year, today.month + 1, 0).getDate();
  const days = Array.from({ length: daysInMonth }, (_, i) => i + 1);
  return (
    <div className="widget calendar-widget">
      <h2>Calendar</h2>
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
    </div>
  );
};

export default CalendarWidget;
