type TextWidgetProps = {
  widget?: {
    content?: string;
  };
};

const TextWidget = ({ widget }: TextWidgetProps) => {
  const content = widget?.content ?? 'Welcome to Smart Mirror!';

  return (
    <div className="widget text-widget">
      <h2>Text</h2>
      <div style={{ minHeight: 40 }}>{content}</div>
    </div>
  );
};

export default TextWidget;
