import { useEffect, useState } from 'react'


/**
 * Uma imagem que exige as credenciais do pareamento.
 *
 * Não dá para usar `<img src>` direto: o recurso exige cabeçalho de
 * autenticação, e `src` não manda cabeçalho. Buscar como blob resolve sem
 * precisar colocar o token na URL, onde ele acabaria em log e em histórico.
 *
 * Nasceu na capa da mídia e virou compartilhado quando o avatar do perfil
 * precisou exatamente do mesmo cuidado — inclusive o de revogar o blob, que é
 * o detalhe fácil de esquecer numa segunda cópia.
 */
export function useAuthenticatedImage(
  url: string | null,
  credentials: { deviceId: string; token: string } | null,
): string | null {
  const [objectUrl, setObjectUrl] = useState<string | null>(null)

  useEffect(() => {
    if (url === null || credentials === null) {
      setObjectUrl(null)
      return
    }

    let cancelado = false
    let criada: string | null = null

    fetch(url, {
      headers: {
        'X-Device-Id': credentials.deviceId,
        'X-Device-Token': credentials.token,
      },
    })
      .then((resposta) => (resposta.ok ? resposta.blob() : null))
      .then((blob) => {
        if (cancelado || blob === null) return
        criada = URL.createObjectURL(blob)
        setObjectUrl(criada)
      })
      .catch(() => setObjectUrl(null))

    return () => {
      cancelado = true
      // Sem revogar, cada troca deixaria um blob preso na memória.
      if (criada !== null) URL.revokeObjectURL(criada)
    }
  }, [url, credentials])

  return objectUrl
}
