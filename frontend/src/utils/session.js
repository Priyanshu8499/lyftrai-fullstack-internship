/**
 * Generate a session ID: s-{random 8 hex chars}
 */
export function generateSessionId() {
  const hex = Array.from(crypto.getRandomValues(new Uint8Array(4)))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
  return `s-${hex}`
}
