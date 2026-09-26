import './abdo.css'
import { memo, useEffect, useImperativeHandle, useRef, useState, type Ref, type SyntheticEvent } from 'react'
import awakePng from '../assets/abdo/5 1.png'
import sleepingGif from '../assets/abdo/sleeping-abdo.gif'
import transitionGif from '../assets/abdo/transition-abdo.gif'

// One play of transition-abdo.gif: its frame durations add up to 1.6 s.
const TRANSITION_MS = 1600
// Abdo falls back asleep after this long without being woken again.
const SLEEP_AFTER_MS = 60_000

// Browsers share one animation clock per GIF URL, so replaying the transition from frame 0
// needs a fresh URL each time: a new blob URL over the same downloaded bytes.
let transitionBlob: Blob | null = null
fetch(transitionGif)
  .then((response) => response.blob())
  .then((blob) => {
    transitionBlob = blob
  })
  .catch(() => {})
new Image().src = awakePng

type Mood = 'sleeping' | 'waking' | 'awake'

export type AbdoHandle = {
  // Page change or someone talking to the chatbot: sleeping -> transition -> awake.
  wake: () => void
}

type AbdoProps = {
  ref?: Ref<AbdoHandle>
}

// The chatbot's avatar, fixed at the bottom center of the mirror.
function Abdo({ ref }: AbdoProps) {
  const [mood, setMood] = useState<Mood>('sleeping')
  const [transitionSrc, setTransitionSrc] = useState(transitionGif)
  const [transitionReady, setTransitionReady] = useState(false)
  const moodRef = useRef<Mood>('sleeping')
  const timers = useRef({ sleep: 0, awake: 0 })

  useImperativeHandle(ref, () => {
    const changeMood = (next: Mood) => {
      moodRef.current = next
      setMood(next)
    }
    return {
      wake() {
        window.clearTimeout(timers.current.sleep)
        timers.current.sleep = window.setTimeout(() => changeMood('sleeping'), SLEEP_AFTER_MS)
        if (moodRef.current !== 'sleeping') {
          return
        }
        setTransitionSrc(transitionBlob ? URL.createObjectURL(transitionBlob) : transitionGif)
        setTransitionReady(false)
        changeMood('waking')
      },
    }
  }, [])

  useEffect(() => {
    const pending = timers.current
    return () => {
      window.clearTimeout(pending.sleep)
      window.clearTimeout(pending.awake)
    }
  }, [])

  // Start the transition clock once its GIF is actually on screen, then hold on the awake still.
  const onTransitionLoad = (event: SyntheticEvent<HTMLImageElement>) => {
    const src = event.currentTarget.src
    setTransitionReady(true)
    window.clearTimeout(timers.current.awake)
    timers.current.awake = window.setTimeout(() => {
      if (src.startsWith('blob:')) {
        URL.revokeObjectURL(src)
      }
      if (moodRef.current === 'waking') {
        moodRef.current = 'awake'
        setMood('awake')
      }
    }, TRANSITION_MS)
  }

  const showSleeping = mood === 'sleeping' || (mood === 'waking' && !transitionReady)

  return (
    <div className="abdo" aria-hidden="true">
      {showSleeping ? <img className="abdo__img" src={sleepingGif} alt="" /> : null}
      {mood === 'waking' ? (
        <img
          key={transitionSrc}
          className={`abdo__img${transitionReady ? '' : ' abdo__img--loading'}`}
          src={transitionSrc}
          alt=""
          onLoad={onTransitionLoad}
        />
      ) : null}
      {mood === 'awake' ? <img className="abdo__img" src={awakePng} alt="" /> : null}
    </div>
  )
}

// memo: camera preview frames re-render MirrorCanvas ~10x/s.
export default memo(Abdo)
