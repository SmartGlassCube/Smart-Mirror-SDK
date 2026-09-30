import { useEffect, useImperativeHandle, useRef, type Ref } from 'react'
import type { PointerPosition } from '../types/mirror'

// Share of the remaining distance covered per animation frame; smooths landmark jitter.
const SMOOTHING = 0.35
// Tracking often drops a frame or two; only hide once the hand has really been gone this long.
const HIDE_AFTER_MS = 300

export type HandCursorHandle = {
  move: (position: PointerPosition | null) => void
}

type HandCursorProps = {
  ref?: Ref<HandCursorHandle>
}

// Circle on the index fingertip. Positions are the same 0..1 screen fractions the backend
// uses to pick widgets. Updated straight on the DOM: POINTER arrives ~30x/s.
function HandCursor({ ref }: HandCursorProps) {
  const element = useRef<HTMLDivElement>(null)
  const motion = useRef({
    target: null as PointerPosition | null,
    current: null as PointerPosition | null,
    frame: 0,
    hideTimer: 0,
  })

  useImperativeHandle(ref, () => {
    const state = motion.current

    const draw = () => {
      state.frame = 0
      const el = element.current
      const { target, current } = state
      if (!el || !target || !current) {
        return
      }
      const dx = target.x - current.x
      const dy = target.y - current.y
      const settled = Math.abs(dx) < 0.0005 && Math.abs(dy) < 0.0005
      state.current = settled ? target : { x: current.x + dx * SMOOTHING, y: current.y + dy * SMOOTHING }
      el.style.left = `${state.current.x * 100}%`
      el.style.top = `${state.current.y * 100}%`
      if (!settled) {
        state.frame = requestAnimationFrame(draw)
      }
    }

    return {
      move(position) {
        const el = element.current
        if (!el) {
          return
        }
        if (position === null) {
          if (!state.hideTimer) {
            state.hideTimer = window.setTimeout(() => {
              state.hideTimer = 0
              state.target = null
              state.current = null
              el.classList.remove('hand-cursor--visible')
            }, HIDE_AFTER_MS)
          }
          return
        }
        window.clearTimeout(state.hideTimer)
        state.hideTimer = 0
        state.target = position
        state.current ??= position // reappear at the hand instead of gliding from the old spot
        el.classList.add('hand-cursor--visible')
        if (!state.frame) {
          state.frame = requestAnimationFrame(draw)
        }
      },
    }
  }, [])

  useEffect(() => {
    const state = motion.current
    return () => {
      cancelAnimationFrame(state.frame)
      window.clearTimeout(state.hideTimer)
    }
  }, [])

  return <div ref={element} className="hand-cursor" aria-hidden="true" />
}

export default HandCursor
