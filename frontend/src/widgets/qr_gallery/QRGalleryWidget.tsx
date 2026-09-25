import type { WidgetProps } from '../defineWidget'

type QrEntry = { title?: string; imageUrl?: string; url?: string }
type QrGalleryData = { categories?: Record<string, QrEntry[]> }

const QRGalleryWidget = ({ widget }: WidgetProps<QrGalleryData>) => {
  const categories = widget.data?.categories ?? {}
  const categoryNames = Object.keys(categories)

  return (
    <div className="widget qr-gallery-widget">
      <h2>QR Gallery</h2>
      {widget.content ? <div>{widget.content}</div> : null}
      {categoryNames.length === 0 ? <div>No QR data available</div> : null}
      {categoryNames.map((name) => {
        const entries = categories[name] ?? []
        const firstEntry = entries[0]

        return (
          <div key={name} style={{ marginTop: 8 }}>
            <strong>{name}</strong>
            <div>{entries.length} item(s)</div>
            {firstEntry?.title ? <div>First: {firstEntry.title}</div> : null}
            {firstEntry?.imageUrl ? (
              <img
                src={firstEntry.imageUrl}
                alt={firstEntry.title ?? `${name} qr`}
                style={{ width: 100, height: 100, objectFit: 'contain', marginTop: 4 }}
              />
            ) : null}
          </div>
        )
      })}
    </div>
  )
}

export default QRGalleryWidget
