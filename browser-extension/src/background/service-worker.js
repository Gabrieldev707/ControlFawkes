/**
 * O service worker — relay entre as abas e o native host, e mais nada.
 *
 * A regra que manda aqui é do Master Loop, critério de implementação incorreta
 * nº 4: **o Service Worker não pode ser responsável pelo relógio.** No MV3 ele
 * morre por inatividade, e um timer aqui simplesmente para de existir sem
 * avisar. Quem conta o tempo é o content script, que vive enquanto a aba viver.
 *
 * A outra regra, do mesmo lugar: keep-alive é otimização, não requisito de
 * correção. Esta implementação assume que o worker PODE morrer a qualquer
 * momento e reconecta quando volta. O `diario` fica em `chrome.storage` porque
 * memória de worker morto não é memória.
 *
 * O que este arquivo NÃO faz: observar `<video>`, ler metadata, decidir sessão
 * ativa, contar tempo. Nada disso sobrevive ao worker morrer.
 */

import { CicloDeVida, envelope, envelopeValido } from '../messaging/messages.js'

const HOST = 'com.controlfawkes.bridge'

/** Cem entradas bastam para ver um padrão e não seguram memória à toa. */
const LIMITE_DO_DIARIO = 100

let porta = null

/**
 * Qual janela do Chrome está em foco. Fase 14.
 *
 * Por EVENTO e não por consulta: `chrome.windows.get` é assíncrono, e o
 * caminho da mensagem é síncrono — pendurar uma consulta ali atrasaria toda
 * mensagem de toda aba para responder algo que muda raramente.
 *
 * `WINDOW_ID_NONE` é o Chrome inteiro perdendo o foco, e é um dado, não um
 * erro: é exatamente o caso "janela não focada" que a Fase 14 quer medir.
 */
let janelaEmFoco = null

chrome.windows?.onFocusChanged?.addListener((windowId) => {
  janelaEmFoco = windowId === chrome.windows.WINDOW_ID_NONE ? null : windowId
})

// O foco atual no start do worker: sem isto, toda mensagem até o primeiro
// `onFocusChanged` diria "nenhuma janela focada", que é falso.
try {
  chrome.windows?.getLastFocused?.({}, (janela) => {
    if (!chrome.runtime.lastError && janela?.focused) janelaEmFoco = janela.id
  })
} catch {
  // Sem a API de janelas, o campo fica `null` — ausente, não errado.
}

async function registrar(evento, detalhe) {
  const linha = { evento, detalhe: detalhe ?? null, em: new Date().toISOString() }
  console.log('[fawkes-bridge]', evento, detalhe ?? '')
  try {
    const { diario = [] } = await chrome.storage.local.get('diario')
    diario.push(linha)
    await chrome.storage.local.set({ diario: diario.slice(-LIMITE_DO_DIARIO) })
  } catch {
    // Storage indisponível não pode derrubar a ponte: o diário é diagnóstico.
  }
}

// Avaliação do módulo É o start do worker. Registrar aqui, e não num
// `onInstalled`, é o que mede os reinícios reais — que é o dado que a Fase 4
// existe para coletar.
void registrar(CicloDeVida.WORKER_STARTED, { motivo: 'avaliação de módulo' })

function conectar() {
  if (porta !== null) return porta
  try {
    porta = chrome.runtime.connectNative(HOST)
  } catch (erro) {
    void registrar(CicloDeVida.TRANSPORT_DISCONNECTED, { erro: String(erro) })
    return null
  }
  void registrar(CicloDeVida.TRANSPORT_CONNECTED, { host: HOST })

  porta.onMessage.addListener((mensagem) => {
    void registrar('HOST_MESSAGE', { messageType: mensagem?.messageType })
    if (mensagem?.messageType === 'COMANDO') void entregarComando(mensagem.payload)
  })

  porta.onDisconnect.addListener(() => {
    // `lastError` é onde o Chrome conta o motivo REAL — host não encontrado,
    // ID fora do allowed_origins, host morreu. Sem ler isto, a falha mais
    // comum do Native Messaging aparece como silêncio absoluto.
    const motivo = chrome.runtime.lastError?.message ?? 'desconhecido'
    void registrar(CicloDeVida.TRANSPORT_DISCONNECTED, { motivo })
    porta = null
  })

  return porta
}

