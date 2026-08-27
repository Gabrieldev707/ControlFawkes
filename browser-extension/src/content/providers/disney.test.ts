/**
 * Fase 10 — o adapter do Disney+.
 *
 * O DOM montado aqui é o MEDIDO, e não um inventado que seja conveniente de
 * testar. Sonda no console em 26/08/2026, com Gavião Arqueiro T1:E1 tocando:
 *
 *     «disney-web-player-ui» ▸ «main-app-controls-overlay» ▸ «title-bug»
 *        ▸ div.title-bug-area ▸ div.title-bug-container
 *          ▸ button.title-btn
 *               ├─ div.title-field      "Gavião Arqueiro"
 *               └─ div.subtitle-field   "T1:E1 Nunca Conheça seus Heróis"
 *
 * Três shadow roots aninhados até chegar no texto. Este aninhamento não é
 * enfeite do teste: era exatamente ele que fazia `document.querySelector`
 * voltar vazio numa página que tinha obra e episódio escritos na tela.
 *
 * E a distinção que mais importa está no `pivot-tray-overlay`, que também
 * carrega um "T1:E..." — o do episódio SEGUINTE, na fileira "A seguir". Ler o
 * errado gravaria no histórico o episódio que a pessoa ainda não assistiu, e
 * isso é pior do que não gravar nada, porque parece certo.
 *
 * O arquivo observado é um content script CLÁSSICO: sem `export`, porque
 * content script declarado no manifesto não é módulo. Ele é lido e avaliado
 * aqui do mesmo jeito que o Chrome o carrega. Mesma forma de `netflix.test.ts`.
 */

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { beforeEach, describe, expect, it } from 'vitest'


const FONTE = readFileSync(resolve(__dirname, 'disney.js'), 'utf8')

type Metadata = {
  workTitle?: string | null
  episodeTitle?: string | null
  seasonNumber?: number | null
  episodeNumber?: number | null
  pageId?: string | null
} | null

type Local = { pathname: string; hostname?: string }

/**
 * Tudo de uma vez, e não um `carregar` por função.
 *
 * A lembrança do adapter é uma variável de módulo, e cada avaliação da fonte
 * cria um fechamento novo. Carregar `lerDisney` e `esquecerLembrancaDoDisney`
 * em chamadas separadas daria duas lembranças diferentes, e o esquecimento não
 * alcançaria a leitura — o teste passaria dizendo o contrário do que acontece.
 */
const api = new Function(
  `${FONTE}\nreturn { lerDisney, esquecerLembrancaDoDisney, temporadaEEpisodioDisney }`,
)() as {
  lerDisney: (d: Document, l: Local) => Metadata
  esquecerLembrancaDoDisney: () => void
  temporadaEEpisodioDisney: (
    t: string,
  ) => { temporada: number; episodio: number; marcador: string } | null
}

const { lerDisney, esquecerLembrancaDoDisney } = api

const EM_PLAY = { pathname: '/pt-br/play/79955576-c891-414d-a87c-9b1b28567e29' }
const OUTRO_EPISODIO = { pathname: '/pt-br/play/aa112233-4444-5555-6666-777788889999' }

/**
 * Monta o player como o Disney+ o monta: três shadow roots até o texto.
 *
 * `titulo` ausente é o overlay FORA do DOM — que é o estado normal enquanto a
 * pessoa assiste sem mexer o mouse, medido após 12 segundos de ociosidade.
 */
function montarPlayer(
  titulo?: { obra: string; legenda?: string; semClasses?: boolean },
  aSeguir?: string,
) {
  const player = document.createElement('disney-web-player-ui')
  document.body.appendChild(player)
  const raizDoPlayer = player.attachShadow({ mode: 'open' })

  if (titulo !== undefined) {
    const overlay = document.createElement('main-app-controls-overlay')
    raizDoPlayer.appendChild(overlay)
    const raizDoOverlay = overlay.attachShadow({ mode: 'open' })

    const bug = document.createElement('title-bug')
    raizDoOverlay.appendChild(bug)
    const raizDoBug = bug.attachShadow({ mode: 'open' })

    const area = document.createElement('div')
    area.className = 'title-bug-area'
    const container = document.createElement('div')
    container.className = 'title-bug-container'
    const botao = document.createElement('button')
    botao.className = 'control-icon-btn title-btn'

    const obra = document.createElement('div')
    // `semClasses` cobre o dia em que o Disney+ renomear as classes: o adapter
    // tem de cair para a posição dos filhos em vez de ficar cego.
    obra.className = titulo.semClasses ? 'algo-novo' : ' title-field body-copy locale-h3 '
    obra.textContent = titulo.obra
    botao.appendChild(obra)

    if (titulo.legenda !== undefined) {
      const legenda = document.createElement('div')
      legenda.className = titulo.semClasses
        ? 'outra-coisa'
        : ' subtitle-field locale-body-headline '
      legenda.textContent = titulo.legenda
      botao.appendChild(legenda)
    }

    container.appendChild(botao)
    area.appendChild(container)
    raizDoBug.appendChild(area)
  }

  // A fileira "A seguir", que carrega o episódio SEGUINTE. Ela fica no DOM
  // junto com o título e é a armadilha central deste adapter.
  if (aSeguir !== undefined) {
    const bandeja = document.createElement('pivot-tray-overlay')
    raizDoPlayer.appendChild(bandeja)
    const raizDaBandeja = bandeja.attachShadow({ mode: 'open' })
    const span = document.createElement('span')
    span.className = 'episode-title locale-metadata'
    span.textContent = aSeguir
    raizDaBandeja.appendChild(span)
  }
}

