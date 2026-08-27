/**
 * Fase 10 — o adapter do Prime Video.
 *
 * O DOM montado aqui é o MEDIDO. Sonda no console em 26/08/2026, com
 * Batman: The Animated Series S3 E7 tocando:
 *
 *     div.atvwebplayersdk-title-text     "Batman: The Animated Series"
 *     span.atvwebplayersdk-episode-info  "S3 E7 Fire from Olympus"
 *
 * Sem Shadow DOM nenhum — ao contrário do Disney+ — e os dois elementos
 * CONTINUAM no DOM quando os controles somem: o que muda é só não terem área
 * na tela. Por isso este adapter não guarda lembrança de nada.
 *
 * ## As três armadilhas, todas medidas na mesma página
 *
 *     "S3 E7 Fire from Olympus"  .atvwebplayersdk-episode-info   ← o que toca
 *     "Resume S3 E7"             div.dv-node-dp-action-box       botão
 *     "Season 3"                 div._3R4jka                     seletor
 *
 * E o botão "Resume" estava VISÍVEL enquanto o do player estava escondido.
 * "Pegar o que está na tela" escolheria o errado — e gravaria no histórico o
 * episódio de um botão em vez do que a pessoa assiste.
 *
 * A terceira armadilha é estrutural: `.atvwebplayersdk-player-container`
 * aparece MAIS DE UMA VEZ na página de detalhe (há players de prévia), e os
 * elementos medidos NÃO estavam dentro do primeiro. Por isso a busca sobe a
 * partir do `<video>` que tem imagem.
 */

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { beforeEach, describe, expect, it } from 'vitest'


const FONTE = readFileSync(resolve(__dirname, 'prime.js'), 'utf8')

type Metadata = {
  workTitle?: string | null
  episodeTitle?: string | null
  seasonNumber?: number | null
  episodeNumber?: number | null
  pageId?: string | null
} | null

const api = new Function(
  `${FONTE}\nreturn { lerPrime, temporadaEEpisodioPrime }`,
)() as {
  lerPrime: (d: Document, l?: unknown) => Metadata
  temporadaEEpisodioPrime: (
    t: string,
  ) => { temporada: number; episodio: number; marcador: string } | null
}

const { lerPrime } = api

const EM_DETALHE = { pathname: '/detail/0HNVIQ8ZNGW9S1S37714VTRY55' }

/** Um `<video>` com o `videoWidth` que o jsdom não simula. */
function montarVideo(largura: number, dentro: HTMLElement = document.body) {
  const video = document.createElement('video')
  Object.defineProperty(video, 'videoWidth', { value: largura, configurable: true })
  dentro.appendChild(video)
  return video
}

/**
 * O player, com o aninhamento medido: os textos são IRMÃOS do vídeo, alguns
 * níveis acima, e não descendentes de um container escolhido a esmo.
 */
function montarPlayer(
  titulo: string | null,
  episodio: string | null,
  { comVideo = true } = {},
): HTMLElement {
  const container = document.createElement('div')
  container.className = 'atvwebplayersdk-player-container f1g7im4y'
  document.body.appendChild(container)

  const cofreDoVideo = document.createElement('div')
  container.appendChild(cofreDoVideo)
  if (comVideo) montarVideo(960, cofreDoVideo)

  if (titulo !== null) {
    const t = document.createElement('div')
    t.className = 'atvwebplayersdk-title-text f52hj7o f17cfskt'
    t.textContent = titulo
    container.appendChild(t)
  }
  if (episodio !== null) {
    const e = document.createElement('span')
    e.className = 'atvwebplayersdk-episode-info f6gi9c2'
    e.textContent = episodio
    container.appendChild(e)
  }
  return container
}

/** O botão "Resume S3 E7" da página de detalhe, que NÃO é o que toca. */
function montarBotaoResume(texto: string) {
  const caixa = document.createElement('div')
  caixa.className = 'dv-node-dp-action-box'
  const link = document.createElement('a')
  link.className = '_1jWggM BLmu_g'
  link.textContent = texto
  caixa.appendChild(link)
  document.body.appendChild(caixa)
}