function enviarAoHost(mensagem) {
  const aberta = conectar()
  if (aberta === null) return false
  try {
    aberta.postMessage(mensagem)
    return true
  } catch (erro) {
    // A porta pode ter morrido entre o `conectar` e o `postMessage`.
    void registrar(CicloDeVida.TRANSPORT_DISCONNECTED, { erro: String(erro) })
    porta = null
    return false
  }
}

/**
 * Tudo que vem de uma aba passa por aqui.
 *
 * O `sender` é a única fonte confiável de `tabId`/`windowId`: se a aba os
 * mandasse no payload, uma página poderia mentir sobre qual aba ela é.
 */
chrome.runtime.onMessage.addListener((mensagem, sender, responder) => {
  if (!envelopeValido(mensagem)) {
    void registrar('MENSAGEM_INVALIDA', { de: sender.tab?.id ?? null })
    responder({ ok: false, code: 'INVALID_ENVELOPE' })
    return false
  }

  // Fase 14 — telemetria de aba. Tudo daqui sai do `sender`, que é o Chrome
  // falando, e NÃO do payload: se a aba declarasse isto, uma página poderia
  // dizer que está ativa e audível para ganhar a disputa da Fase 15.
  //
  // `audible` é a novidade que mais vale: é por ABA, enquanto a Core Audio do
  // ControlFawkes só sabe responder por PROCESSO — e o Chrome agrupa todas as
  // abas num processo só. É a limitação que `audio_activity.py` documenta como
  // herdada, e este campo é o que a desfaz.
  const aba = sender.tab ?? null
  const enriquecida = {
    ...mensagem,
    payload: {
      ...(mensagem.payload ?? {}),
      tabId: aba?.id ?? null,
      windowId: aba?.windowId ?? null,
      active: aba?.active ?? null,
      audible: aba?.audible ?? null,
      tabMuted: aba?.mutedInfo?.muted ?? null,
      windowFocused: janelaEmFoco === null || aba?.windowId === undefined
        ? null
        : aba.windowId === janelaEmFoco,
    },
  }

  // Só o TIPO e a aba. O payload traz `href`, e registrá-lo transformaria o
  // diário de diagnóstico num histórico de navegação.
  void registrar('DA_ABA', {
    messageType: mensagem.messageType,
    tabId: sender.tab?.id ?? null,
  })

  // Esta aba acabou de falar. É o único dado de que a vigia precisa, e ele
  // entra aqui porque aqui passa TODA mensagem de toda aba — inclusive as que
  // não são batimento, que também provam que há script vivo do outro lado.
  void anotarQueFalou(sender.tab?.id ?? null)

  responder({ ok: enviarAoHost(enriquecida) })
  return false
})

/**
 * Entrega um comando à aba certa e devolve o resultado ao host. Fase 16.
 *
 * O worker é o ÚNICO lado que sabe endereçar uma aba: `chrome.tabs.sendMessage`
 * não existe dentro da página. Por isso o comando desce por aqui mesmo o
 * worker não podendo guardar estado — ele não guarda nada; só encaminha.
 *
 * O `tabId` vem do ControlFawkes, escolhido pelo árbitro da Fase 15. Aqui não
 * se escolhe aba nenhuma: mandar para "a aba ativa" desfaria a decisão que foi
 * tomada com os dados da Fase 14 e recriaria o defeito da barra de espaço.
 *
 * Toda falha vira um resultado com motivo, nunca silêncio. Quem apertou o botão
 * está olhando para a tela, e o ControlFawkes precisa saber que por aqui não
 * deu para cair no plano B — a tecla — em vez de ficar esperando.
 */
async function entregarComando(payload) {
  const responder = (ok, detalhe) => enviarAoHost({
    protocolVersion: 1,
    messageType: 'RESULTADO',
    timestamp: Date.now(),
    payload: { id: payload?.id, ok, detalhe },
  })

  if (payload === null || typeof payload !== 'object' || typeof payload.id !== 'string') {
    void registrar('COMANDO_INVALIDO')
    return
  }
  if (typeof payload.tabId !== 'number') {
    responder(false, 'sem tabId')
    return
  }
  try {
    const resposta = await chrome.tabs.sendMessage(payload.tabId, {
      messageType: 'COMANDO',
      payload,
    })
    responder(resposta?.ok === true, resposta?.detalhe ?? null)
  } catch (erro) {
    // Aba fechada, content script órfão depois de recarregar a extensão,
    // página que não aceita injeção. São todos o mesmo caso para quem espera:
    // por aqui não deu.
    responder(false, String(erro))
  }
}

