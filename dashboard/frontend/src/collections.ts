import type { CollectionName } from './types'

export type FieldType = 'text' | 'textarea' | 'datetime' | 'number' | 'tags' | 'select'

export interface FieldSchema {
  name: string
  label: string
  type: FieldType
  required?: boolean
  options?: string[]
}

export interface CollectionConfig {
  name: CollectionName
  label: string
  singular: string
  titleField: string
  fields: FieldSchema[]
}

export const COLLECTIONS: CollectionConfig[] = [
  {
    name: 'events',
    label: 'Events',
    singular: 'event',
    titleField: 'title',
    fields: [
      { name: 'title', label: 'Title', type: 'text', required: true },
      { name: 'description', label: 'Description', type: 'textarea', required: true },
      { name: 'start', label: 'Start (Africa/Tunis)', type: 'datetime', required: true },
      { name: 'end', label: 'End (Africa/Tunis)', type: 'datetime' },
      { name: 'location', label: 'Location', type: 'text' },
      { name: 'tags', label: 'Tags (comma-separated)', type: 'tags' },
      { name: 'registration_url', label: 'Registration URL', type: 'text' },
      { name: 'image_url', label: 'Image URL', type: 'text' },
    ],
  },
  {
    name: 'announcements',
    label: 'Announcements',
    singular: 'announcement',
    titleField: 'title',
    fields: [
      { name: 'title', label: 'Title', type: 'text', required: true },
      { name: 'body', label: 'Body', type: 'textarea', required: true },
      { name: 'publish_at', label: 'Publish at (Africa/Tunis)', type: 'datetime', required: true },
      { name: 'expires_at', label: 'Expires at (Africa/Tunis)', type: 'datetime' },
      { name: 'priority', label: 'Priority', type: 'select', options: ['normal', 'low', 'high'], required: true },
    ],
  },
  {
    name: 'about',
    label: 'About',
    singular: 'section',
    titleField: 'title',
    fields: [
      { name: 'key', label: 'Key', type: 'text', required: true },
      { name: 'title', label: 'Title', type: 'text', required: true },
      { name: 'body', label: 'Body', type: 'textarea', required: true },
    ],
  },
  {
    name: 'achievements',
    label: 'Achievements',
    singular: 'achievement',
    titleField: 'title',
    fields: [
      { name: 'title', label: 'Title', type: 'text', required: true },
      { name: 'date', label: 'Date (Africa/Tunis)', type: 'datetime', required: true },
      { name: 'description', label: 'Description', type: 'textarea', required: true },
    ],
  },
  {
    name: 'board',
    label: 'Board',
    singular: 'board member',
    titleField: 'name',
    fields: [
      { name: 'name', label: 'Name', type: 'text', required: true },
      { name: 'role', label: 'Role', type: 'text', required: true },
      { name: 'term', label: 'Term', type: 'text', required: true },
      { name: 'order', label: 'Order', type: 'number', required: true },
      { name: 'email', label: 'Email', type: 'text' },
    ],
  },
]
