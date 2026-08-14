import { Check, Film, Loader2, TriangleAlert, X } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { apiBaseUrl } from '../../features/fawkes-remote/apiUrl'


interface CatalogKeyCardProps {
  credentials: { deviceId: string; token: string } | null
}

interface EstadoDoCatalogo {
  enabled: boolean
  source: 'NENHUMA' | 'AMBIENTE' | 'GUARDADA' | 'FIXA'
  region: string
  envOverrides: boolean
}

type Veredito =
  | { tipo: 'nenhum' }
  | { tipo: 'testando' }
  | { tipo: 'ok'; titulo: string; ano: number | null; plataformas: string[] }
  | { tipo: 'erro'; mensagem: string }

const NOMES: Record<string, string> = {
  NETFLIX: 'Netflix',
  PRIME_VIDEO: 'Prime Video',
  YOUTUBE: 'YouTube',
  SPOTIFY: 'Spotify',
  MAX: 'Max',
  DISNEY_PLUS: 'Disney+',
}

/**
 * Ligar o catálogo sem editar variável de ambiente nem reiniciar nada.
 *
 * Antes, a única forma de saber se a chave prestava era fazer uma busca e
 * torcer: o catálogo falha em silêncio de propósito, então chave errada, rede
 * caída e título inexistente eram indistinguíveis. Aqui a chave é testada
 * contra a API de verdade e o veredito vem com o resultado da busca — a prova
 * de que funcionou, não um "ok" genérico.
 */
export function CatalogKeyCard({ credentials }: CatalogKeyCardProps) {
  const [estado, setEstado] = useState<EstadoDoCatalogo | null>(null)
  const [chave, setChave] = useState('')
  const [veredito, setVeredito] = useState<Veredito>({ tipo: 'nenhum' })

  const cabecalhos = useCallback(() => ({
    'Content-Type': 'application/json',
    'X-Device-Id': credentials?.deviceId ?? '',
    'X-Device-Token': credentials?.token ?? '',
  }), [credentials])

  useEffect(() => {
    if (credentials === null) return
    let cancelado = false
    fetch(`${apiBaseUrl()}/catalog/tmdb`, { headers: cabecalhos() })
      .then((r) => (r.ok ? r.json() : null))
      .then((dados) => { if (!cancelado && dados) setEstado(dados) })
      .catch(() => undefined)
    return () => { cancelado = true }
  }, [cabecalhos, credentials])

  const salvar = async () => {
    if (!chave.trim() || credentials === null) return
    setVeredito({ tipo: 'testando' })
    try {
      const resposta = await fetch(`${apiBaseUrl()}/catalog/tmdb`, {
        method: 'POST',
        headers: cabecalhos(),
        body: JSON.stringify({ apiKey: chave.trim() }),
      })
      const dados = await resposta.json().catch(() => null)
      if (!resposta.ok) {
        setVeredito({
          tipo: 'erro',
          mensagem: typeof dados?.detail === 'string'
            ? dados.detail
            : 'Não foi possível verificar a chave.',
        })
        return
      }
      setEstado({
        enabled: true,
        source: dados.source,
        region: dados.region,
        envOverrides: false,
      })
      setChave('')
      setVeredito({
        tipo: 'ok',
        titulo: dados.sample.title,
        ano: dados.sample.year,
        plataformas: dados.sample.platforms ?? [],
      })
    } catch {
      setVeredito({ tipo: 'erro', mensagem: 'O computador não respondeu.' })
    }
  }

  const remover = async () => {
    if (credentials === null) return
    try {
      const resposta = await fetch(`${apiBaseUrl()}/catalog/tmdb`, {
        method: 'DELETE',
        headers: cabecalhos(),
      })
      if (!resposta.ok) return
      setEstado(await resposta.json())
      setVeredito({ tipo: 'nenhum' })
    } catch {
      // Nada a fazer: o estado na tela continua o que era.
    }
  }

  const ligado = estado?.enabled === true

  return (
    <section className="settings-card" aria-labelledby="settings-catalog-title">
      <h3 id="settings-catalog-title" className="settings-card__title">
        <Film size={15} aria-hidden="true" />
        Catálogo de títulos
      </h3>

      <p className="settings-card__text">
        {ligado
          ? `Ligado. O controle diz em qual serviço o título está (região ${estado?.region}).`
          : 'Desligado. Com uma chave do TMDB, o controle passa a dizer onde o título está em vez de perguntar.'}
      </p>

      {estado?.envOverrides ? (
        <p className="catalog-key__aviso">
          <TriangleAlert size={13} aria-hidden="true" />
          A chave vem da variável de ambiente e tem prioridade sobre esta tela.
        </p>
      ) : ligado ? (
        <button type="button" className="settings-danger" onClick={remover}>
          <X size={15} aria-hidden="true" />
          Remover a chave
        </button>
      ) : (
        <form
          className="catalog-key"
          onSubmit={(event) => {
            event.preventDefault()
            void salvar()
          }}
        >
          <input
            type="text"
            value={chave}
            aria-label="Chave do TMDB"
            placeholder="Cole a chave do TMDB"
            autoComplete="off"
            autoCorrect="off"
            autoCapitalize="none"
            spellCheck={false}
            onChange={(event) => setChave(event.target.value)}
          />
          <button type="submit" disabled={!chave.trim() || veredito.tipo === 'testando'}>
            {veredito.tipo === 'testando'
              ? <Loader2 size={15} aria-hidden="true" className="voice-btn__spinner" />
              : 'Verificar'}
          </button>
        </form>
      )}

      {veredito.tipo === 'ok' ? (
        <p className="catalog-key__ok" role="status">
          <Check size={13} aria-hidden="true" />
          Funcionou. Achei “{veredito.titulo}”
          {veredito.ano !== null ? ` (${veredito.ano})` : ''}
          {veredito.plataformas.length > 0
            ? ` no ${veredito.plataformas.map((p) => NOMES[p] ?? p).join(', ')}.`
            : ', sem serviço por assinatura na sua região.'}
        </p>
      ) : null}

      {veredito.tipo === 'erro' ? (
        <p className="catalog-key__erro" role="alert">
          <TriangleAlert size={13} aria-hidden="true" />
          {veredito.mensagem}
        </p>
      ) : null}
    </section>
  )
}
