// Wire format sent by the Python backend (smartmirror/server/websocket.py).

export type Position = {
  x?: number
  y?: number
}

// One widget as serialized by BaseWidget.serialize() in Python.
export type MirrorWidget<TData = unknown, TMetadata = Record<string, unknown>> = {
  id: string
  type: string
  position?: Position
  content?: string | null
  data?: TData | null
  metadata?: TMetadata
  draggable?: boolean
  dragging?: boolean
}

// StateManager.get_state_snapshot(): the active page and the ids of all pages.
export type MirrorState = {
  nodeId: string | null
  nodeIds: string[]
  widgets: MirrorWidget[]
}

export type GestureEventInfo = {
  name: string
  hand: string | null
}

// Small annotated webcam preview (JPEG data URL) plus the latest gestures.
export type CameraFrame = {
  image: string
  events: GestureEventInfo[]
}

export type BackendMessage =
  | { type: 'INIT' | 'STATE_UPDATE'; state: MirrorState }
  | ({ type: 'CAMERA_FRAME' } & CameraFrame)
  // Someone talked to the chatbot: wakes Abdo (see assistant/Abdo.tsx).
  | { type: 'ASSISTANT_WAKE' }
