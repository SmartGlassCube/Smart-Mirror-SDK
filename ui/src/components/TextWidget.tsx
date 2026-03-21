type TextWidgetProps = {
  widget?: {
    content?: string;
    metadata?: {
      contentMode?: string;
      key?: string;
      itemIndex?: number;
      activeItemCount?: number;
    };
  };
};

const TextWidget = ({ widget }: TextWidgetProps) => {
  const content = widget?.content ?? 'Welcome to Smart Mirror!';
  const metadata = widget?.metadata;
  const hasIndex = typeof metadata?.itemIndex === 'number' && typeof metadata?.activeItemCount === 'number';
  const itemIndex = hasIndex ? (metadata?.itemIndex ?? 0) + 1 : null;
  const itemCount = hasIndex ? metadata?.activeItemCount : null;

  return (
    <div className="widget text-widget">
      <h2>Text</h2>
      {metadata?.contentMode === 'dict' && metadata?.key ? <div>Section: {metadata.key}</div> : null}
      {hasIndex ? <div>Item: {itemIndex}/{itemCount}</div> : null}
      <div style={{ minHeight: 40 }}>{content}</div>
    </div>
  );
};

export default TextWidget;
