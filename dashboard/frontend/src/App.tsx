import { useState } from 'react'
import { CollectionView } from './components/CollectionView'
import { LoginForm } from './components/LoginForm'
import { MirrorStatusView } from './components/MirrorStatusView'
import { Sidebar, type Section } from './components/Sidebar'
import { COLLECTIONS } from './collections'
import { AuthProvider, useAuth } from './useAuth'

function Dashboard() {
  const [section, setSection] = useState<Section>('events')
  const config = COLLECTIONS.find((c) => c.name === section)

  return (
    <div className="app-shell">
      <Sidebar active={section} onSelect={setSection} />
      <main>{section === 'mirror' ? <MirrorStatusView /> : config ? <CollectionView config={config} /> : null}</main>
    </div>
  )
}

function Gate() {
  const { user, loading } = useAuth()
  if (loading) return <div className="loading-screen">Loading...</div>
  return user ? <Dashboard /> : <LoginForm />
}

export default function App() {
  return (
    <AuthProvider>
      <Gate />
    </AuthProvider>
  )
}
