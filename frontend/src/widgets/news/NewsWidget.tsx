import { useEffect, useState } from 'react'
import type { WidgetProps } from '../defineWidget'

const placeholderHeadlines = [
  'Breaking: Smart Mirror MVP Launched!',
  'Weather is sunny today in Paris.',
  'Calendar now supports gesture navigation.',
  'Stay tuned for more updates!',
]

// One news item: an active announcement or an achievement (see content sync's news()).
type NewsItem = {
  kind?: 'announcement' | 'achievement'
  title?: string
  priority?: string | null
  // null = the whole Student Branch
  chapter_name?: string | null
}
type NewsData = { items?: NewsItem[] }

const ROTATE_MS = 10000

const NewsWidget = ({ widget }: WidgetProps<NewsData>) => {
  const [index, setIndex] = useState(0)
  const items = widget.data?.items ?? []
  const count = items.length || placeholderHeadlines.length

  useEffect(() => {
    const interval = setInterval(() => {
      setIndex((i) => (i + 1) % count)
    }, ROTATE_MS)
    return () => clearInterval(interval)
  }, [count])

  const item = items.length > 0 ? items[index % items.length] : null

  return (
    <div className="widget news-widget">
      <h2>News</h2>
      {item ? (
        <div className="widget-message">
          <div className="news-widget__label">
            {item.kind === 'achievement' ? 'Achievement' : item.priority === 'high' ? 'Important' : 'Announcement'}
            {` · ${item.chapter_name ?? 'IEEE INSAT SB'}`}
          </div>
          {item.title ?? 'Untitled'}
        </div>
      ) : (
        <div className="widget-message">{widget.content ?? placeholderHeadlines[index % placeholderHeadlines.length]}</div>
      )}
    </div>
  )
}

export default NewsWidget
