import { useEffect, useState } from 'react'
import type { WidgetProps } from '../defineWidget'

const placeholderHeadlines = [
  'Breaking: Smart Mirror MVP Launched!',
  'Weather is sunny today in Paris.',
  'Calendar now supports gesture navigation.',
  'Stay tuned for more updates!',
]

const NewsWidget = ({ widget }: WidgetProps) => {
  const [index, setIndex] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => {
      setIndex((i) => (i + 1) % placeholderHeadlines.length)
    }, 10000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="widget news-widget">
      <h2>News</h2>
      <div className="widget-message">{widget.content ?? placeholderHeadlines[index]}</div>
    </div>
  )
}

export default NewsWidget
