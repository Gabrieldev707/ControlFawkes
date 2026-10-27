/**
 * A aba continua falando — as três defesas contra o silêncio.
 *
 * O defeito que este arquivo protege foi medido no `host.log` em 30/08/2026,
 * nos dois modos:
 *
 *   aba em segundo plano   o Chrome estrangula `setInterval`. O batimento de
 *                          dez segundos passou 840 segundos sem sair, e depois
 *                          ficou em exatos 60s.
 *   content script órfão   vinte e oito minutos de silêncio com o filme
 *                          tocando e a aba ATIVA. O que devolveu a ponte foi o
 *                          usuário recarregando a extensão na mão.
 *
 * Como os outros testes da extensão, o arquivo observado é avaliado do mesmo
 * jeito que o Chrome o carrega: `video-observer.js` primeiro, `index.js`
 * depois, na ordem do manifesto — o teste exercita o arquivo real.
 */

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'


const OBSERVADOR = readFileSync(resolve(__dirname, 'video-observer.js'), 'utf8')
const INDEX = readFileSync(resolve(__dirname, 'index.js'), 'utf8')

type Ouvinte = (
  mensagem: unknown,
  remetente: unknown,
  responder: (resposta: unknown) => void,
) => boolean

type Chrome = {
  runtime: {
    id: string | undefined
    sendMessage: ReturnType<typeof vi.fn>
    onMessage: { addListener: (o: Ouvinte) => void }
  }
}

/** Os ouvintes que a cópia atual registrou em `chrome.runtime.onMessage`. */
let ouvintes: Ouvinte[] = []

function montarChrome(): Chrome {
  return {
    runtime: {
      id: 'fawkes-teste',
      sendMessage: vi.fn().mockResolvedValue({ ok: true }),
      onMessage: { addListener: (o: Ouvinte) => { ouvintes.push(o) } },
    },
  }
}

/**
 * Carrega uma cópia do content script, como uma injeção do Chrome.
 *
 * Chamar duas vezes É o caso sob teste: é o que a reinjeção da vigia faz, e as
 * duas cópias compartilham o mesmo `globalThis` — o mundo isolado é um só por
 * extensão, e é dele que depende a guarda de idempotência.
 */
/**
 * Os globais do navegador que o content script usa e que o realm do
 * `new Function` do vitest NÃO tem.
 *
 * O corpo de um `new Function` é avaliado no escopo global do realm, e o do
 * vitest não carrega os globais do jsdom — nem `document`, nem `location`, nem
 * os temporizadores. `netflix.test.ts` não tropeça nisso porque `netflix.js`
 * recebe `documento`/`local` por parâmetro; `index.js` lê os globais de
 * verdade, como content script de verdade faz.
 *
 * Passar por parâmetro em vez de escrever em `globalThis` é de propósito: o
 * `globalThis` continua sendo o mesmo objeto para as duas cópias injetadas, e
 * é dele que depende a guarda de idempotência sob teste. Poluí-lo aqui
 * misturaria o andaime com o que se quer medir.
 */
const GLOBAIS = {
  document: () => globalThis.document,
  location: () => ({
    hostname: 'www.netflix.com',
    pathname: '/watch/81234567',
    href: '',
  }),
  addEventListener: () => globalThis.addEventListener.bind(globalThis),
  setInterval: () => globalThis.setInterval,
  clearInterval: () => globalThis.clearInterval,
  MutationObserver: () => globalThis.MutationObserver,
  getComputedStyle: () => globalThis.getComputedStyle.bind(globalThis),
} as const

function injetar(): void {
  const nomes = Object.keys(GLOBAIS)
  const valores = Object.values(GLOBAIS).map((obter) => obter())
  new Function('chrome', ...nomes, `${OBSERVADOR}\n${INDEX}`)(
    globalThis.chrome,
    ...valores,
  )
}

/**
 * Um `<video>` na página, e ele não é decoração.
 *
 * `baterAgora` desiste quando não há elemento — "sem elemento não há o que
 * sincronizar" —, então sem isto o batimento nunca sai e todo teste sobre o
 * relógio passaria por vacuidade, medindo zero contra zero. `duration`,
 * `paused` e companhia são getters somente-leitura no jsdom, e por isso vão
 * definidos no próprio elemento, como em `video-observer.test.ts`.
 */
function plantarVideo(): void {
  const video = document.createElement('video')
  for (const [nome, valor] of Object.entries({
    duration: 100,
    currentTime: 10,
    paused: false,
    ended: false,
    playbackRate: 1,
    muted: false,
    clientWidth: 640,
    clientHeight: 360,
  })) {
    Object.defineProperty(video, nome, { value: valor, configurable: true, writable: true })
  }
  document.body.append(video)
}

beforeEach(() => {
  vi.useFakeTimers()
  ouvintes = []
  delete (globalThis as { __fawkesDesmontar?: unknown }).__fawkesDesmontar
  ;(globalThis as { chrome?: Chrome }).chrome = montarChrome()
  document.body.innerHTML = ''
  plantarVideo()
})

afterEach(() => {
  // CHAMAR e não só esquecer: apagar a referência deixaria a cópia do teste
  // anterior viva, com o relógio girando e o observador pendurado no `<video>`
  // do teste seguinte. É literalmente o defeito que este arquivo testa, e ele
  // apareceu aqui primeiro — como vazamento entre casos.
  const desmontar = (globalThis as { __fawkesDesmontar?: () => void }).__fawkesDesmontar
  if (typeof desmontar === 'function') desmontar()
  delete (globalThis as { __fawkesDesmontar?: unknown }).__fawkesDesmontar
  vi.useRealTimers()
})