/**
 * Reinjeta os content scripts nas abas que ja estavam abertas.
 *
 * Recarregar a extensao troca o service worker na hora e NAO troca os content
 * scripts das abas abertas: eles ficam orfaos — vivos na pagina, com as APIs
 * `chrome.*` mortas — ate alguem dar F5. O sintoma e sempre o mesmo e sempre
 * enganoso: o worker aparece atualizado nos logs, o dado novo nunca chega, e
 * nada acusa.
 *
 * Medido em 26/08/2026: `active` e `audible` chegavam (worker novo) e
 * `documentTitle` nao (content script velho), na mesma mensagem. Foram varias
 * rodadas de depuracao perdidas nisso.
 *
 * A ordem dos arquivos e a MESMA do manifesto, e tem de ser: `index.js` usa o
 * que os dois anteriores deixam no escopo.
 */
const ARQUIVOS_DO_CONTENT_SCRIPT = [
  'src/content/video-observer.js',
  'src/content/providers/disney.js',
  'src/content/providers/prime.js',
  'src/content/providers/max.js',
  'src/content/providers/netflix.js',
  'src/content/index.js',
]

async function reinjetarNasAbasAbertas() {
  if (chrome.scripting === undefined) return
  let abas = []
  try {
    abas = await chrome.tabs.query({ url: ['http://*/*', 'https://*/*'] })
  } catch (erro) {
    void registrar('REINJECAO_FALHOU', { erro: String(erro) })
    return
  }
  let injetadas = 0
  for (const aba of abas) {
    if (aba.id === undefined) continue
    try {
      await chrome.scripting.executeScript({
        target: { tabId: aba.id },
        files: ARQUIVOS_DO_CONTENT_SCRIPT,
      })
      injetadas += 1
    } catch {
      // Aba do proprio Chrome, PDF, pagina de erro: nao da para injetar, e
      // tentar nao pode derrubar o resto.
    }
  }
  void registrar('REINJETADO', { abas: injetadas })
}

/**
 * A vigia — e por que ela NÃO viola a regra do relógio.
 *
 * O Master Loop proíbe o worker de ser responsável pelo relógio, e continua
 * proibindo: quem conta tempo é o content script, e nada aqui conta tempo.
 * Isto é outra coisa — é conferir se as abas ainda estão FALANDO, e o worker é
 * o único lado que pode fazer isso, porque é o único que sabe endereçar abas.
 *
 * `chrome.alarms` e não `setInterval` justamente por causa da regra: alarme
 * sobrevive à morte do worker e o ACORDA para disparar. Um `setInterval` aqui
 * morreria junto com o worker, em silêncio, que é o defeito que a regra existe
 * para evitar.
 *
 * ## O que a vigia conserta
 *
 * Medido no host.log em 30/08/2026, os dois modos de silêncio:
 *
 *   aba em segundo plano   o Chrome estrangula `setInterval` para uma vez por
 *                          minuto e depois congela a aba. O batimento de dez
 *                          segundos chegou a passar 840 segundos sem sair, e a
 *                          cadência ficou em exatos 60s — a assinatura do
 *                          estrangulamento.
 *
 *   content script órfão   a extensão recarregou e a aba ficou sem `chrome.*`.
 *                          Vinte e oito minutos de silêncio com o filme
 *                          tocando e a aba ativa; o que devolveu a ponte foi o
 *                          usuário recarregando a extensão na mão.
 *
 * O cutucão resolve o primeiro (a aba responde e bate na hora) e DESCOBRE o
 * segundo (a órfã não responde), e aí a reinjeção resolve.
 */
const ALARME_DA_VIGIA = 'vigia-das-abas'

/**
 * Quanto tempo de silêncio de uma aba já é motivo de suspeita.
 *
 * O batimento é de dez segundos. Noventa dá folga para o estrangulamento
 * brando do Chrome e para uma volta perdida, sem deixar o silêncio real passar
 * de um minuto e meio — que já é mais do que a tela deveria mentir.
 */
const SEGUNDOS_DE_SILENCIO_SUSPEITO = 90

/**
 * Quando cada aba falou pela última vez.
 *
 * Em `chrome.storage.session` e não em memória porque memória de worker morto
 * não é memória — a mesma razão do diário. `session` e não `local`: isto
 * descreve esta execução do navegador e não faz sentido sobreviver a ela.
 */