beforeEach(() => {
  document.body.innerHTML = ''
  esquecerLembrancaDoDisney()
})


// ── O caso medido ─────────────────────────────────────────────────────────

describe('o que a página do Disney+ entrega', () => {
  it('lê obra, temporada, episódio e nome do episódio', () => {
    montarPlayer({ obra: 'Gavião Arqueiro', legenda: 'T1:E1 Nunca Conheça seus Heróis' })

    expect(lerDisney(document, EM_PLAY)).toMatchObject({
      workTitle: 'Gavião Arqueiro',
      episodeTitle: 'Nunca Conheça seus Heróis',
      seasonNumber: 1,
      episodeNumber: 1,
      pageId: '79955576-c891-414d-a87c-9b1b28567e29',
    })
  })

  it('não confunde o episódio atual com o da fileira "A seguir"', () => {
    // Os dois no DOM ao mesmo tempo, que é o estado real com os controles
    // abertos. O de baixo é o próximo episódio, e gravá-lo poria no histórico
    // algo que a pessoa não assistiu.
    montarPlayer(
      { obra: 'Gavião Arqueiro', legenda: 'T1:E1 Nunca Conheça seus Heróis' },
      'T1:E2 Esconde-Esconde',
    )

    const lida = lerDisney(document, EM_PLAY)

    expect(lida?.episodeNumber).toBe(1)
    expect(lida?.episodeTitle).toBe('Nunca Conheça seus Heróis')
  })

  it('atravessa os shadow roots', () => {
    // A prova de que a varredura é necessária: com `querySelector` comum, a
    // página inteira parece vazia.
    montarPlayer({ obra: 'Gavião Arqueiro', legenda: 'T1:E1 Nunca Conheça seus Heróis' })

    expect(document.querySelector('.title-btn')).toBeNull()
    expect(lerDisney(document, EM_PLAY)?.workTitle).toBe('Gavião Arqueiro')
  })
})


// ── A lembrança, que é o coração do adapter ───────────────────────────────

describe('o overlay que some', () => {
  it('continua respondendo depois de os controles saírem do DOM', () => {
    montarPlayer({ obra: 'Gavião Arqueiro', legenda: 'T1:E1 Nunca Conheça seus Heróis' })
    expect(lerDisney(document, EM_PLAY)?.workTitle).toBe('Gavião Arqueiro')

    // Doze segundos sem mouse: medido, o overlay inteiro sai do DOM.
    document.body.innerHTML = ''
    montarPlayer()

    const lida = lerDisney(document, EM_PLAY)
    expect(lida?.workTitle).toBe('Gavião Arqueiro')
    expect(lida?.episodeNumber).toBe(1)
  })

  it('esquece quando a reprodução muda, mesmo sem conseguir ler a nova', () => {
    montarPlayer({ obra: 'Gavião Arqueiro', legenda: 'T1:E1 Nunca Conheça seus Heróis' })
    lerDisney(document, EM_PLAY)

    // Episódio seguinte, e o overlay dele ainda não apareceu. Repetir o
    // anterior aqui seria afirmar o episódio errado — pior do que calar.
    document.body.innerHTML = ''
    montarPlayer()

    const lida = lerDisney(document, OUTRO_EPISODIO)
    expect(lida?.pageId).toBe('aa112233-4444-5555-6666-777788889999')
    expect(lida?.workTitle).toBeUndefined()
  })

  it('sem nunca ter lido, entrega só a identidade da reprodução', () => {
    montarPlayer()

    const lida = lerDisney(document, EM_PLAY)
    expect(lida?.pageId).toBe('79955576-c891-414d-a87c-9b1b28567e29')
    expect(lida?.workTitle).toBeUndefined()
  })
})