describe('a guarda de idempotência', () => {
  it('publica o desmontador para a próxima cópia encontrar', () => {
    injetar()

    expect(typeof (globalThis as { __fawkesDesmontar?: unknown }).__fawkesDesmontar)
      .toBe('function')
  })

  it('a cópia nova desmonta a velha antes de subir', () => {
    injetar()
    const velho = (globalThis as { __fawkesDesmontar?: unknown }).__fawkesDesmontar

    injetar()

    // O desmontador publicado é o da cópia NOVA: se fosse o mesmo objeto, a
    // terceira injeção desmontaria a primeira em vez da segunda, e a segunda
    // ficaria girando para sempre — que é a camada empilhada que este teste
    // existe para não deixar acontecer.
    expect((globalThis as { __fawkesDesmontar?: unknown }).__fawkesDesmontar)
      .not.toBe(velho)
  })

  it('uma cópia velha que estoura ao desmontar não impede a nova de subir', () => {
    // Sem script na aba o silêncio é total, que é pior do que a sobra.
    ;(globalThis as { __fawkesDesmontar?: unknown }).__fawkesDesmontar = () => {
      throw new Error('cópia velha quebrada')
    }

    expect(() => injetar()).not.toThrow()
  })
})


describe('injetar numa aba que JÁ está tocando', () => {
  it('não estoura na construção do observador', () => {
    // O caso que a vigia cria o tempo todo, e que `reinjetarNasAbasAbertas` já
    // criava a cada reload da extensão.
    //
    // `criarObservador` termina chamando `reconferir()` de forma SÍNCRONA. Com
    // um `<video>` já na página ele prende o elemento e dispara
    // `aoMudar('bound')` ainda dentro da própria construção — e esse callback
    // lê `observador`. Enquanto a variável era `const`, isso caía na zona morta
    // temporal e estourava `ReferenceError`, matando o content script inteiro:
    // sem relógio, sem vigia de metadata, sem observador. A aba ficava muda e
    // nada acusava.
    expect(document.querySelector('video')).not.toBeNull()

    expect(() => injetar()).not.toThrow()
  })

  it('e o relógio da cópia nova bate', async () => {
    // Não basta não estourar: o que se quer é a ponte VOLTANDO a falar, que é
    // a razão de a vigia reinjetar.
    injetar()
    const chrome = (globalThis as unknown as { chrome: Chrome }).chrome

    await vi.advanceTimersByTimeAsync(11_000)

    expect(chrome.runtime.sendMessage.mock.calls.length).toBeGreaterThan(0)
  })
})


describe('o contexto invalidado', () => {
  it('para o relógio em vez de girar em falso para sempre', async () => {
    injetar()
    const chrome = (globalThis as unknown as { chrome: Chrome }).chrome

    // A extensão foi recarregada: este content script virou órfão e nenhum
    // `chrome.*` dele volta a funcionar. `runtime.id` é o teste certo — ele
    // fica `undefined` exatamente nesse caso.
    chrome.runtime.sendMessage.mockRejectedValue(new Error('Extension context invalidated'))
    chrome.runtime.id = undefined

    await vi.advanceTimersByTimeAsync(11_000)
    const tentativas = chrome.runtime.sendMessage.mock.calls.length
    // Sem isto o teste passaria medindo zero contra zero.
    expect(tentativas).toBeGreaterThan(0)

    // Muito tempo depois: uma cópia desmontada não tenta de novo.
    await vi.advanceTimersByTimeAsync(120_000)

    expect(chrome.runtime.sendMessage.mock.calls.length).toBe(tentativas)
  })

  it('worker apenas dormindo NÃO desmonta — ele volta na próxima mensagem', async () => {
    injetar()
    const chrome = (globalThis as unknown as { chrome: Chrome }).chrome

    // Falha passageira, com o contexto vivo: `runtime.id` continua lá.
    chrome.runtime.sendMessage.mockRejectedValue(
      new Error('Could not establish connection'),
    )

    await vi.advanceTimersByTimeAsync(11_000)
    const tentativas = chrome.runtime.sendMessage.mock.calls.length
    expect(tentativas).toBeGreaterThan(0)

    await vi.advanceTimersByTimeAsync(60_000)

    expect(chrome.runtime.sendMessage.mock.calls.length).toBeGreaterThan(tentativas)
  })
})


describe('o cutucão da vigia', () => {
  it('responde que está vivo', () => {
    injetar()

    const respostas: unknown[] = []
    for (const ouvinte of ouvintes) {
      ouvinte({ messageType: 'CUTUCAO' }, {}, (r) => { respostas.push(r) })
    }

    // É a resposta que distingue a aba viva da órfã: a órfã não responde, e é
    // assim que a vigia sabe que precisa reinjetar aquela aba.
    expect(respostas).toContainEqual({ ok: true })
  })

  it('não se confunde com um comando', () => {
    injetar()

    const respostas: unknown[] = []
    for (const ouvinte of ouvintes) {
      ouvinte({ messageType: 'OUTRA_COISA' }, {}, (r) => { respostas.push(r) })
    }

    expect(respostas).toEqual([])
  })
})
