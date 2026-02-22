import { useState } from 'react';

const texts = [
  'Welcome to Smart Mirror!',
  'Swipe to see more info.',
  'Stay productive and healthy!',
  'Have a great day!'
];

const TextWidget = () => {
  const [index, setIndex] = useState(0);

  const nextText = () => setIndex((i) => (i + 1) % texts.length);
  const prevText = () => setIndex((i) => (i - 1 + texts.length) % texts.length);

  return (
    <div className="widget text-widget">
      <h2>Text</h2>
      <div style={{ minHeight: 40 }}>{texts[index]}</div>
      <div>
        <button onClick={prevText}>⏪</button>
        <button onClick={nextText}>⏩</button>
      </div>
    </div>
  );
};

export default TextWidget;
