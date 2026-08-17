import { Disc3, Pause, Play } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { useAuthenticatedImage } from '../../hooks/useAuthenticatedImage'
import { PLATFORM_BRANDS } from '../../features/fawkes-remote/platformBrand'
import { formatarTempo } from '../../features/fawkes-remote/tempo'
import type { NowPlayingSession } from '../../features/fawkes-remote/types'


interface NowPlayingCardProps {
  session: NowPlayingSession
  /** Base do backend e credenciais: a capa é um recurso autenticado. */
  apiBaseUrl: string
  credentials: { deviceId: string; token: string } | null
  onTogglePlay?: () => void
}

/**
 * O nome do serviço para o cabeçalho do cartão.
 *
 * A API de mídia do Windows não devolve "Spotify": devolve o identificador do
 * pacote. Medido na tela — apareceu
 * "SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify" inteiro ao lado de "Tocando
 * agora", que é ruído e ainda empurrava o resto da linha para fora.
 *
 * Quando a plataforma é conhecida, o nome da marca é o que a pessoa reconhece.
 * Quando não é, só passa o que já se parece com um nome — identificador de
 * pacote tem ponto, barra ou exclamação, e nada disso é nome de serviço.
 */
export function nomeDoServico(session: NowPlayingSession): string | null {
  const marca = session.platform !== null ? PLATFORM_BRANDS[session.platform] : undefined
  if (marca !== undefined) {
    return marca.name
  }
  const app = session.app?.trim() ?? ''
  if (app === '' || app.length > 24 || /[.!/\\_]/.test(app)) {
    return null
  }
  return app
}

/**
 * O que está tocando, no controle.
 *
 * O progresso é contado no próprio celular a partir do último valor recebido:
 * empurrar a posição pela rede a cada segundo gastaria uma mensagem por
 * segundo por dispositivo para dizer o que o relógio já sabe.
 */
