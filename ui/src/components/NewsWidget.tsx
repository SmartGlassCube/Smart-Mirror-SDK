import { useEffect, useState } from 'react';

const newsList = [
  'Breaking: Smart Mirror MVP Launched!',
  'Weather is sunny today in Paris.',
  'Calendar now supports gesture navigation.',
  'Stay tuned for more updates!'
];

type NewsWidgetProps = {
  widget?: {
    content?: string;
  };
};

const NewsWidget = ({ widget }: NewsWidgetProps) => {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setIndex((i) => (i + 1) % newsList.length);
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="widget news-widget">
      <h2>News</h2>
      <div style={{ minHeight: 40 }}>{widget?.content ?? newsList[index]}</div>
    </div>
  );
};

export default NewsWidget;