/** O seletor de temporadas da página de detalhe. */
function montarSeletorDeTemporada(...temporadas: string[]) {
  const caixa = document.createElement('div')
  caixa.className = '_3R4jka'
  for (const t of temporadas) {
    const span = document.createElement('span')
    span.className = '_36qUej'
    span.textContent = t
    caixa.appendChild(span)
  }
  document.body.appendChild(caixa)
}

beforeEach(() => {
  document.body.innerHTML = ''
})


// ── O caso medido ─────────────────────────────────────────────────────────

describe('o que a página do Prime entrega', () => {
  it('lê obra, temporada, episódio e nome do episódio', () => {
    montarPlayer('Batman: The Animated Series', 'S3 E7 Fire from Olympus')

    expect(lerPrime(document, EM_DETALHE)).toEqual({
      workTitle: 'Batman: The Animated Series',
      episodeTitle: 'Fire from Olympus',
      seasonNumber: 3,
      episodeNumber: 7,
      pageId: null,
    })
  })

  it('lê com os controles escondidos, que é o estado normal', () => {
    // Medido: os elementos ficam no DOM sem área na tela. Diferente do
    // Disney+, que remove o overlay inteiro.
    const container = montarPlayer('Batman: The Animated Series', 'S3 E7 Fire from Olympus')
    container.style.display = 'none'

    expect(lerPrime(document, EM_DETALHE)?.episodeNumber).toBe(7)
  })

  it('NÃO manda pageId', () => {
    // A URL medida é `/detail/0HNVIQ8ZN...`, que identifica a SÉRIE: ela não
    // muda quando o episódio muda. Mandá-la faria dois episódios diferentes
    // parecerem a mesma reprodução, e o histórico não perceberia a troca.
    montarPlayer('Batman: The Animated Series', 'S3 E7 Fire from Olympus')

    expect(lerPrime(document, EM_DETALHE)?.pageId).toBeNull()
  })
})


// ── As armadilhas da página de detalhe ────────────────────────────────────

describe('o que NÃO é o episódio que está tocando', () => {
  it('ignora o botão "Resume", mesmo ele sendo o visível', () => {
    montarPlayer('Batman: The Animated Series', 'S3 E7 Fire from Olympus')
    montarBotaoResume('Resume S3 E12')

    const lida = lerPrime(document, EM_DETALHE)

    expect(lida?.episodeNumber).toBe(7)
    expect(lida?.episodeTitle).toBe('Fire from Olympus')
  })

  it('ignora o seletor de temporadas', () => {
    montarPlayer('Batman: The Animated Series', 'S3 E7 Fire from Olympus')
    montarSeletorDeTemporada('Season 1', 'Season 2', 'Season 4')

    expect(lerPrime(document, EM_DETALHE)?.seasonNumber).toBe(3)
  })

  it('escolhe o player DO vídeo que está tocando, e não o primeiro da página', () => {
    // Medido: `.atvwebplayersdk-player-container` aparece mais de uma vez, e
    // os elementos lidos NÃO estavam dentro do primeiro.
    montarPlayer('Uma Prévia Qualquer', 'S9 E9 Não É Isto', { comVideo: false })
    montarPlayer('Batman: The Animated Series', 'S3 E7 Fire from Olympus')

    const lida = lerPrime(document, EM_DETALHE)

    expect(lida?.workTitle).toBe('Batman: The Animated Series')
    expect(lida?.episodeNumber).toBe(7)
  })
})


// ── O guarda do vídeo ─────────────────────────────────────────────────────

