/**
 * Fase 10 — o adapter do Max.
 *
 * O DOM montado aqui é o MEDIDO. Sonda no console em 26/08/2026, com
 * Lanternas T1 Ep.2 tocando:
 *
 *     document.title                            "⁨Trust Fall⁩ • HBO Max"
 *     [data-testid="player-ux-asset-title"]     "Lanternas"
 *     [data-testid="player-ux-season-episode"]  "T1 Ep.2:"
 *     [data-testid="player-ux-asset-subtitle"]  "Salto no Escuro"
 *     rótulo acessível  "Lanternas, Temporada 1 Episódio 2, Salto no Escuro"
 *
 * O título da janela publica "Trust Fall" — o nome do EPISÓDIO em inglês, o
 * mesmo "Salto no Escuro". A série chama-se "Lanternas", e a janela nunca diz
 * isso. É o único serviço cujo título de janela é ativamente enganoso, e o
 * defeito já apareceu antes: em 18/08/2026, com Ben 10, a janela publicou
 * "⁨Fame⁩ • HBO Max" e o cartão anunciou uma obra chamada "Fame".
 */

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { beforeEach, describe, expect, it } from 'vitest'


const FONTE = readFileSync(resolve(__dirname, 'max.js'), 'utf8')

type Metadata = {
  workTitle?: string | null
  episodeTitle?: string | null
  seasonNumber?: number | null
  episodeNumber?: number | null
  pageId?: string | null
} | null

const api = new Function(`${FONTE}\nreturn { lerMax, temporadaEEpisodioMax }`)() as {
  lerMax: (d: Document, l: { pathname: string }) => Metadata
  temporadaEEpisodioMax: (
    t: string,
  ) => { temporada: number; episodio: number; marcador: string } | null
}

const { lerMax } = api

const EM_WATCH = { pathname: '/video/watch/ce67d50b-0a2d-4856-9836-ad29f4cd5883' }
const ID = 'ce67d50b-0a2d-4856-9836-ad29f4cd5883'

function porTestId(testid: string, texto: string) {
  const span = document.createElement('span')
  span.setAttribute('data-testid', testid)
  span.className = `${testid}-Fuse-Web-Play__sc-k9fw09-5 ctIycZ`
  span.textContent = texto
  document.body.appendChild(span)
}

/** O player como o Max o monta. */
function montarPlayer(
  obra: string | null,
  marcador: string | null,
  nome: string | null,
) {
  if (obra !== null) porTestId('player-ux-asset-title', obra)
  if (marcador !== null) porTestId('player-ux-season-episode', marcador)
  if (nome !== null) porTestId('player-ux-asset-subtitle', nome)
}

/** O rótulo escondido que leitores de tela leem. */
function montarRotuloAcessivel(texto: string) {
  const p = document.createElement('p')
  p.className = 'StyledVisiblyHiddenLabel-Fuse-Web-Play__sc-ja1og5-1 kQnoOz'
  p.textContent = texto
  document.body.appendChild(p)
}

beforeEach(() => {
  document.body.innerHTML = ''
})


// ── O caso medido ─────────────────────────────────────────────────────────

describe('o que a página do Max entrega', () => {
  it('lê a SÉRIE, que a janela nunca publica', () => {
    montarPlayer('Lanternas', 'T1 Ep.2:', 'Salto no Escuro')

    expect(lerMax(document, EM_WATCH)).toEqual({
      workTitle: 'Lanternas',
      episodeTitle: 'Salto no Escuro',
      seasonNumber: 1,
      episodeNumber: 2,
      pageId: ID,
    })
  })

  it('o nome do episódio não ocupa a linha da obra', () => {
    // A regressão que este arquivo existe para impedir. Sem adapter, o que
    // chegava era "Trust Fall" — e ele ia para a linha da série.
    montarPlayer('Lanternas', 'T1 Ep.2:', 'Salto no Escuro')

    const lida = lerMax(document, EM_WATCH)

    expect(lida?.workTitle).not.toBe('Salto no Escuro')
    expect(lida?.workTitle).not.toBe('Trust Fall')
  })

  it('tira o dois-pontos de layout do marcador', () => {
    montarPlayer('Lanternas', 'T1 Ep.2:', 'Salto no Escuro')

    expect(lerMax(document, EM_WATCH)?.episodeNumber).toBe(2)
  })
})


