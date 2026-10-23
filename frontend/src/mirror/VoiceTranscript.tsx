import '../ui/speech-bubble.css'
import { useEffect } from 'react'
import { FRAME_IMAGE } from '../ui/pixelFrame'

// Hides again this long after the last thing the chatbot heard.
const HIDE_AFTER_MS = 15_000

type VoiceTranscriptProps = {
  // '' when only the wake word was heard: Abdo is waiting for the question.
  text: string
  onExpire: () => void
}

// What the chatbot just heard, next to the camera preview, in the same 8-bit frame as Abdo's speech bubble.
// Give it a new `key` per transcript so its hide timer restarts.
function VoiceTranscript({ text, onExpire }: VoiceTranscriptProps) {
  useEffect(() => {
    const timer = window.setTimeout(onExpire, HIDE_AFTER_MS)
    return () => window.clearTimeout(timer)
  }, [onExpire])

  return (
    <div className="speech-bubble voice-transcript" style={{ borderImageSource: FRAME_IMAGE }} aria-live="polite">
      <div className="voice-transcript__label">Heard</div>
      <p className={`voice-transcript__text${text ? '' : ' voice-transcript__text--waiting'}`}>
        {text || 'Listening...'}
      </p>
    </div>
  )
}

export default VoiceTranscript
