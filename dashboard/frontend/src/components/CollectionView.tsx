import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from '../api'
import type { CollectionConfig } from '../collections'
import type { BaseItem } from '../types'
import { ItemForm } from './ItemForm'

interface Props {
  config: CollectionConfig
}

type Editing = BaseItem | 'new' | null

export function CollectionView({ config }: Props) {
  const [items, setItems] = useState<BaseItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])
  const [editing, setEditing] = useState<Editing>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.get<BaseItem[]>(`/api/${config.name}`)
      setItems(data)
      setError(null)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load')
    } finally {
      setLoading(false)
    }
  }, [config.name])

  useEffect(() => {
    setEditing(null)
    setWarnings([])
    void load()
  }, [load])

  async function handleCreate(payload: Record<string, unknown>) {
    const result = await api.post<BaseItem & { warnings: string[] }>(`/api/${config.name}`, payload)
    setEditing(null)
    setWarnings(result.warnings ?? [])
    await load()
  }

  async function handleUpdate(id: string, payload: Record<string, unknown>) {
    const result = await api.put<BaseItem & { warnings: string[] }>(`/api/${config.name}/${id}`, payload)
    setEditing(null)
    setWarnings(result.warnings ?? [])
    await load()
  }

  async function handleDelete(item: BaseItem) {
    const label = String(item[config.titleField])
    if (!window.confirm(`Delete "${label}"? This cannot be undone.`)) return
    await api.delete(`/api/${config.name}/${item.id}`)
    await load()
  }

  async function handleTogglePublish(item: BaseItem) {
    const action = item.status === 'published' ? 'unpublish' : 'publish'
    await api.patch(`/api/${config.name}/${item.id}/${action}`)
    await load()
  }

  if (editing !== null) {
    const initial = editing === 'new' ? null : editing
    return (
      <ItemForm
        config={config}
        initial={initial}
        onCancel={() => setEditing(null)}
        onSubmit={(payload) =>
          editing === 'new' ? handleCreate(payload) : handleUpdate((editing as BaseItem).id, payload)
        }
      />
    )
  }

  return (
    <section>
      <header className="section-header">
        <h2>{config.label}</h2>
        <button onClick={() => setEditing('new')}>New</button>
      </header>
      {warnings.length > 0 && (
        <div className="warnings">
          {warnings.map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
        </div>
      )}
      {loading && <p>Loading...</p>}
      {error && <p className="error">{error}</p>}
      <ul className="item-list">
        {items.map((item) => (
          <li key={item.id}>
            <span className={`badge badge-${item.status}`}>{item.status}</span>
            <span className="item-title">{String(item[config.titleField])}</span>
            <span className="item-actions">
              <button onClick={() => setEditing(item)}>Edit</button>
              <button onClick={() => void handleTogglePublish(item)}>
                {item.status === 'published' ? 'Unpublish' : 'Publish'}
              </button>
              <button className="danger" onClick={() => void handleDelete(item)}>
                Delete
              </button>
            </span>
          </li>
        ))}
        {!loading && items.length === 0 && <li className="empty">No items yet.</li>}
      </ul>
    </section>
  )
}
