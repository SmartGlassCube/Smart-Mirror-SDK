import { useState, type FormEvent } from 'react'
import type { CollectionConfig, FieldSchema } from '../collections'
import type { BaseItem } from '../types'
import { tunisInputToUtcIso, utcIsoToTunisInput } from '../time'

interface Props {
  config: CollectionConfig
  initial: BaseItem | null
  onCancel: () => void
  onSubmit: (payload: Record<string, unknown>) => Promise<void>
}

function toFormValue(field: FieldSchema, raw: unknown): string {
  if (raw === undefined || raw === null) {
    if (field.type === 'select' && field.options?.length) return field.options[0]
    return ''
  }
  if (field.type === 'datetime') return utcIsoToTunisInput(String(raw))
  if (field.type === 'tags') return Array.isArray(raw) ? raw.join(', ') : String(raw)
  return String(raw)
}

export function ItemForm({ config, initial, onCancel, onSubmit }: Props) {
  const [values, setValues] = useState<Record<string, string>>(() => {
    const initialValues: Record<string, string> = {}
    for (const field of config.fields) {
      initialValues[field.name] = toFormValue(field, initial?.[field.name])
    }
    return initialValues
  })
  const [status, setStatus] = useState<string>(initial ? String(initial.status) : 'draft')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function update(name: string, value: string) {
    setValues((prev) => ({ ...prev, [name]: value }))
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)

    const payload: Record<string, unknown> = { status }
    for (const field of config.fields) {
      const raw = (values[field.name] ?? '').trim()
      if (raw === '') {
        if (field.required) {
          setError(`${field.label} is required`)
          return
        }
        continue
      }
      if (field.type === 'datetime') payload[field.name] = tunisInputToUtcIso(raw)
      else if (field.type === 'number') payload[field.name] = Number(raw)
      else if (field.type === 'tags') {
        payload[field.name] = raw.split(',').map((part) => part.trim()).filter(Boolean)
      } else payload[field.name] = raw
    }

    setSubmitting(true)
    try {
      await onSubmit(payload)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="item-form" onSubmit={handleSubmit}>
      <h3>{initial ? `Edit ${config.singular}` : `New ${config.singular}`}</h3>
      {config.fields.map((field) => (
        <label key={field.name}>
          {field.label}
          {field.type === 'textarea' ? (
            <textarea rows={4} value={values[field.name]} onChange={(e) => update(field.name, e.target.value)} />
          ) : field.type === 'select' ? (
            <select value={values[field.name]} onChange={(e) => update(field.name, e.target.value)}>
              {field.options?.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          ) : field.type === 'datetime' ? (
            <input
              type="datetime-local"
              value={values[field.name]}
              onChange={(e) => update(field.name, e.target.value)}
            />
          ) : field.type === 'number' ? (
            <input type="number" value={values[field.name]} onChange={(e) => update(field.name, e.target.value)} />
          ) : (
            <input type="text" value={values[field.name]} onChange={(e) => update(field.name, e.target.value)} />
          )}
        </label>
      ))}
      <label>
        Status
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="draft">draft</option>
          <option value="published">published</option>
        </select>
      </label>
      {error && <p className="error">{error}</p>}
      <div className="form-actions">
        <button type="submit" disabled={submitting}>
          {submitting ? 'Saving...' : 'Save'}
        </button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  )
}