// ── O que não pode virar obra ─────────────────────────────────────────────

describe('fora da reprodução', () => {
  it.each([
    '/pt-br/home',
    '/pt-br/browse',
    '/pt-br/series/gaviao-arqueiro/3xpKzP0zXeUq',
    '/',
  ])('%s não é reprodução', (caminho) => {
    // A vitrine dessas telas toca trailer. É o mesmo defeito que fazia a
    // Netflix mandar "Home" como nome de obra.
    montarPlayer({ obra: 'Gavião Arqueiro' })

    expect(lerDisney(document, { pathname: caminho })).toBeNull()
  })

  it('sair da reprodução apaga a lembrança', () => {
    montarPlayer({ obra: 'Gavião Arqueiro', legenda: 'T1:E1 Nunca Conheça seus Heróis' })
    lerDisney(document, EM_PLAY)

    lerDisney(document, { pathname: '/pt-br/home' })

    document.body.innerHTML = ''
    montarPlayer()
    const lida = lerDisney(document, EM_PLAY)
    expect(lida?.pageId).toBe('79955576-c891-414d-a87c-9b1b28567e29')
    expect(lida?.workTitle).toBeUndefined()
  })
})


// ── Filmes e grafias novas ────────────────────────────────────────────────

describe('quando não há episódio', () => {
  it('um filme entrega só a obra', () => {
    montarPlayer({ obra: 'Duna: Parte Dois' })

    expect(lerDisney(document, EM_PLAY)).toMatchObject({
      workTitle: 'Duna: Parte Dois',
      episodeTitle: null,
      seasonNumber: null,
      episodeNumber: null,
      pageId: '79955576-c891-414d-a87c-9b1b28567e29',
    })
  })

  it('uma legenda sem T/E vira nome de episódio, e NÃO vira número', () => {
    // Um "T1 E1" chutado é pior do que número nenhum: a pessoa acredita nele.
    montarPlayer({ obra: 'Alguma Série', legenda: 'Um Episódio Especial' })

    const lida = lerDisney(document, EM_PLAY)
    expect(lida?.episodeTitle).toBe('Um Episódio Especial')
    expect(lida?.seasonNumber).toBeNull()
    expect(lida?.episodeNumber).toBeNull()
  })

  it('lê mesmo se as classes mudarem de nome', () => {
    // Um seletor único é uma bomba com relógio. O dia em que o Disney+
    // renomear `.title-field` não pode ser o dia em que a metadata some.
    montarPlayer({
      obra: 'Gavião Arqueiro',
      legenda: 'T1:E1 Nunca Conheça seus Heróis',
      semClasses: true,
    })

    const lida = lerDisney(document, EM_PLAY)
    expect(lida?.workTitle).toBe('Gavião Arqueiro')
    expect(lida?.episodeNumber).toBe(1)
  })
})


// ── A separação de T e E, isolada ─────────────────────────────────────────

describe('temporada e episódio', () => {
  it.each([
    ['T1:E1 Nunca Conheça seus Heróis', 1, 1],
    ['T2:E10 Alguma Coisa', 2, 10],
    ['S1 E4 Neil Armstrong', 1, 4],
    ['1x04 M. Night Shaym', 1, 4],
  ])('%s → T%i E%i', (texto, temporada, episodio) => {
    expect(api.temporadaEEpisodioDisney(texto)).toMatchObject({ temporada, episodio })
  })

  it.each(['', 'Nunca Conheça seus Heróis', 'T0:E0 Nada', 'Duna: Parte Dois'])(
    '%s não tem números',
    (texto) => {
      expect(api.temporadaEEpisodioDisney(texto)).toBeNull()
    },
  )
})


// ── A posição real, que o <video> do Disney+ não sabe ─────────────────────
//
// Medido no mesmo instante, com Gavião Arqueiro T1:E1 tocando:
//
//     slider "Linha do tempo"   now=146  max=3043   ("2:26 of 50:43")
//     video.currentTime         50.8
//     video.duration            Infinity
//     video.seekable            [0, 62]
//
// O `seekable` inteiro cabia em 62 segundos num episódio de cinquenta minutos:
// o `<video>` só conhece a janela DASH que está montando. A posição que o
// ControlFawkes mostrava para Disney+ nunca esteve certa.

