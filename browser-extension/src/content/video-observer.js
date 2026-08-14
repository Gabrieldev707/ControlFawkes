/**
 * Observa o `<video>` da página — e sobrevive a ele ser trocado.
 *
 * Sem `import`: content script declarado no manifesto não é módulo. Este
 * arquivo é carregado antes de `index.js` e expõe `criarObservador` no escopo
 * do content script (mundo isolado, não vaza para a página).
 *
 * ## O que quase todo observador de vídeo erra
 *
 * Guardar referência ao primeiro `<video>` que encontrou. Netflix, Max,
 * Disney+ e Prime Video usam MSE, e **trocam o elemento** em mudança de
 * qualidade e em troca de episódio. Quem guardou o primeiro para de receber
 * evento e não percebe: `currentTime` congela num número plausível, nenhum
 * erro aparece, e a extensão segue reportando com confiança a posição de um
 * elemento que saiu do documento.
 *
 * É o critério de implementação incorreta nº 18 do Master Loop, e o motivo de
 * o gate da Fase 5 exigir troca de elemento aprovada — validar só numa página
 * HTML5 simples aprova um observador que nunca funcionaria na Netflix.
 *
 * ## Duração é traiçoeira
 *
 * `video.duration` é `NaN` antes de `loadedmetadata` e `Infinity` em
 * transmissão ao vivo. Nenhum dos dois é uma duração, e os dois viram `null` —
 * mandar `NaN` viraria a string `null` no JSON e mandar `Infinity` viraria
 * `null` também, mas por acidente de serialização, não por decisão. Aqui é por
 * decisão.
 */

/* eslint-disable no-unused-vars */

/** Eventos do elemento que merecem envio imediato. */
const EVENTOS = [
  'play', 'pause', 'ended', 'seeking', 'seeked',
  'loadedmetadata', 'durationchange', 'ratechange', 'emptied',
]

function duracaoUtil(bruta) {
  // `NaN` (metadata não chegou) e `Infinity` (ao vivo) não são durações.
  if (typeof bruta !== 'number' || Number.isNaN(bruta) || !Number.isFinite(bruta)) return null
  return bruta > 0 ? bruta : null
}

function estadoDe(video) {
  if (video.ended) return 'ended'
  return video.paused ? 'paused' : 'playing'
}

/** O retrato do elemento agora. Só os campos do contrato da Fase 2. */
function lerElemento(video) {
  return {
    playbackState: estadoDe(video),
    currentTime: Number.isFinite(video.currentTime) ? video.currentTime : null,
    duration: duracaoUtil(video.duration),
    playbackRate: Number.isFinite(video.playbackRate) ? video.playbackRate : null,
    muted: video.muted === true,
  }
}

/**
 * Acha o elemento que importa.
 *
 * O maior em área, e não o primeiro do documento: páginas de serviço têm
 * `<video>` de trailer, de prévia e de anúncio junto com o player. O primeiro
 * na ordem do DOM costuma ser o errado.
 *
 * Shadow roots ABERTOS entram na busca. Os fechados não são alcançáveis por
 * ninguém, e fingir que são só produziria código morto.
 */
function descobrir(raiz = document) {
  const achados = []

  const varrer = (no) => {
    for (const elemento of no.querySelectorAll('video, audio')) {
      achados.push(elemento)
      if (elemento.shadowRoot) varrer(elemento.shadowRoot)
    }
    for (const elemento of no.querySelectorAll('*')) {
      if (elemento.shadowRoot) varrer(elemento.shadowRoot)
    }
  }

  try {
    varrer(raiz)
  } catch {
    // DOM hostil não pode derrubar o content script.
  }

  if (achados.length === 0) return null
  return achados.reduce((maior, atual) => {
    const area = (elemento) => (elemento.clientWidth || 0) * (elemento.clientHeight || 0)
    return area(atual) > area(maior) ? atual : maior
  })
}

/**
 * Liga o observador e devolve como desligá-lo.
 *
 * `aoMudar(tipo, leitura)` é chamado em cada evento relevante e quando o
 * elemento é trocado. O relógio de batimento NÃO mora aqui — quem o mantém é
 * `index.js`, e este módulo só sabe ler.
 */
function criarObservador(aoMudar) {
  let atual = null
  let desligarEventos = null

  const soltar = () => {
    if (desligarEventos !== null) desligarEventos()
    desligarEventos = null
    atual = null
  }

  const prender = (video) => {
    if (video === atual) return
    soltar()
    atual = video

    const ouvinte = (evento) => aoMudar(evento.type, lerElemento(video))
    for (const nome of EVENTOS) video.addEventListener(nome, ouvinte)
    desligarEventos = () => {
      for (const nome of EVENTOS) video.removeEventListener(nome, ouvinte)
    }
    aoMudar('bound', lerElemento(video))
  }

  const reconferir = () => {
    // `isConnected` é o que pega a troca de elemento: o objeto antigo continua
    // existindo e respondendo `currentTime`, só não está mais no documento.
    // Sem esta checagem o observador segue lendo um fantasma.
    if (atual !== null && !atual.isConnected) {
      aoMudar('detached', null)
      soltar()
    }
    const achado = descobrir()
    if (achado === null) {
      if (atual !== null) soltar()
      return
    }
    prender(achado)
  }

  // MutationObserver para o DOM mudar, e uma reconferida periódica porque
  // nem toda troca passa por mutação observável — trocar o `src` de um
  // elemento que já existe não move nada na árvore.
  const mutacoes = new MutationObserver(() => reconferir())
  try {
    mutacoes.observe(document.documentElement, { childList: true, subtree: true })
  } catch {
    // Documento ainda não montado: a reconferida periódica cobre.
  }
  const periodica = setInterval(reconferir, 2000)
  reconferir()

  return {
    ler: () => (atual !== null && atual.isConnected ? lerElemento(atual) : null),
    parar: () => {
      mutacoes.disconnect()
      clearInterval(periodica)
      soltar()
    },
  }
}