// ── A armadilha do "Ep." com ponto ────────────────────────────────────────

describe('as grafias do marcador', () => {
  it('"T1 Ep.2:" — a grafia MEDIDA do Max', () => {
    // Ela NÃO casa com o padrão que os outros adapters usam: o ponto entre
    // "Ep" e "2" quebra a expressão. Reusar sem medir teria descartado
    // temporada e episódio em silêncio.
    expect(api.temporadaEEpisodioMax('T1 Ep.2:')).toMatchObject({
      temporada: 1, episodio: 2,
    })
  })

  it.each([
    ['S1 Ep.2', 1, 2],
    ['T2:E10', 2, 10],
    ['S3 E7', 3, 7],
    ['Temporada 1 Episódio 2', 1, 2],
    ['Season 4 Episode 12', 4, 12],
    ['1x04', 1, 4],
  ])('%s → T%i E%i', (texto, temporada, episodio) => {
    expect(api.temporadaEEpisodioMax(texto)).toMatchObject({ temporada, episodio })
  })

  it.each(['', 'Salto no Escuro', 'T0 Ep.0', 'Duna: Parte Dois'])(
    '%s não tem números',
    (texto) => {
      expect(api.temporadaEEpisodioMax(texto)).toBeNull()
    },
  )
})


// ── A rede de acessibilidade ──────────────────────────────────────────────

describe('quando os data-testid somem', () => {
  it('o rótulo acessível entrega os três campos', () => {
    // Os `data-testid` são contrato de teste da HBO, não nosso. O dia em que
    // eles mudarem não pode ser o dia em que o Max volta a publicar o nome do
    // episódio como se fosse a série.
    montarRotuloAcessivel('Lanternas, Temporada 1 Episódio 2, Salto no Escuro')

    expect(lerMax(document, EM_WATCH)).toEqual({
      workTitle: 'Lanternas',
      episodeTitle: 'Salto no Escuro',
      seasonNumber: 1,
      episodeNumber: 2,
      pageId: ID,
    })
  })

  it('um rótulo sem os três pedaços não vira obra', () => {
    // Com dois pedaços não dá para separar obra de episódio, e chutar qual é
    // qual poria o nome do episódio na linha da série — o defeito de origem.
    montarRotuloAcessivel('Temporada 1 Episódio 2')

    expect(lerMax(document, EM_WATCH)).toEqual({ pageId: ID })
  })

  it('os data-testid vencem o rótulo', () => {
    montarPlayer('Lanternas', 'T1 Ep.2:', 'Salto no Escuro')
    montarRotuloAcessivel('Outra Coisa, Temporada 9 Episódio 9, Nada')

    expect(lerMax(document, EM_WATCH)?.workTitle).toBe('Lanternas')
  })
})


// ── Filmes, e o que não é reprodução ──────────────────────────────────────

describe('os outros casos', () => {
  it('um filme entrega só a obra', () => {
    montarPlayer('Duna: Parte Dois', null, null)

    expect(lerMax(document, EM_WATCH)).toEqual({
      workTitle: 'Duna: Parte Dois',
      episodeTitle: null,
      seasonNumber: null,
      episodeNumber: null,
      pageId: ID,
    })
  })

  it('sem nome nenhum, o id ainda é identidade de reprodução', () => {
    // No Max o id é por EPISÓDIO, então ele distingue "retomado" de "próximo"
    // sozinho. E devolvê-lo é melhor do que deixar "Trust Fall" virar série.
    expect(lerMax(document, EM_WATCH)).toEqual({ pageId: ID })
  })

  it.each(['/', '/browse', '/video/series/lanternas', '/search'])(
    '%s não é reprodução',
    (pathname) => {
      montarPlayer('Lanternas', 'T1 Ep.2:', 'Salto no Escuro')

      expect(lerMax(document, { pathname })).toBeNull()
    },
  )

  it('uma legenda sem marcador vira nome de episódio, e não vira número', () => {
    montarPlayer('Alguma Série', 'Especial', 'Um Episódio Qualquer')

    const lida = lerMax(document, EM_WATCH)
    expect(lida?.episodeTitle).toBe('Um Episódio Qualquer')
    expect(lida?.seasonNumber).toBeNull()
    expect(lida?.episodeNumber).toBeNull()
  })
})
