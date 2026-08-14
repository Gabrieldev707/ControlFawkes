/**
 * Fase 5 — o observador, e o defeito que ele existe para não ter.
 *
 * O arquivo observado é um content script CLÁSSICO: sem `export`, porque
 * content script declarado no manifesto não é módulo. Então ele é lido e
 * avaliado aqui do mesmo jeito que o Chrome o carrega — o teste exercita o
 * arquivo real, não uma cópia adaptada.
 */

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { beforeEach, describe, expect, it, vi } from 'vitest'


const FONTE = readFileSync(
  resolve(__dirname, 'video-observer.js'),
  'utf8',
)

type Leitura = {
  playbackState: string
  currentTime: number | null
  duration: number | null
  playbackRate: number | null
  muted: boolean
}

type Observador = {
  ler: () => Leitura | null
  parar: () => void
}

function carregar(): (aoMudar: (t: string, l: Leitura | null) => void) => Observador {
  // `criarObservador` é declarado no topo do escopo do arquivo; devolvê-lo é a
  // única forma de alcançá-lo sem `export`.
  return new Function(`${FONTE}\nreturn criarObservador`)() as never
}

/**
 * Um `<video>` controlável. `duration`, `paused` e `ended` são getters
 * somente-leitura no jsdom, então o teste os define no próprio elemento — o
 * que se quer exercitar é a nossa lógica, não a implementação de mídia do
 * jsdom.
 */
function criarVideo(valores: Partial<{
  duration: number
  currentTime: number
  paused: boolean
  ended: boolean
  playbackRate: number
  muted: boolean
  largura: number
  altura: number
}> = {}) {
  const video = document.createElement('video')
  const definir = (nome: string, valor: unknown) => {
    Object.defineProperty(video, nome, { value: valor, configurable: true, writable: true })
  }
  definir('duration', valores.duration ?? 100)
  definir('currentTime', valores.currentTime ?? 0)
  definir('paused', valores.paused ?? true)
  definir('ended', valores.ended ?? false)
  definir('playbackRate', valores.playbackRate ?? 1)
  definir('muted', valores.muted ?? false)
  definir('clientWidth', valores.largura ?? 640)
  definir('clientHeight', valores.altura ?? 360)
  return video
}

/** Deixa o MutationObserver e a reconferida periódica rodarem. */
async function assentar() {
  await new Promise((ok) => setTimeout(ok, 0))
}


describe('descoberta', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  it('escolhe o maior elemento, não o primeiro do documento', async () => {
    // Páginas de serviço têm `<video>` de trailer e de anúncio junto com o
    // player. O primeiro na ordem do DOM costuma ser o errado.
    const trailer = criarVideo({ largura: 200, altura: 120, currentTime: 5 })
    const player = criarVideo({ largura: 1280, altura: 720, currentTime: 900 })
    document.body.append(trailer, player)

    const observador = carregar()(() => {})
    await assentar()

    expect(observador.ler()?.currentTime).toBe(900)
    observador.parar()
  })

  it('acha o elemento dentro de shadow root aberto', async () => {
    const hospedeiro = document.createElement('div')
    document.body.append(hospedeiro)
    const sombra = hospedeiro.attachShadow({ mode: 'open' })
    sombra.append(criarVideo({ currentTime: 42 }))

    const observador = carregar()(() => {})
    await assentar()

    expect(observador.ler()?.currentTime).toBe(42)
    observador.parar()
  })

  it('sem elemento nenhum, não inventa leitura', async () => {
    const observador = carregar()(() => {})
    await assentar()

    expect(observador.ler()).toBeNull()
    observador.parar()
  })
})


describe('troca de elemento', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  it('não guarda referência eterna ao primeiro <video>', async () => {
    // O defeito que este teste existe para impedir. Netflix, Max, Disney+ e
    // Prime Video usam MSE e TROCAM o elemento em mudança de qualidade e em
    // troca de episódio. Quem guardou o primeiro segue lendo `currentTime` de
    // um objeto fora do documento — um número plausível, congelado, sem erro
    // nenhum aparecer.
    const primeiro = criarVideo({ currentTime: 10 })
    document.body.append(primeiro)

    const observador = carregar()(() => {})
    await assentar()
    expect(observador.ler()?.currentTime).toBe(10)

    primeiro.remove()
    document.body.append(criarVideo({ currentTime: 999 }))
    await assentar()

    expect(observador.ler()?.currentTime).toBe(999)
    observador.parar()
  })

  it('avisa quando o elemento sai do documento', async () => {
    const video = criarVideo()
    document.body.append(video)
    const eventos: string[] = []

    const observador = carregar()((tipo) => { eventos.push(tipo) })
    await assentar()
    video.remove()
    await assentar()

    expect(eventos).toContain('detached')
    observador.parar()
  })

  it('sem elemento no documento, a leitura volta a ser nula', async () => {
    const video = criarVideo()
    document.body.append(video)

    const observador = carregar()(() => {})
    await assentar()
    video.remove()
    await assentar()

    expect(observador.ler()).toBeNull()
    observador.parar()
  })
})


describe('duração', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  it.each([
    ['NaN, antes de loadedmetadata', Number.NaN],
    ['Infinity, transmissão ao vivo', Number.POSITIVE_INFINITY],
    ['zero', 0],
  ])('%s não é uma duração', async (_caso, valor) => {
    document.body.append(criarVideo({ duration: valor }))

    const observador = carregar()(() => {})
    await assentar()

    expect(observador.ler()?.duration).toBeNull()
    observador.parar()
  })

  it('a duração que chega depois é reportada', async () => {
    // `durationchange` é o evento em que ela aparece: o elemento nasce com
    // `NaN` e só sabe o tamanho quando a metadata carrega.
    const video = criarVideo({ duration: Number.NaN })
    document.body.append(video)

    const observador = carregar()(() => {})
    await assentar()
    expect(observador.ler()?.duration).toBeNull()

    Object.defineProperty(video, 'duration', { value: 2820, configurable: true })

    expect(observador.ler()?.duration).toBe(2820)
    observador.parar()
  })
})


describe('estado', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  it.each([
    [{ paused: true, ended: false }, 'paused'],
    [{ paused: false, ended: false }, 'playing'],
    // "Acabou" e "pausado" são coisas diferentes para o histórico: um conta
    // como visto até o fim, o outro entra em "continuar assistindo".
    [{ paused: true, ended: true }, 'ended'],
  ])('%o vira %s', async (valores, esperado) => {
    document.body.append(criarVideo(valores))

    const observador = carregar()(() => {})
    await assentar()

    expect(observador.ler()?.playbackState).toBe(esperado)
    observador.parar()
  })

  it('os eventos do elemento chegam a quem observa', async () => {
    const video = criarVideo()
    document.body.append(video)
    const eventos: string[] = []

    const observador = carregar()((tipo) => { eventos.push(tipo) })
    await assentar()
    video.dispatchEvent(new Event('play'))
    video.dispatchEvent(new Event('seeked'))

    expect(eventos).toContain('play')
    expect(eventos).toContain('seeked')
    observador.parar()
  })

  it('parar desliga tudo e não deixa observador duplicado', async () => {
    const video = criarVideo()
    document.body.append(video)
    const aoMudar = vi.fn()

    const observador = carregar()(aoMudar)
    await assentar()
    observador.parar()
    aoMudar.mockClear()

    video.dispatchEvent(new Event('play'))

    expect(aoMudar).not.toHaveBeenCalled()
  })
})
