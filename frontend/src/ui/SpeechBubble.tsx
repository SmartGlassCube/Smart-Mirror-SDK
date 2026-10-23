import './speech-bubble.css'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { FRAME_IMAGE, pixelImage } from './pixelFrame'

// Typewriter speed: one character every CHAR_MS.
const CHAR_MS = 35

// Tail pointing up at Abdo. Its last two rows lie on the frame's top edge and open it up.
const TAIL = [
  '....S....',
  '...SKS...',
  '..SKWKS..',
  '.SKWWWKS.',
  'SKWWWWWKS',
  'KKWWWWWKK',
]

const TAIL_IMAGE = pixelImage(TAIL)

type SpeechBubbleProps = {
  text: string
  className?: string
  // Calls `onClose` this long after the text has finished typing; stays open when omitted.
  holdMs?: number
  onClose?: () => void
}

// 8-bit speech bubble that types `text` out letter by letter, then blinks a "next" arrow.
// Give it a new `key` per message so the typing restarts.
function SpeechBubble({ text, className, holdMs, onClose }: SpeechBubbleProps) {
  const [shown, setShown] = useState(0)
  const done = shown >= text.length
  const textBox = useRef<HTMLDivElement>(null)
  const caret = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (done) {
      return
    }
    const timer = window.setTimeout(() => setShown((count) => count + 1), CHAR_MS)
    return () => window.clearTimeout(timer)
  }, [done, shown])

  useEffect(() => {
    if (!done || holdMs === undefined || !onClose) {
      return
    }
    const timer = window.setTimeout(onClose, holdMs)
    return () => window.clearTimeout(timer)
  }, [done, holdMs, onClose])

  // Long text: keep the line being typed in view, older lines scroll off the top.
  useLayoutEffect(() => {
    const box = textBox.current
    const line = caret.current
    if (box && line) {
      box.scrollTop = Math.max(0, line.offsetTop + line.offsetHeight - box.clientHeight)
    }
  }, [shown])

  return (
    <div className={`speech-bubble${className ? ` ${className}` : ''}`} style={{ borderImageSource: FRAME_IMAGE }}>
      <div className="speech-bubble__tail" style={{ backgroundImage: TAIL_IMAGE }} />
      {/* The untyped rest is laid out invisibly, so the bubble has its final size from the start. */}
      <div ref={textBox} className="speech-bubble__text">
        <p>
          {text.slice(0, shown)}
          {/* Word joiner: zero-width and no line break, so it marks the typing position without moving text. */}
          <span ref={caret}>{'⁠'}</span>
          <span className="speech-bubble__pending">{text.slice(shown)}</span>
        </p>
      </div>
      {done ? <div className="speech-bubble__next" /> : null}
    </div>
  )
}

export default SpeechBubble
