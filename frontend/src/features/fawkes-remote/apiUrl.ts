/**
 * Endereço do backend, a partir de como a página foi aberta.
 *
 * Mesma porta do WebSocket porque é o mesmo servidor, e o protocolo acompanha
 * o da página: uma página em https não pode buscar em http sem cair no bloqueio
 * de conteúdo misto.
 */
export function buildApiUrl(
  configuredUrl: string | undefined,
  origin: string,
  hostname: string,
  pageProtocol: string,
  port: string,
): string {
  if (configuredUrl) return configuredUrl.replace(/\/$/, '')
  if (!hostname) return origin
  return `${pageProtocol === 'https:' ? 'https' : 'http'}://${hostname}:${port}`
}

/** O endereço para esta página, já resolvido. */
export function apiBaseUrl(): string {
  return buildApiUrl(
    import.meta.env.VITE_API_URL,
    window.location.origin,
    window.location.hostname,
    window.location.protocol,
    import.meta.env.VITE_WS_PORT ?? '8100',
  )
}