export function NowPlayingCard({
  session,
  apiBaseUrl,
  credentials,
  onTogglePlay,
}: NowPlayingCardProps) {
  const capaLocal = useAuthenticatedImage(
    session.thumbnailId === null ? null : `${apiBaseUrl}/now-playing/thumbnail/${session.thumbnailId}`,
    credentials,
  )
  // A capa do próprio aplicativo vem primeiro: é a do álbum que está
  // tocando. O pôster do catálogo entra quando não há nenhuma — que é o
  // caso de todo filme assistido pelo navegador.
  // Um pôster que não carrega cai para o logo do serviço, e o logo é local.
  // Guarda qual URL falhou, e não um sim/não: com o booleano, a primeira
  // capa quebrada apagaria também as capas das faixas seguintes.
  const [capaQuebrada, setCapaQuebrada] = useState<string | null>(null)
  const candidata = capaLocal ?? session.posterUrl ?? null
  const capa = candidata !== null && candidata !== capaQuebrada ? candidata : null
  // Nem tudo tem pôster: um jogo ao vivo no YouTube não está no catálogo de
  // filmes. O logo do serviço é uma resposta honesta — diz de onde vem o que
  // está tocando — e evita o disco genérico, que não informa nada.
  const logo = capa === null && session.platform !== null
    ? PLATFORM_BRANDS[session.platform].logo
    : null
  const { positionSeconds, durationSeconds, playing } = session
  // O servidor avisa quando o número que mandou é desta reprodução mas parou de
  // ser atualizado pelo site. Antes ele não avisava: mandava `null`, e a
  // minutagem sumia inteira no meio do filme. Agora o número continua na tela —
  // só não anda, porque ninguém mediu esse avanço.
  const travada = session.positionStale === true
  const [decorrido, setDecorrido] = useState(positionSeconds ?? 0)
  const ancoraRef = useRef({ posicao: positionSeconds ?? 0, em: Date.now() })

  useEffect(() => {
    ancoraRef.current = { posicao: positionSeconds ?? 0, em: Date.now() }
    setDecorrido(positionSeconds ?? 0)
  }, [positionSeconds])

  useEffect(() => {
    if (!playing || positionSeconds === null || travada) return
    const timer = window.setInterval(() => {
      const { posicao, em } = ancoraRef.current
      setDecorrido(posicao + (Date.now() - em) / 1000)
    }, 500)
    return () => window.clearInterval(timer)
  }, [playing, positionSeconds, travada])

  // Quatro combinações possíveis, e cada uma merece uma resposta diferente.
  // Antes só existia "tem duração": sem ela a minutagem sumia inteira, mesmo
  // com a posição conhecida — que é o caso de transmissão ao vivo. E sem
  // posição, com duração, aparecia um "0:00" que não era verdade.
  const temPosicao = positionSeconds !== null
  const temDuracao = durationSeconds !== null && durationSeconds > 0
  const temBarra = temPosicao && temDuracao
  // O contador roda aqui no celular a partir da última posição recebida, e
  // nada o segurava. Quando o site para de publicar posição nova — o estado
  // normal com a API de mídia do Windows pendurada — o episódio acaba e o
  // contador continua: a tela mostrava "1:01:00 de 1:00:00".
  //
  // A barra já era limitada; faltava limitar o NÚMERO, que é o que se lê.
  // Sem duração não há fim para segurar: transmissão ao vivo continua correndo.
  const mostrado = temDuracao ? Math.min(decorrido, durationSeconds) : decorrido
  const proporcao = temBarra
    ? Math.min(1, Math.max(0, mostrado / durationSeconds))
    : 0

  return (
    <section className="now-playing" aria-label="Tocando agora">
      <div className="now-playing__cover" aria-hidden="true">
        {capa !== null ? (
          <img src={capa} alt="" onError={() => setCapaQuebrada(capa)} />
        ) : logo !== null ? (
          <img className="now-playing__logo" src={logo} alt="" />
        ) : (
          <Disc3 size={22} className={playing ? 'now-playing__spin' : undefined} />
        )}
      </div>

      <div className="now-playing__body">
        <p className="now-playing__eyebrow">
          {playing ? 'Tocando agora' : 'Pausado'}
          {nomeDoServico(session) !== null ? ` · ${nomeDoServico(session)}` : ''}
        </p>
        <p className="now-playing__title" title={session.title}>{session.title}</p>
        {/* O episódio primeiro, quando existe: numa série, "Rick and Morty" é a
            resposta para "o que você está vendo?" e "Campo dos Sonhos" é a
            resposta para "em qual?". O cartão mostrava só uma das duas — e era
            a segunda, que sozinha não diz nem que série é. */}
        {session.episode ? (
          <p className="now-playing__artist" title={session.episode}>{session.episode}</p>
        ) : session.artist ? (
          <p className="now-playing__artist">{session.artist}</p>
        ) : null}

        {temPosicao ? (
          <div
            className={
              travada ? 'now-playing__progress now-playing__progress--travada'
                : 'now-playing__progress'
            }
            /* Por que o número não anda, para quem estranhar que ele não ande. */
            title={travada ? 'O serviço parou de informar o tempo' : undefined}
          >
            {temBarra ? (
              <div
                className="now-playing__bar"
                role="progressbar"
                aria-label="Progresso"
                aria-valuemin={0}
                aria-valuemax={Math.round(durationSeconds)}
                aria-valuenow={Math.round(mostrado)}
              >
                <span style={{ width: `${proporcao * 100}%` }} />
              </div>
            ) : null}
            <p className="now-playing__times">
              <span>{formatarTempo(mostrado)}</span>
              {/* Sem duração é transmissão ao vivo: o tempo decorrido continua
                  valendo, e dizer "ao vivo" é mais honesto do que inventar um
                  fim que não existe. */}
              <span>{temDuracao ? formatarTempo(durationSeconds) : 'ao vivo'}</span>
            </p>
          </div>
        ) : null}
      </div>

      {onTogglePlay ? (
        <button
          type="button"
          className="now-playing__toggle"
          aria-label={playing ? 'Pausar' : 'Continuar'}
          onClick={onTogglePlay}
        >
          {playing
            ? <Pause size={17} aria-hidden="true" fill="currentColor" />
            : <Play size={17} aria-hidden="true" fill="currentColor" />}
        </button>
      ) : null}
    </section>
  )
}
