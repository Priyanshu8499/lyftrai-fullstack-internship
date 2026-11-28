/** Anonymous session IDs act as bearer capabilities, so use 256 random bits. */
export function generateSessionId() {
  const hex = Array.from(crypto.getRandomValues(new Uint8Array(32)))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
  return `s-${hex}`;
}

export function isValidSessionId(value) {
  return typeof value === "string" && /^s-[0-9a-f]{64}$/.test(value);
}