describe('sem reprodução não há o que afirmar', () => {
  it('sem vídeo com imagem, não lê nada', () => {
    // A pessoa fechou o player e está navegando pelo catálogo. Os elementos
    // do SDK podem ficar para trás, e afirmar o último episódio lido seria
    // dizer que está tocando algo que não está.
    montarPlayer('Batman: The Animated Series', 'S3 E7 Fire from Olympus', {
      comVideo: false,
    })

    expect(lerPrime(document, EM_DETALHE)).toBeNull()
  })

  it('o vídeo parado de largura zero não conta', () => {
    // Medido: a página mantém um segundo `<video>` com `videoWidth` zero.
    const container = montarPlayer(
      'Batman: The Animated Series', 'S3 E7 Fire from Olympus', { comVideo: false },
    )
    montarVideo(0, container)

    expect(lerPrime(document, EM_DETALHE)).toBeNull()
  })

  it('uma prévia junto do conteúdo não cala o adapter', () => {
    // A primeira versão exigia EXATAMENTE um vídeo com imagem e devolvia nada
    // com dois — regra copiada do Disney+, onde ela tem motivo (o player usa um
    // segundo elemento para anúncio, com outra origem de TEMPO). Aqui este
    // adapter não declara tempo nenhum, e o vídeo responde uma pergunta só:
    // "há reprodução acontecendo?". Calar por causa de uma prévia era rigor
    // emprestado de um problema que o Prime não tem.
    const container = montarPlayer(
      'Batman: The Animated Series', 'S3 E7 Fire from Olympus',
    )
    montarVideo(640, container)

    expect(lerPrime(document, EM_DETALHE)?.episodeNumber).toBe(7)
  })

  it('página sem o SDK do player não vira leitura', () => {
    // A loja da Amazon, que atende no mesmo domínio que o adapter aceita.
    montarVideo(960)

    expect(lerPrime(document, { pathname: '/dp/B08XYZ' })).toBeNull()
  })
})


// ── Filmes e grafias novas ────────────────────────────────────────────────

describe('quando não há episódio', () => {
  it('um filme entrega só a obra', () => {
    montarPlayer('Duna: Parte Dois', null)

    expect(lerPrime(document, EM_DETALHE)).toEqual({
      workTitle: 'Duna: Parte Dois',
      episodeTitle: null,
      seasonNumber: null,
      episodeNumber: null,
      pageId: null,
    })
  })

  it('uma legenda sem S/E vira nome de episódio, e NÃO vira número', () => {
    montarPlayer('Alguma Série', 'Um Episódio Especial')

    const lida = lerPrime(document, EM_DETALHE)
    expect(lida?.episodeTitle).toBe('Um Episódio Especial')
    expect(lida?.seasonNumber).toBeNull()
    expect(lida?.episodeNumber).toBeNull()
  })

  it('cai para o documento inteiro se o aninhamento mudar', () => {
    // Rede de segurança: o dia em que a Amazon mexer na árvore não pode ser o
    // dia em que a metadata some. Só vale com UM título na página.
    const titulo = document.createElement('div')
    titulo.className = 'atvwebplayersdk-title-text'
    titulo.textContent = 'Batman: The Animated Series'
    const episodio = document.createElement('span')
    episodio.className = 'atvwebplayersdk-episode-info'
    episodio.textContent = 'S3 E7 Fire from Olympus'
    document.body.append(titulo, episodio)
    montarVideo(960)

    expect(lerPrime(document, EM_DETALHE)?.episodeNumber).toBe(7)
  })
})


// ── A separação de S e E, isolada ─────────────────────────────────────────

describe('temporada e episódio', () => {
  it.each([
    ['S3 E7 Fire from Olympus', 3, 7],
    ['S1 E4 Neil Armstrong', 1, 4],
    ['T2:E10 Alguma Coisa', 2, 10],
    ['1x04 M. Night Shaym', 1, 4],
  ])('%s → T%i E%i', (texto, temporada, episodio) => {
    expect(api.temporadaEEpisodioPrime(texto)).toMatchObject({ temporada, episodio })
  })

  it.each(['', 'Fire from Olympus', 'S0 E0 Nada', 'Duna: Parte Dois'])(
    '%s não tem números',
    (texto) => {
      expect(api.temporadaEEpisodioPrime(texto)).toBeNull()
    },
  )
})
