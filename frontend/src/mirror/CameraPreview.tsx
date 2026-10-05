import type { CameraFrame } from '../types/mirror'

type CameraPreviewProps = {
  frame: CameraFrame
}

// Little webcam view in the top-right corner: hands drawn by the backend, latest gestures below.
function CameraPreview({ frame }: CameraPreviewProps) {
  return (
    <div className="camera-preview">
      <img className="camera-preview__image" src={frame.image} alt="Camera" />
      {frame.events.map((event, index) => (
        <div key={`${event.name}-${index}`} className="camera-preview__event">
          {event.name.replaceAll('_', ' ')}
          {event.hand ? ` · ${event.hand}` : ''}
        </div>
      ))}
    </div>
  )
}

export default CameraPreview
