import { ArrowLeft } from 'lucide-react'
import { useEffect, useState } from 'react'

import {
  HighlightRow,
  HighlightRowSkeleton,
  type Destaque,
} from '../../components/fawkes-remote/HighlightRow'
import { PlatformGrid } from '../../components/fawkes-remote/PlatformGrid'
import { RemoteStatusText } from '../../components/fawkes-remote/RemoteStatusText'
import { apiBaseUrl } from '../../features/fawkes-remote/apiUrl'
import { PLATFORM_BRANDS } from '../../features/fawkes-remote/platformBrand'
import { isPlatform, type Platform } from '../../features/fawkes-remote/types'


interface PlatformsScreenProps {
  selectedPlatform: Platform | null
  disabled: boolean
  statusMessage: string
  statusError: boolean
  credentials?: { deviceId: string; token: string } | null
  onSelect: (platform: Platform) => void
  onPickTitle?: (platform: Platform, title: string) => void
  onBack: () => void
}

interface Linha {
  platform: Platform
  titles: Destaque[]
}

/** Só o que veio no formato esperado: a lista alimenta `src` de imagens. */
function linhasValidas(dados: unknown): Linha[] {
  if (typeof dados !== 'object' || dados === null) return []
  const rows = (dados as { rows?: unknown }).rows
  if (!Array.isArray(rows)) return []

  return rows.flatMap((linha) => {
    if (typeof linha !== 'object' || linha === null) return []
    const { platform, titles } = linha as { platform?: unknown; titles?: unknown }
    if (!isPlatform(platform) || !Array.isArray(titles)) return []

    const validos = titles.flatMap((item) => {
      if (typeof item !== 'object' || item === null) return []
      const { title, year, posterUrl } = item as Record<string, unknown>
      if (typeof title !== 'string' || !title) return []
      // O pôster vira `src`: aceitar qualquer texto deixaria um `javascript:`
      // entrar na página.
      if (typeof posterUrl !== 'string' || !posterUrl.startsWith('https://')) return []
      return [{ title, year: typeof year === 'number' ? year : null, posterUrl }]
    })

    return validos.length > 0 ? [{ platform, titles: validos }] : []
  })
}

export function PlatformsScreen({
  selectedPlatform,
  disabled,
  statusMessage,
  statusError,
  credentials = null,
  onSelect,
  onPickTitle,
  onBack,
}: PlatformsScreenProps) {
  const [linhas, setLinhas] = useState<Linha[] | null>(null)
  const [carregando, setCarregando] = useState(false)

  useEffect(() => {
    if (credentials === null) return
    let cancelado = false
    setCarregando(true)

    fetch(`${apiBaseUrl()}/catalog/highlights`, {
      headers: {
        'X-Device-Id': credentials.deviceId,
        'X-Device-Token': credentials.token,
      },
    })
      .then((resposta) => (resposta.ok ? resposta.json() : null))
      .then((dados) => { if (!cancelado) setLinhas(linhasValidas(dados)) })
      .catch(() => { if (!cancelado) setLinhas([]) })
      .finally(() => { if (!cancelado) setCarregando(false) })

    return () => { cancelado = true }
  }, [credentials])

  const temDestaques = linhas !== null && linhas.length > 0

  return (
    <main className="remote-screen platforms-screen" aria-labelledby="platforms-screen-title">
      <button type="button" className="remote-screen__back" aria-label="Voltar" onClick={onBack}>
        <ArrowLeft size={18} aria-hidden="true" />
        Voltar
      </button>

      <div className="platforms-screen__heading">
        <p className="remote-screen__eyebrow">Streaming</p>
        <h2 id="platforms-screen-title">
          {temDestaques ? 'O que assistir' : 'Plataformas'}
        </h2>
      </div>

      <RemoteStatusText message={statusMessage} error={statusError} />

      {carregando && linhas === null ? (
        <div role="status" aria-live="polite">
          <span className="visually-hidden">Buscando os destaques…</span>
          {(['NETFLIX', 'MAX', 'DISNEY_PLUS'] as const).map((plataforma) => (
            <HighlightRowSkeleton
              key={plataforma}
              logo={PLATFORM_BRANDS[plataforma].logo}
              name={PLATFORM_BRANDS[plataforma].name}
            />
          ))}
        </div>
      ) : null}

      {temDestaques ? (
        <>
          {linhas.map((linha) => (
            <HighlightRow
              key={linha.platform}
              platform={linha.platform}
              logo={PLATFORM_BRANDS[linha.platform].logo}
              name={PLATFORM_BRANDS[linha.platform].name}
              titles={linha.titles}
              disabled={disabled}
              onOpenPlatform={onSelect}
              onPickTitle={(plataforma, titulo) => onPickTitle?.(plataforma, titulo)}
            />
          ))}

          <p className="platforms-screen__all">Todas as plataformas</p>
        </>
      ) : (
        <p className="platforms-screen__intro">
          {linhas === null
            ? 'Escolha um destino. O computador abrirá somente a URL oficial cadastrada.'
            : 'Ligue o catálogo em Ajustes para ver os destaques de cada serviço aqui.'}
        </p>
      )}

      <div className="platforms-screen__grid">
        <PlatformGrid
          selectedPlatform={selectedPlatform}
          disabled={disabled}
          onSelect={onSelect}
        />
      </div>
    </main>
  )
}
