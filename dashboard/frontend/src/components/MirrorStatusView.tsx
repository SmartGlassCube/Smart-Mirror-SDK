import { useEffect, useState } from 'react'
import { api, ApiError } from '../api'
import type { MirrorStatus } from '../types'

const REFRESH_INTERVAL_MS = 10_000

export function MirrorStatusView() {
  const [statuses, setStatuses] = useState<MirrorStatus[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const data = await api.get<MirrorStatus[]>('/api/mirror/status')
        if (!cancelled) {
          setStatuses(data)
          setError(null)
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : 'Failed to load')
      }
    }

    void load()
    const interval = setInterval(load, REFRESH_INTERVAL_MS)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  return (
    <section>
      <h2>Mirror status</h2>
      {error && <p className="error">{error}</p>}
      {statuses.length === 0 && !error && <p>No mirror has reported in yet.</p>}
      <ul className="mirror-list">
        {statuses.map((mirror) => (
          <li key={mirror.mirror_id} className={mirror.online ? 'online' : 'offline'}>
            <h3>
              {mirror.mirror_id} -- {mirror.online ? 'Online' : 'Offline'}
            </h3>
            <p>Last seen: {new Date(mirror.last_seen).toLocaleString()}</p>
            <p>Current page: {mirror.current_page ?? '--'}</p>
            <p>Last sync: {mirror.last_sync_at ? new Date(mirror.last_sync_at).toLocaleString() : 'never'}</p>
            {mirror.last_error && <p className="error">Last error: {mirror.last_error}</p>}
          </li>
        ))}
      </ul>
    </section>
  )
}