/** Um `<video>` com `videoWidth` e `currentTime` que o jsdom não simula. */
function montarVideo(largura: number, tempo: number): HTMLVideoElement {
  const video = document.createElement('video')
  Object.defineProperty(video, 'videoWidth', { value: largura, configurable: true })
  Object.defineProperty(video, 'currentTime', { value: tempo, configurable: true, writable: true })
  document.body.appendChild(video)
  return video
}

/** A barra de progresso, dentro do shadow root em que ela realmente vive. */
function montarLinhaDoTempo(posicao: number, duracao: number, rotulo = 'Linha do tempo') {
  const barra = document.createElement('progress-bar')
  document.body.appendChild(barra)
  const raiz = barra.attachShadow({ mode: 'open' })
  const slider = document.createElement('div')
  slider.setAttribute('role', 'slider')
  slider.setAttribute('aria-label', rotulo)
  slider.setAttribute('aria-valuenow', String(posicao))
  slider.setAttribute('aria-valuemin', '0')
  slider.setAttribute('aria-valuemax', String(duracao))
  slider.className = ' progress-bar__seekable-range '
  raiz.appendChild(slider)
}

describe('a posição real', () => {
  it('vem do slider, e não do currentTime', () => {
    montarPlayer({ obra: 'Gavião Arqueiro', legenda: 'T1:E1 Nunca Conheça seus Heróis' })
    montarVideo(1280, 50.8)
    montarLinhaDoTempo(146, 3043)

    const lida = lerDisney(document, EM_PLAY) as Record<string, unknown>

    expect(lida.adapterPosition).toBe(146)
    expect(lida.adapterDuration).toBe(3043)
  })

  it('é projetada pelo delta quando o overlay some', () => {
    montarPlayer({ obra: 'Gavião Arqueiro', legenda: 'T1:E1 Nunca Conheça seus Heróis' })
    const video = montarVideo(1280, 50.8)
    montarLinhaDoTempo(146, 3043)
    lerDisney(document, EM_PLAY)

    // Doze segundos depois: o overlay saiu do DOM e o vídeo andou doze
    // segundos — exatamente o que foi medido (50.8 → 62.8).
    document.querySelector('progress-bar')?.remove()
    Object.defineProperty(video, 'currentTime', { value: 62.8, configurable: true })

    const lida = lerDisney(document, EM_PLAY) as Record<string, unknown>

    expect(lida.adapterPosition).toBeCloseTo(158, 1)
    expect(lida.adapterDuration).toBe(3043)
  })

  it('sem nunca ter visto o overlay, não afirma posição', () => {
    // O estado de quem abriu a aba e não mexeu o mouse. O backend sabe
    // desenhar um cartão sem posição; ele não sabe desconfiar de uma errada.
    montarPlayer()
    montarVideo(1280, 50.8)

    const lida = lerDisney(document, EM_PLAY) as Record<string, unknown>

    expect(lida.adapterPosition).toBeNull()
    expect(lida.adapterDuration).toBeNull()
  })

  it('com dois vídeos tocando, não ancora em nenhum', () => {
    // O player carrega `has-interstitials` e usa um segundo elemento para
    // anúncio. Ancorar no errado daria um deslocamento errado que continuaria
    // sendo aplicado depois.
    montarPlayer({ obra: 'Gavião Arqueiro' })
    montarVideo(1280, 50.8)
    montarVideo(640, 12.0)
    montarLinhaDoTempo(146, 3043)

    const lida = lerDisney(document, EM_PLAY) as Record<string, unknown>

    expect(lida.adapterPosition).toBeNull()
  })

  it('o vídeo trocar invalida a âncora', () => {
    montarPlayer({ obra: 'Gavião Arqueiro' })
    const primeiro = montarVideo(1280, 50.8)
    montarLinhaDoTempo(146, 3043)
    lerDisney(document, EM_PLAY)

    // Entrada ou saída de anúncio: outro elemento, outra origem de tempo.
    document.querySelector('progress-bar')?.remove()
    primeiro.remove()
    montarVideo(1280, 3.0)

    const lida = lerDisney(document, EM_PLAY) as Record<string, unknown>

    expect(lida.adapterPosition).toBeNull()
  })

  it('um seek para trás invalida a âncora', () => {
    montarPlayer({ obra: 'Gavião Arqueiro' })
    const video = montarVideo(1280, 500.0)
    montarLinhaDoTempo(600, 3043)
    lerDisney(document, EM_PLAY)

    document.querySelector('progress-bar')?.remove()
    Object.defineProperty(video, 'currentTime', { value: 20.0, configurable: true })

    const lida = lerDisney(document, EM_PLAY) as Record<string, unknown>

    expect(lida.adapterPosition).toBeNull()
  })

  it('a projeção não passa do fim do episódio', () => {
    montarPlayer({ obra: 'Gavião Arqueiro' })
    const video = montarVideo(1280, 10.0)
    montarLinhaDoTempo(3000, 3043)
    lerDisney(document, EM_PLAY)

    // Âncora velha: o delta levaria a 3110, além da duração.
    document.querySelector('progress-bar')?.remove()
    Object.defineProperty(video, 'currentTime', { value: 120.0, configurable: true })

    const lida = lerDisney(document, EM_PLAY) as Record<string, unknown>

    expect(lida.adapterPosition).toBe(3043)
  })

  it('o rótulo do slider é traduzido, e por isso não é ele quem casa', () => {
    // `aria-label` vem no idioma da conta — "Linha do tempo" aqui, "Timeline"
    // noutra máquina. Prender o adapter ao rótulo o quebraria para quem não
    // usa português.
    montarPlayer({ obra: 'Gavião Arqueiro' })
    montarVideo(1280, 50.8)
    montarLinhaDoTempo(146, 3043, 'Timeline')

    const lida = lerDisney(document, EM_PLAY) as Record<string, unknown>

    expect(lida.adapterPosition).toBe(146)
  })

  it('sair da reprodução apaga a âncora', () => {
    montarPlayer({ obra: 'Gavião Arqueiro' })
    const video = montarVideo(1280, 50.8)
    montarLinhaDoTempo(146, 3043)
    lerDisney(document, EM_PLAY)

    lerDisney(document, { pathname: '/pt-br/home' })

    document.querySelector('progress-bar')?.remove()
    Object.defineProperty(video, 'currentTime', { value: 62.8, configurable: true })
    const lida = lerDisney(document, EM_PLAY) as Record<string, unknown>

    expect(lida.adapterPosition).toBeNull()
  })
})