async function anotarQueFalou(tabId) {
  if (tabId === null || chrome.storage?.session === undefined) return
  try {
    const { ultimaFala = {} } = await chrome.storage.session.get('ultimaFala')
    ultimaFala[tabId] = Date.now()
    await chrome.storage.session.set({ ultimaFala })
  } catch {
    // Sem o registro a vigia cutuca a aba à toa, que é barato. Derrubar a
    // mensagem que estava passando não seria.
  }
}

async function vigiar() {
  if (chrome.storage?.session === undefined) return
  let ultimaFala = {}
  try {
    ({ ultimaFala = {} } = await chrome.storage.session.get('ultimaFala'))
  } catch {
    return
  }

  const agora = Date.now()
  const vivas = {}
  for (const [chave, quando] of Object.entries(ultimaFala)) {
    const tabId = Number(chave)
    // A aba sumiu do Chrome: esquecer é o certo, e tentar cutucá-la só geraria
    // erro. Sem isto o registro cresceria para sempre.
    let existe = true
    try {
      await chrome.tabs.get(tabId)
    } catch {
      existe = false
    }
    if (!existe) continue
    vivas[tabId] = quando

    if (agora - quando < SEGUNDOS_DE_SILENCIO_SUSPEITO * 1000) continue

    // Cutucar primeiro. Uma aba viva e só estrangulada responde na hora e bate
    // junto — e reinjetar uma aba que estava boa custaria trocar o observador
    // e o `sessionId` dela por nada.
    let respondeu = false
    try {
      const resposta = await chrome.tabs.sendMessage(tabId, {
        messageType: 'CUTUCAO',
      })
      respondeu = resposta?.ok === true
    } catch {
      // Não respondeu: órfã, congelada, ou página que nunca teve script.
    }
    if (respondeu) {
      void registrar('VIGIA_CUTUCOU', { tabId, silencio: Math.round((agora - quando) / 1000) })
      continue
    }

    try {
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ARQUIVOS_DO_CONTENT_SCRIPT,
      })
      void registrar('VIGIA_REINJETOU', { tabId, silencio: Math.round((agora - quando) / 1000) })
      // Conta como falado agora: a aba acabou de ganhar script novo, e cobrar
      // dela um batimento imediato só a reinjetaria de novo no próximo alarme.
      vivas[tabId] = agora
    } catch {
      // Aba do próprio Chrome, PDF, página de erro. Não dá para injetar, e
      // insistir a cada minuto não muda isso.
    }
  }

  try {
    await chrome.storage.session.set({ ultimaFala: vivas })
  } catch {
    // O próximo alarme reconstrói o que se perdeu aqui.
  }
}

chrome.alarms?.onAlarm.addListener((alarme) => {
  if (alarme.name === ALARME_DA_VIGIA) void vigiar()
})

/**
 * Um minuto é o piso do `chrome.alarms` em produção, e serve.
 *
 * `create` com o mesmo nome substitui o alarme existente, então chamar isto a
 * cada start do worker é idempotente — e é preciso, porque o worker morre e
 * volta o tempo todo.
 */
function ligarAVigia() {
  try {
    chrome.alarms?.create(ALARME_DA_VIGIA, { periodInMinutes: 1 })
  } catch {
    // Sem a API de alarmes a ponte continua funcionando como antes: o
    // batimento da aba é o caminho normal, e a vigia é a rede embaixo dele.
  }
}

ligarAVigia()

chrome.runtime.onInstalled.addListener(() => {
  void registrar('INSTALLED')
  void reinjetarNasAbasAbertas()
  ligarAVigia()
  enviarAoHost(envelope('PING'))
})

chrome.runtime.onStartup.addListener(() => {
  void registrar('STARTUP')
  enviarAoHost(envelope('PING'))
})

// Clicar no ícone força um teste manual, sem depender de esperar um evento.
chrome.action.onClicked.addListener(() => {
  void registrar('ACTION_CLICKED')
  enviarAoHost(envelope('PING'))
})

// O worker vai morrer: registrar a saída é o que permite comparar quantos
// starts houve contra quantos stops, e descobrir se a porta o mantinha vivo.
chrome.runtime.onSuspend?.addListener(() => {
  void registrar(CicloDeVida.WORKER_STOPPING)
})
