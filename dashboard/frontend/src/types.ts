export type Role = 'admin' | 'editor'

export interface User {
  username: string
  role: Role
}

export type ItemStatus = 'draft' | 'published'

export interface BaseItem {
  id: string
  status: ItemStatus
  created_at: string
  updated_at: string
  updated_by: string
  [key: string]: unknown
}

export interface MirrorStatus {
  mirror_id: string
  last_seen: string
  uptime_s: number
  current_page: string | null
  last_sync_at: string | null
  last_error: string | null
  online: boolean
}

export type CollectionName = 'events' | 'announcements' | 'about' | 'achievements' | 'board'
