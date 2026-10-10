import { COLLECTIONS } from '../collections'
import type { CollectionName } from '../types'
import { useAuth } from '../useAuth'

export type Section = CollectionName | 'mirror'

interface Props {
  active: Section
  onSelect: (section: Section) => void
}

export function Sidebar({ active, onSelect }: Props) {
  const { user, logout } = useAuth()

  return (
    <nav className="sidebar">
      <h2>IEEE INSAT</h2>
      <ul>
        {COLLECTIONS.map((collection) => (
          <li key={collection.name}>
            <button
              className={active === collection.name ? 'active' : ''}
              onClick={() => onSelect(collection.name)}
            >
              {collection.label}
            </button>
          </li>
        ))}
        <li>
          <button className={active === 'mirror' ? 'active' : ''} onClick={() => onSelect('mirror')}>
            Mirror status
          </button>
        </li>
      </ul>
      <div className="sidebar-footer">
        <span>
          {user?.username} <em>({user?.role})</em>
        </span>
        <button onClick={() => void logout()}>Log out</button>
      </div>
    </nav>
  )
}