// ── Acordar os controles sozinho ──────────────────────────────────────────
//
// Relatado em 26/08/2026, com WandaVision tocando: o cartão dizia "ao vivo" e
// mostrava "2:34". Sem âncora, a duração fica ausente — o `<video>` publica
// `Infinity`, recusado na validação — e a posição cai para o `currentTime` do
// elemento, que é a janela DASH e não o episódio.
//
// A causa era do desenho: o adapter esperava que alguém mexesse o mouse. E
// quem assiste pelo celular não mexe o mouse do computador nunca.

describe('quando ninguém mexe o mouse', () => {
  function comOuvinteDeMouse() {
    const visto: string[] = []
    const alvo = montarVideo(1280, 50.8)
    for (const tipo of ['mousemove', 'pointermove']) {
      alvo.addEventListener(tipo, () => visto.push(tipo))
    }
    return visto
  }

  it('pede os controles de volta quando não há âncora', () => {
    montarPlayer()
    const visto = comOuvinteDeMouse()

    lerDisney(document, EM_PLAY)

    expect(visto).toContain('mousemove')
  })

  it('PARA de pedir assim que consegue a leitura', () => {
    // O overlay aparecendo na tela é o custo. Uma vez, para conseguir a única
    // leitura que falta, é aceitável; a cada batimento seria a interface
    // piscando sozinha em cima do filme.
    montarPlayer({ obra: 'WandaVision', legenda: 'T1:E1 Gravado ao Vivo' })
    const visto = comOuvinteDeMouse()
    montarLinhaDoTempo(154, 1810)

    lerDisney(document, EM_PLAY)

    expect(visto).toEqual([])
  })

  it('não pede de novo a cada leitura', () => {
    montarPlayer()
    const visto = comOuvinteDeMouse()

    for (let i = 0; i < 10; i += 1) lerDisney(document, EM_PLAY)

    // Uma rajada de leituras não vira uma rajada de overlays.
    expect(visto.filter((t) => t === 'mousemove').length).toBe(1)
  })

  it('com a âncora conseguida, o cartão deixa de dizer "ao vivo"', () => {
    // É o sintoma exato: sem duração, a tela desenha "ao vivo".
    montarPlayer({ obra: 'WandaVision', legenda: 'T1:E1 Gravado ao Vivo' })
    montarVideo(1280, 50.8)
    montarLinhaDoTempo(154, 1810)

    const lida = lerDisney(document, EM_PLAY) as Record<string, unknown>

    expect(lida.adapterDuration).toBe(1810)
    expect(lida.adapterPosition).toBe(154)
  })
})
