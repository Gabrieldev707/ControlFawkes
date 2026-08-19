import { ArrowLeft, Clapperboard, Play, Sparkles, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import {
  Achievements,
  type Conquista,
  type Progresso,
} from '../../components/fawkes-remote/Achievements'
import { GenreTiles } from '../../components/fawkes-remote/GenreTiles'
import { ProfilePhoto } from '../../components/fawkes-remote/ProfilePhoto'
import { RemoteStatusText } from '../../components/fawkes-remote/RemoteStatusText'
import { apiBaseUrl } from '../../features/fawkes-remote/apiUrl'
import { PLATFORM_BRANDS } from '../../features/fawkes-remote/platformBrand'
import { isPlatform, type Platform } from '../../features/fawkes-remote/types'


interface ProfileScreenProps {
  disabled: boolean
  statusMessage: string
  statusError: boolean
  credentials: { deviceId: string; token: string } | null
  /** Retomar: manda a busca do título para a plataforma onde ele estava. */
  onResume: (platform: Platform | null, title: string) => void
  onBack: () => void
}

interface Assistido {
  titulo: string
  platform: Platform | null
  segundos: number
  posicao: number | null
  duracao: number | null
  posterUrl: string | null
  /** Onde a pessoa parou, quando é série. Sem isto o cartão não dizia de ONDE
   *  continuar — só o nome da obra e mais nada. */
  episodio: string | null
}

interface Contagem {
  nome: string
  segundos: number
}

interface SecaoDeServico {
  platform: Platform
  itens: Assistido[]
}

interface Perfil {
  continuar: Assistido[]
  continuarPorServico: SecaoDeServico[]
  generos: Contagem[]
  plataformas: Contagem[]
  totalDeTitulos: number
  totalDeSegundos: number
  conquistas: Conquista[]
  progresso: Progresso | null
}

interface Sugestao {
  title: string
  year: number | null
  posterUrl: string
}

/** "faltam 47 min" — o quanto sobra, do jeito que se fala. */
function restanteEmTexto(segundos: number): string {
  const minutos = Math.round(segundos / 60)
  if (minutos < 1) return 'quase no fim'
  if (minutos < 60) return minutos === 1 ? 'falta 1 min' : `faltam ${minutos} min`
  const horas = Math.floor(minutos / 60)
  const resto = minutos % 60
  if (resto === 0) return horas === 1 ? 'falta 1 h' : `faltam ${horas} h`
  return `faltam ${horas} h ${resto} min`
}

/**
 * Quanto falta para acabar, quando o servidor sabe dizer.
 *
 * Uma pergunta só por cartão, e sempre a mesma. A primeira versão disto
 * mostrava a minutagem quando havia posição e caía para o tempo somado quando
 * não havia — e aí a mesma linha da mesma faixa dizia "1.1 h vistos" num
 * cartão e "34:18 de 1:22:08" no cartão do lado. Duas perguntas diferentes
 * ("quanto eu já vi" e "onde eu parei") no mesmo lugar da tela, e quem lê não
 * tem como saber qual das duas está lendo.
 *
 * Numa lista chamada "continuar assistindo", a pergunta é quanto falta. Quando
 * não dá para responder — nem todo serviço publica a linha do tempo, e com a
 * SMTC pendurada não há posição para guardar —, o lugar fica vazio. Vazio diz
 * "não sei"; um número que responde outra pergunta diz algo errado.
 */
function restanteDe(
  posicao: number | null,
  duracao: number | null,
): { proporcao: number; legenda: string } | null {
  if (posicao === null || duracao === null || duracao <= 0 || posicao < 0) return null
  return {
    proporcao: Math.min(1, posicao / duracao),
    legenda: restanteEmTexto(Math.max(0, duracao - posicao)),
  }
}

function horas(segundos: number): string {
  if (segundos < 3600) return `${Math.max(1, Math.round(segundos / 60))} min`
  const total = segundos / 3600
  return `${total < 10 ? total.toFixed(1) : Math.round(total)} h`
}

/**
 * Uma faixa de obras para retomar.
 *
 * Extraída porque agora há mais de uma: a principal, com o que se viu por
 * último em qualquer serviço, e uma por serviço. Duas cópias do mesmo cartão
 * divergiriam — foi assim que o mapa de logos acabou desencontrado em quatro
 * telas.
 */
function FaixaDeObras({
  itens,
  disabled,
  onResume,
}: {
  itens: Assistido[]
  disabled: boolean
  onResume: (platform: Platform | null, titulo: string) => void
}) {
  return (
    <div className="profile-screen__faixa">
      {itens.map((item) => {
        const restante = restanteDe(item.posicao, item.duracao)
        return (
          <button
            key={`${item.platform}-${item.titulo}`}
            type="button"
            className="continuar-card"
            disabled={disabled}
            aria-label={
              [
                `Retomar ${item.titulo}`,
                item.episodio,
                restante?.legenda,
              ].filter(Boolean).join(', ')
            }
            onClick={() => onResume(item.platform, item.titulo)}
          >
            <span className="continuar-card__capa" aria-hidden="true">
              {item.posterUrl !== null
                ? <img src={item.posterUrl} alt="" loading="lazy" />
                : <Play size={20} />}
              {item.platform !== null ? (
                <img
                  className="continuar-card__logo"
                  src={PLATFORM_BRANDS[item.platform].logo}
                  alt=""
                />
              ) : null}
              {/* Sobre a capa, como todo serviço faz: é onde o olho já procura
                  o quanto falta. */}
              {restante !== null ? (
                <span className="continuar-card__barra">
                  <span style={{ width: `${restante.proporcao * 100}%` }} />
                </span>
              ) : null}
            </span>
            <span className="continuar-card__titulo">{item.titulo}</span>
            {/* Em QUE episódio a pessoa parou — a resposta para "continuar de
                onde?", que o cartão não dava.

                Linha própria, e não no lugar do tempo: o slot de tempo responde
                "quanto falta" e só isso. Misturar ali "8,5 h vistas" com
                "faltam 20 min" na mesma faixa põe duas perguntas diferentes no
                mesmo lugar, e quem lê não sabe qual está lendo — foi um defeito
                já corrigido uma vez, e o teste que o protege continua de pé. */}
            {item.episodio !== null ? (
              <span className="continuar-card__episodio" title={item.episodio}>
                {item.episodio}
              </span>
            ) : null}
            {/* A barra e o texto aparecem juntos ou não aparecem: os dois saem
                da mesma posição, e um sem o outro sugeriria que a informação
                que falta é de outro tipo. */}
            {restante !== null ? (
              <span className="continuar-card__tempo">{restante.legenda}</span>
            ) : null}
          </button>
        )
      })}
    </div>
  )
}

/** Só o que veio no formato esperado: a lista alimenta `src` de imagens. */
function comoPerfil(dados: unknown): Perfil | null {
  if (typeof dados !== 'object' || dados === null) return null
  const bruto = dados as Record<string, unknown>

  const contagens = (valor: unknown): Contagem[] => (
    Array.isArray(valor)
      ? valor.flatMap((item) => {
        if (typeof item !== 'object' || item === null) return []
        const { nome, segundos } = item as Record<string, unknown>
        if (typeof nome !== 'string' || typeof segundos !== 'number') return []
        return [{ nome, segundos }]
      })
      : []
  )

  // Uma leitura só de item assistido, usada pela faixa principal e por todas as
  // faixas de serviço. Duas cópias divergiriam, e a que ficasse para trás
  // deixaria de barrar um `posterUrl` que não é https — que alimenta `src`.
  const assistidos = (valor: unknown): Assistido[] => (
    Array.isArray(valor)
      ? valor.flatMap((item) => {
        if (typeof item !== 'object' || item === null) return []
        const dado = item as Record<string, unknown>
        if (typeof dado.titulo !== 'string' || !dado.titulo) return []
        const poster = typeof dado.posterUrl === 'string' && dado.posterUrl.startsWith('https://')
          ? dado.posterUrl
          : null
        return [{
          titulo: dado.titulo,
          platform: isPlatform(dado.platform) ? dado.platform : null,
          segundos: typeof dado.segundos === 'number' ? dado.segundos : 0,
          posicao: typeof dado.posicao === 'number' ? dado.posicao : null,
          duracao: typeof dado.duracao === 'number' ? dado.duracao : null,
          posterUrl: poster,
          episodio: typeof dado.episodio === 'string' && dado.episodio
            ? dado.episodio
            : null,
        }]
      })
      : []
  )

  const continuar = assistidos(bruto.continuar)

  // Só serviço reconhecido vira seção: o título dela é o nome da marca, e sem
  // plataforma não há nome nem logo para pôr.
  const continuarPorServico = Array.isArray(bruto.continuarPorServico)
    ? bruto.continuarPorServico.flatMap((secao) => {
      if (typeof secao !== 'object' || secao === null) return []
      const dado = secao as Record<string, unknown>
      if (!isPlatform(dado.platform)) return []
      const itens = assistidos(dado.itens)
      return itens.length > 0 ? [{ platform: dado.platform, itens }] : []
    })
    : []

  const conquistas = Array.isArray(bruto.conquistas)
    ? bruto.conquistas.flatMap((item) => {
      if (typeof item !== 'object' || item === null) return []
      const dado = item as Record<string, unknown>
      if (typeof dado.codigo !== 'string' || typeof dado.nome !== 'string') return []
      return [{
        codigo: dado.codigo,
        nome: dado.nome,
        descricao: typeof dado.descricao === 'string' ? dado.descricao : '',
        atual: typeof dado.atual === 'number' ? dado.atual : 0,
        alvo: typeof dado.alvo === 'number' && dado.alvo > 0 ? dado.alvo : 1,
        conquistada: dado.conquistada === true,
      }]
    })
    : []

  const cru = bruto.progresso
  const progresso = typeof cru === 'object' && cru !== null
    && typeof (cru as Record<string, unknown>).nivel === 'number'
    && typeof (cru as Record<string, unknown>).total === 'number'
    ? {
      nivel: (cru as Record<string, number>).nivel,
      total: (cru as Record<string, number>).total,
      proxima: conquistas.find(
        (c) => c.codigo === ((cru as Record<string, unknown>).proxima as
          Record<string, unknown> | null)?.codigo,
      ) ?? null,
    }
    : null

  return {
    continuar,
    continuarPorServico,
    generos: contagens(bruto.generos),
    plataformas: contagens(bruto.plataformas),
    totalDeTitulos: typeof bruto.totalDeTitulos === 'number' ? bruto.totalDeTitulos : 0,
    totalDeSegundos: typeof bruto.totalDeSegundos === 'number' ? bruto.totalDeSegundos : 0,
    conquistas,
    progresso,
  }
}

function comoSugestoes(
  dados: unknown,
): { base: string | null; titles: Sugestao[]; filtrado: boolean } {
  if (typeof dados !== 'object' || dados === null) {
    return { base: null, titles: [], filtrado: false }
  }
  const bruto = dados as Record<string, unknown>
  const base = typeof bruto.base === 'object' && bruto.base !== null
    ? (bruto.base as Record<string, unknown>).titulo
    : null

  const titles = Array.isArray(bruto.titles)
    ? bruto.titles.flatMap((item) => {
      if (typeof item !== 'object' || item === null) return []
      const { title, year, posterUrl } = item as Record<string, unknown>
      if (typeof title !== 'string' || !title) return []
      if (typeof posterUrl !== 'string' || !posterUrl.startsWith('https://')) return []
      return [{ title, year: typeof year === 'number' ? year : null, posterUrl }]
    })
    : []

  return {
    base: typeof base === 'string' ? base : null,
    titles,
    filtrado: bruto.filtrado === true,
  }
}

/**
 * O perfil de quem usa o controle.
 *
 * Não é o perfil da Netflix — aquele é "quem está assistindo?" e vive na tela
 * inicial. Este é o que este computador andou vendo: o que ficou pela metade,
 * do que você gosta, e o que combina com isso nos serviços que você tem.
 *
 * Tudo sai do que o laço de "tocando agora" já observava e descartava. Nada
 * daqui depende de conta em lugar nenhum.
 */
export function ProfileScreen({
  disabled,
  statusMessage,
  statusError,
  credentials,
  onResume,
  onBack,
}: ProfileScreenProps) {
  const [perfil, setPerfil] = useState<Perfil | null>(null)
  const [sugestoes, setSugestoes] = useState<{
    base: string | null
    titles: Sugestao[]
    filtrado: boolean
  }>({ base: null, titles: [], filtrado: false })
  const [apagando, setApagando] = useState(false)

  const cabecalhos = useCallback(() => ({
    'X-Device-Id': credentials?.deviceId ?? '',
    'X-Device-Token': credentials?.token ?? '',
  }), [credentials])

  const carregar = useCallback(async () => {
    if (credentials === null) return
    try {
      const resposta = await fetch(`${apiBaseUrl()}/profile`, { headers: cabecalhos() })
      setPerfil(resposta.ok ? comoPerfil(await resposta.json()) : null)
    } catch {
      setPerfil(null)
    }
  }, [cabecalhos, credentials])

  useEffect(() => { void carregar() }, [carregar])

  // As recomendações custam várias idas ao catálogo; chegam depois, sem
  // segurar o resto da tela.
  //
  // É essa mesma chamada que faz o servidor descobrir a capa dos títulos novos.
  // Por isso o perfil é lido de novo quando ela termina: sem isso, o filme que
  // você começou hoje só ganharia imagem na próxima vez que a tela abrisse.
  useEffect(() => {
    if (credentials === null) return
    let cancelado = false
    fetch(`${apiBaseUrl()}/profile/recommendations`, { headers: cabecalhos() })
      .then((resposta) => (resposta.ok ? resposta.json() : null))
      .then((dados) => {
        if (cancelado) return
        if (dados) setSugestoes(comoSugestoes(dados))
        return carregar()
      })
      .catch(() => {})
    return () => { cancelado = true }
  }, [cabecalhos, carregar, credentials])

  async function apagar() {
    if (credentials === null) return
    setApagando(true)
    try {
      await fetch(`${apiBaseUrl()}/profile/history`, {
        method: 'DELETE',
        headers: cabecalhos(),
      })
      await carregar()
      setSugestoes({ base: null, titles: [], filtrado: false })
    } catch {
      // Falhou apagar: a tela continua como está e o toque pode ser repetido.
    }
    setApagando(false)
  }

  const vazio = perfil !== null && perfil.totalDeTitulos === 0

  return (
    <main className="remote-screen profile-screen" aria-labelledby="profile-screen-title">
      <button type="button" className="remote-screen__back" aria-label="Voltar" onClick={onBack}>
        <ArrowLeft size={18} aria-hidden="true" />
        Voltar
      </button>

      <div className="profile-screen__heading">
        <p className="remote-screen__eyebrow">Seu histórico neste computador</p>
        <h2 id="profile-screen-title">Perfil</h2>
      </div>

      <ProfilePhoto
        credentials={credentials}
        nivel={perfil?.progresso?.nivel ?? 0}
        total={perfil?.progresso?.total ?? 0}
      />

      <RemoteStatusText message={statusMessage} error={statusError} />

      {vazio ? (
        <p className="profile-screen__vazio">
          <Clapperboard size={18} aria-hidden="true" />
          Assista alguma coisa por uns minutos e ela aparece aqui. Nada é
          registrado antes de 90 segundos.
        </p>
      ) : null}

      {perfil !== null && perfil.continuar.length > 0 ? (
        <section aria-labelledby="continuar-titulo">
          <p className="profile-screen__secao" id="continuar-titulo">Continuar assistindo</p>
          <FaixaDeObras itens={perfil.continuar} disabled={disabled} onResume={onResume} />
        </section>
      ) : null}

      {/* E o mesmo, serviço a serviço.

          A faixa acima tem teto, e um teto único faz os serviços disputarem
          entre si: medido em 17/08/2026, três vídeos do YouTube de 16/08
          empurraram para fora do corte tudo o que era de 14/08 — Família
          Soprano, A Casa do Dragão e Rick and Morty estavam no histórico,
          inteiros, e não cabiam na tela. Maratonar um serviço não pode
          enterrar o que se assiste nos outros. */}
      {perfil !== null && perfil.continuarPorServico.map((secao) => (
        secao.itens.length > 0 ? (
          <section key={secao.platform} aria-labelledby={`continuar-${secao.platform}`}>
            <p className="profile-screen__secao" id={`continuar-${secao.platform}`}>
              <img
                className="profile-screen__secao-logo"
                src={PLATFORM_BRANDS[secao.platform].logo}
                alt=""
                aria-hidden="true"
              />
              {`Continuar no ${PLATFORM_BRANDS[secao.platform].name}`}
            </p>
            <FaixaDeObras itens={secao.itens} disabled={disabled} onResume={onResume} />
          </section>
        ) : null
      ))}

      {sugestoes.titles.length > 0 ? (
        <section aria-labelledby="sugestoes-titulo">
          <p className="profile-screen__secao" id="sugestoes-titulo">
            <Sparkles size={12} aria-hidden="true" />
            {sugestoes.base !== null
              ? `Porque você assistiu ${sugestoes.base}`
              : 'Com base no que você assistiu'}
          </p>
          <div className="profile-screen__faixa">
            {sugestoes.titles.map((item) => (
              <button
                key={`${item.title}-${item.year}`}
                type="button"
                className="sugestao-card"
                disabled={disabled}
                aria-label={`Procurar ${item.title}`}
                onClick={() => onResume(null, item.title)}
              >
                <img src={item.posterUrl} alt="" aria-hidden="true" loading="lazy" />
                <span>{item.title}</span>
              </button>
            ))}
          </div>
          {/* Só quando o filtro existiu de verdade: sem nenhum serviço de
              catálogo no histórico, nada foi filtrado, e a frase viraria uma
              promessa falsa sobre a lista logo acima. */}
          {sugestoes.filtrado ? (
            <p className="profile-screen__nota">
              Só o que está nos serviços que aparecem no seu histórico.
            </p>
          ) : null}
        </section>
      ) : null}

      {perfil !== null && perfil.generos.length > 0 ? (
        <section aria-labelledby="generos-titulo">
          <p className="profile-screen__secao" id="generos-titulo">O que você mais vê</p>
          <GenreTiles generos={perfil.generos} formatar={horas} />
        </section>
      ) : null}

      {perfil !== null ? (
        <Achievements conquistas={perfil.conquistas} progresso={perfil.progresso} />
      ) : null}

      {perfil !== null && perfil.totalDeTitulos > 0 ? (
        <section className="profile-screen__numeros" aria-label="Números">
          <div>
            <strong>{perfil.totalDeTitulos}</strong>
            <span>títulos</span>
          </div>
          <div>
            <strong>{horas(perfil.totalDeSegundos)}</strong>
            <span>assistidas</span>
          </div>
          <div>
            {/* O logo em vez do nome: é assim que o serviço é reconhecido em
                toda a tela, e "PRIME_VIDEO" escrito nunca coube na caixa. */}
            {perfil.plataformas.length > 0
            && PLATFORM_BRANDS[perfil.plataformas[0].nome as Platform] !== undefined ? (
              <img
                className="profile-screen__logo"
                src={PLATFORM_BRANDS[perfil.plataformas[0].nome as Platform].logo}
                alt={PLATFORM_BRANDS[perfil.plataformas[0].nome as Platform].name}
              />
            ) : (
              <strong>—</strong>
            )}
            <span>mais usado</span>
          </div>
        </section>
      ) : null}

      {perfil !== null && perfil.totalDeTitulos > 0 ? (
        <button
          type="button"
          className="profile-screen__apagar"
          disabled={apagando}
          onClick={() => void apagar()}
        >
          <Trash2 size={14} aria-hidden="true" />
          Apagar meu histórico
        </button>
      ) : null}
    </main>
  )
}
