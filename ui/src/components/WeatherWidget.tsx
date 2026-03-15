type WeatherWidgetProps = {
  widget?: {
    content?: string;
  };
};

const WeatherWidget = ({ widget }: WeatherWidgetProps) => (
  <div className="widget weather-widget">
    <h2>Weather</h2>
    {widget?.content ? <div>{widget.content}</div> : <div>🌤️ 22°C, Partly Cloudy</div>}
    <div>Location: Paris</div>
    <div>Humidity: 60%</div>
    <div>Wind: 10 km/h</div>
  </div>
);

export default WeatherWidget;
