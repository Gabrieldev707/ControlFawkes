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
    void registrar('HOST_MESSAGE', mensagem)
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

  const enriquecida = {
    ...mensagem,
    payload: {
      ...(mensagem.payload ?? {}),
      tabId: sender.tab?.id ?? null,
      windowId: sender.tab?.windowId ?? null,
    },
  }

  // Só o TIPO e a aba. O payload traz `href`, e registrá-lo transformaria o
  // diário de diagnóstico num histórico de navegação.
  void registrar('DA_ABA', {
    messageType: mensagem.messageType,
    tabId: sender.tab?.id ?? null,
  })

  responder({ ok: enviarAoHost(enriquecida) })
  return false
})

chrome.runtime.onInstalled.addListener(() => {
  void registrar('INSTALLED')
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
