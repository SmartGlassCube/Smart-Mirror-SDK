// Africa/Tunis has been a fixed UTC+1 with no DST since 2009 -- a constant
// offset is correct and avoids pulling in a timezone library for this.
const TUNIS_OFFSET_MINUTES = 60

/** UTC ISO string -> value for <input type="datetime-local">, rendered in Africa/Tunis time. */
export function utcIsoToTunisInput(utcIso: string | null | undefined): string {
  if (!utcIso) return ''
  const tunisMs = new Date(utcIso).getTime() + TUNIS_OFFSET_MINUTES * 60_000
  return new Date(tunisMs).toISOString().slice(0, 16)
}

/** <input type="datetime-local"> value (interpreted as Africa/Tunis wall-clock) -> UTC ISO string. */
export function tunisInputToUtcIso(inputValue: string): string {
  const asIfUtcMs = Date.parse(`${inputValue}:00Z`)
  const trueUtcMs = asIfUtcMs - TUNIS_OFFSET_MINUTES * 60_000
  return new Date(trueUtcMs).toISOString()
}
