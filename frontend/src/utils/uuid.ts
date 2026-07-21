export interface RequestIdRandomSource {
  randomUUID?: () => string
  fillRandomValues: (values: Uint8Array<ArrayBuffer>) => void
}

function browserRandomSource(): RequestIdRandomSource {
  const browserCrypto = globalThis.crypto
  return {
    randomUUID: typeof browserCrypto.randomUUID === 'function'
      ? () => browserCrypto.randomUUID()
      : undefined,
    fillRandomValues: (values) => { browserCrypto.getRandomValues(values) },
  }
}

export function generateRequestId(
  source: RequestIdRandomSource = browserRandomSource(),
): string {
  if (source.randomUUID) return source.randomUUID()

  const bytes = new Uint8Array(new ArrayBuffer(16))
  source.fillRandomValues(bytes)
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}
