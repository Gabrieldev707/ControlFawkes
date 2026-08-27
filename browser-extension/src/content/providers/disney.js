/**
 * Fase 10 — o que só a página do Disney+ sabe.
 *
 * ## O que foi MEDIDO (26/08/2026, Gavião Arqueiro T1:E1 tocando)
 *
 * O título da aba diz só a obra, e mais nada:
 *
 *     document.title = "Gavião Arqueiro | Disney+"
 *
 * `navigator.mediaSession` está VAZIO (`playbackState: "none"`, sem metadata).
 * O Disney+ não declara nada para o navegador, e por isso a SMTC do Windows
 * nunca teve o que publicar. Não há fonte do lado do sistema operacional: ou a
 * página entrega, ou ninguém entrega.
 *
 * E a página entrega — dentro de Shadow DOM, que é onde as sondas anteriores
 * eram cegas:
 *
 *     «title-bug» ▸ div.title-bug-area ▸ div.title-bug-container
 *                 ▸ button.title-btn
 *                      ├─ div.title-field      "Gavião Arqueiro"
 *                      └─ div.subtitle-field   "T1:E1 Nunca Conheça seus Heróis"
 *
 * Obra e episódio separados, com T e E no formato que o backend já lê.
 *
 * ## A restrição que desenha este arquivo inteiro
 *
 * O overlay de controles some do DOM depois de alguns segundos sem mouse.
 * Medido, com duas amostras a 12 segundos de distância:
 *
 *     imediato          `.title-btn` presente, obra e episódio legíveis
 *     após 12s ocioso   `.title-btn` NÃO EXISTE. sliders: []. nada.
 *
 * Ou seja: durante o uso normal — que é a pessoa assistindo sem mexer o mouse
 * — a leitura falha na esmagadora maioria dos batimentos. Um adapter que só
 * respondesse com o overlay aberto entregaria metadata piscando, e o cartão
 * trocaria de nome a cada dez segundos.
 *
 * Então a regra aqui é LER QUANDO APARECE, LEMBRAR DEPOIS.
 *
 * E a lembrança é presa ao `pathname`, que carrega o id do conteúdo
 * (`/pt-br/play/79955576-...`). Quando o episódio troca, a URL troca, e a
 * lembrança do anterior é descartada sozinha — sem precisar de expiração por
 * tempo, que seria um chute sobre quanto dura um episódio.
 *
 * ## A posição, que no Disney+ o `<video>` NÃO sabe
 *
 * Medido no mesmo instante:
 *
 *     slider "Linha do tempo"   now=146  max=3043   ("2:26 of 50:43")
 *     video.currentTime         50.8
 *     video.duration            Infinity
 *     video.seekable            [0, 62]
 *
 * O `<video>` do Disney+ só conhece a janela DASH que está montando naquele
 * instante — `seekable` inteiro cabia em 62 segundos, num episódio de 50
 * minutos. Então `currentTime` não é a posição no episódio, e `duration` não é
 * a duração dele. A posição que o ControlFawkes mostrava para Disney+ nunca
 * esteve certa: não é regressão, é um defeito que sempre esteve lá, escondido
 * atrás de um número plausível.
 *
 * Quem sabe é o slider — e ele desaparece junto com o resto do overlay.
 *
 * ## Âncora e projeção, e por que isso NÃO é um segundo relógio
 *
 * O critério de implementação incorreta nº 11 do Master Loop proíbe uma
 * segunda verdade sobre o tempo. Um `setInterval` contando aqui seria
 * exatamente isso, e não é o que acontece.
 *
 * O que se guarda é um PAR, lido no mesmo instante:
 *
 *     âncora = (posição real do slider, `currentTime` naquele momento)
 *
 * Depois, a posição real é `âncora.real + (currentTime - âncora.base)`. Quem
 * conta o tempo continua sendo o mesmo `<video>` de sempre; a âncora só
 * corrige o DESLOCAMENTO entre a origem da janela DASH e a origem do episódio.
 * Uma verdade sobre o tempo, com um offset medido.
 *
 * E o delta é confiável mesmo que o absoluto não seja: medido, `currentTime`
 * andou de 50.8 para 62.8 em doze segundos — exatamente doze.
 *
 * A âncora é descartada, e a posição volta a ser desconhecida, quando:
 *
 *     - o elemento de vídeo muda        outro `<video>`, outra origem
 *     - o delta é negativo ou absurdo   houve seek, ou a janela DASH virou
 *     - a URL muda                      outra reprodução
 *
 * Nos três casos a resposta é NÃO AFIRMAR até o overlay reaparecer. Projetar
 * em cima de uma âncora inválida daria um número plausível e errado, que é a
 * forma de erro que este projeto mais paga caro.
 */

/* eslint-disable no-unused-vars */

/**
 * Teto da varredura de shadow roots.
 *
 * O player abre dezenas por conta própria (medido: 76 numa página de
 * reprodução). Varrer é barato; varrer sem limite, numa página que nenhum de
 * nós controla, não é.
 */
const TETO_DE_RAIZES_DISNEY = 400

/**
 * Todas as raízes de DOM da página, atravessando shadow roots.
 *
 * `document.querySelectorAll` NÃO atravessa shadow root, e o player do Disney+
 * é feito inteiro de custom elements (`disney-web-player-ui`,
 * `main-app-controls-overlay`, `title-bug`...). Sem esta varredura a página
 * parece vazia: a primeira sonda voltou com zero elementos marcados e zero
 * textos com episódio, num player que tinha os dois na tela.
 */
function raizesComShadow(documento) {
  const raizes = [documento]
  const vistas = new Set()
  for (let i = 0; i < raizes.length && i < TETO_DE_RAIZES_DISNEY; i += 1) {
    let elementos
    try {
      elementos = raizes[i].querySelectorAll('*')
    } catch {
      continue
    }
    for (const elemento of elementos) {
      const raiz = elemento.shadowRoot
      if (raiz && !vistas.has(raiz)) {
        vistas.add(raiz)
        raizes.push(raiz)
      }
    }
  }
  return raizes
}

/** O primeiro casamento do seletor em qualquer raiz. */
function acharEmQualquerRaiz(raizes, seletor) {
  for (const raiz of raizes) {
    let achado
    try {
      achado = raiz.querySelector(seletor)
    } catch {
      continue
    }
    if (achado) return achado
  }
  return null
}

function textoDisney(no) {
  if (!no) return null
  const bruto = (no.textContent || '').replace(/\s+/g, ' ').trim()
  return bruto === '' ? null : bruto
}

/**
 * "T1:E1", "S1 E1", "1x04" → { temporada, episodio, marcador }.
 *
 * Duplicado de `netflix.js` de propósito, e não importado: content script
 * declarado no manifesto NÃO é módulo, e fazer este adapter depender de o
 * outro ter sido avaliado antes cria um acoplamento invisível entre dois
 * arquivos que precisam poder falhar em separado. São seis linhas de regex; um
 * refactor do arquivo que hoje é o ÚNICO serviço funcionando custa mais.
 *
 * `marcador` é o trecho que casou, e existe para o nome do episódio poder ser
 * o que sobra depois de tirá-lo.
 */
const PADROES_DISNEY = [
  /\b[ST](\d{1,2})\s*(?:[:x\s-]\s*E?|E)P?\s*(\d{1,3})\b/i,
  /\b(?:temporada|season)\s*(\d{1,2}).{0,4}(?:epis[oó]dio|episode)\s*(\d{1,3})\b/i,
  /\b(\d{1,2})x(\d{2,3})\b/,
]

function temporadaEEpisodioDisney(texto) {
  if (typeof texto !== 'string' || texto === '') return null
  for (const padrao of PADROES_DISNEY) {
    const achado = padrao.exec(texto)
    if (achado === null) continue
    const temporada = Number(achado[1])
    const episodio = Number(achado[2])
    // Zero não existe em nenhuma das duas contagens; número alto demais é ano
    // ou pedaço do nome que virou número por acidente.
    if (temporada >= 1 && temporada <= 50 && episodio >= 1 && episodio <= 999) {
      return { temporada, episodio, marcador: achado[0] }
    }
  }
  return null
}

/**
 * O bloco de título do player, quando ele está no DOM.
 *
 * `.title-field` e `.subtitle-field` são nomes MEDIDOS, não deduzidos: a sonda
 * pediu os filhos do `.title-btn` justamente para não ter de inventar nome de
 * classe. Foi inventar formato de título que quebrou Prime, Disney+ e Max
 * enquanto a Netflix — a única medida — funcionava.
 *
 * Ainda assim a leitura é tolerante a esses dois nomes sumirem: um seletor
 * único é uma bomba com relógio, e o dia em que o Disney+ renomear a classe
 * não pode ser o dia em que a metadata some inteira.
 */
function doBlocoDeTitulo(raizes) {
  const botao = acharEmQualquerRaiz(raizes, '.title-btn')
  if (botao === null) return null

  const filhos = Array.from(botao.children)
  const comTexto = filhos.filter((filho) => textoDisney(filho) !== null)
  const obra = textoDisney(botao.querySelector('.title-field'))
    ?? textoDisney(comTexto[0])
  if (obra === null) return null

  const legenda = textoDisney(botao.querySelector('.subtitle-field'))
    ?? textoDisney(comTexto.find((filho) => textoDisney(filho) !== obra))

  const resultado = { workTitle: obra }
  // Um filme não tem legenda nenhuma, e isso é resposta completa, não falha.
  if (legenda === null) return resultado

  const numeros = temporadaEEpisodioDisney(legenda)
  if (numeros === null) {
    // Grafia que ainda não vimos. O texto vira NOME de episódio em vez de ser
    // jogado fora — e sem número, porque um "T1 E1" chutado é pior do que
    // número nenhum: a pessoa acredita nele.
    resultado.episodeTitle = legenda
    return resultado
  }

  resultado.seasonNumber = numeros.temporada
  resultado.episodeNumber = numeros.episodio
  // O que sobra depois de tirar o "T1:E1" é o nome. Em
  // "T1:E1 Nunca Conheça seus Heróis" sobra "Nunca Conheça seus Heróis".
  const nome = legenda.replace(numeros.marcador, '').replace(/^[\s:·|–—-]+/, '').trim()
  if (nome !== '') resultado.episodeTitle = nome
  return resultado
}

/**
 * A última leitura boa, presa à URL de onde ela veio.
 *
 * Sem isto o adapter responderia em talvez um batimento a cada dez — o overlay
 * fica fora do DOM na maior parte do tempo — e o cartão ficaria alternando
 * entre "Gavião Arqueiro T1:E1" e nada, sem parar.
 */
let lembrancaDoDisney = null

/**
 * A classe da barra de progresso, medida: `progress-bar__seekable-range`.
 *
 * O casamento é por CLASSE e não por `aria-label`, que veio "Linha do tempo"
 * nesta máquina e viria "Timeline" noutra — o rótulo é traduzido para o idioma
 * da conta, e prender o adapter a ele o quebraria para qualquer pessoa que não
 * usasse português.
 */
const CLASSE_DA_LINHA_DO_TEMPO = 'progress-bar__seekable-range'

/** Quanto o `currentTime` pode andar entre duas leituras e ainda ser o mesmo. */
const DELTA_MINIMO = -2.0
const DELTA_MAXIMO = 7200.0

/**
 * A posição e a duração REAIS, do slider — quando o overlay está aberto.
 *
 * `aria-valuenow` e `aria-valuemax` em segundos, medidos: `now=146 max=3043`,
 * com o `aria-valuetext` dizendo "2:26 of 50:43" — 146s são 2:26 e 3043s são
 * 50:43, então os dois números são de conteúdo, não de buffer.
 */
function daLinhaDoTempo(raizes) {
  for (const raiz of raizes) {
    let sliders
    try {
      sliders = raiz.querySelectorAll('[role="slider"]')
    } catch {
      continue
    }
    for (const slider of sliders) {
      if (!String(slider.className || '').includes(CLASSE_DA_LINHA_DO_TEMPO)) continue
      const posicao = Number(slider.getAttribute('aria-valuenow'))
      const duracao = Number(slider.getAttribute('aria-valuemax'))
      if (!Number.isFinite(posicao) || !Number.isFinite(duracao)) continue
      // Duração zero não é duração, e posição além do fim é leitura misturada
      // entre duas reproduções. Um segundo de folga cobre arredondamento.
      if (duracao <= 0 || posicao < 0 || posicao > duracao + 1) continue
      return { posicao, duracao }
    }
  }
  return null
}

/**
 * O `<video>` do conteúdo, e só ele.
 *
 * A página tem DOIS: medido, um parado em `currentTime=0` com
 * `videoWidth=0`, e o que está tocando. O player carrega a classe
 * `has-interstitials` e usa o segundo elemento também para anúncio — e um
 * anúncio tem outra origem de tempo.
 *
 * Com mais de um candidato a resposta é NENHUM. Ancorar no vídeo errado daria
 * um deslocamento errado que continuaria sendo aplicado depois, e um número
 * errado que persiste é pior do que um número ausente.
 */
function videoDoConteudo(raizes) {
  const candidatos = []
  for (const raiz of raizes) {
    let videos
    try {
      videos = raiz.querySelectorAll('video')
    } catch {
      continue
    }
    for (const video of videos) {
      if (video.videoWidth > 0) candidatos.push(video)
    }
  }
  return candidatos.length === 1 ? candidatos[0] : null
}

/**
 * O par (posição real, `currentTime` daquele instante).
 *
 * Guarda o ELEMENTO, e não só o número: quando o player troca de `<video>` —
 * entrada ou saída de anúncio — a origem do tempo muda, e continuar projetando
 * em cima do deslocamento antigo daria um número plausível e errado.
 */
let ancoraDoDisney = null

/**
 * A posição real agora: do slider quando ele está aberto, projetada quando não.
 *
 * `null` é resposta legítima e frequente — é o estado de quem ainda não viu o
 * overlay uma vez. O backend já sabe desenhar um cartão sem posição; ele não
 * sabe desconfiar de uma posição errada.
 */
function posicaoReal(raizes, caminho) {
  const video = videoDoConteudo(raizes)
  const lido = daLinhaDoTempo(raizes)

  if (lido !== null && video !== null) {
    ancoraDoDisney = {
      caminho,
      real: lido.posicao,
      duracao: lido.duracao,
      base: video.currentTime,
      elemento: video,
    }
    return { posicao: lido.posicao, duracao: lido.duracao }
  }

  const ancora = ancoraDoDisney
  if (ancora === null || video === null) return null
  // Outra reprodução, ou outro elemento: o deslocamento medido não vale mais.
  if (ancora.caminho !== caminho || ancora.elemento !== video) {
    ancoraDoDisney = null
    return null
  }

  const delta = video.currentTime - ancora.base
  // Delta negativo é seek para trás; delta absurdo é a janela DASH tendo
  // virado. Nos dois casos o deslocamento morreu junto.
  if (!Number.isFinite(delta) || delta < DELTA_MINIMO || delta > DELTA_MAXIMO) {
    ancoraDoDisney = null
    return null
  }

  const projetada = Math.max(0, ancora.real + delta)
  return {
    // Não passa do fim: um episódio que "passou" da própria duração é sinal de
    // âncora velha, e o fim é o valor mais honesto que ainda é verdade.
    posicao: Math.min(projetada, ancora.duracao),
    duracao: ancora.duracao,
  }
}

/** Só para os testes: a âncora não pode vazar de um caso para o outro. */
function esquecerAncoraDoDisney() {
  ancoraDoDisney = null
}

/** O id da reprodução na URL: `/pt-br/play/79955576-c891-414d-...`. */
function idDaPaginaDisney(caminho) {
  const achado = /\/play\/([0-9a-f][0-9a-f-]{7,})/i.exec(caminho || '')
  return achado === null ? null : achado[1]
}

function lerDisney(documento = document, local = location) {
  const caminho = local.pathname || ''
  const id = idDaPaginaDisney(caminho)

  // Fora de `/play` não há reprodução: é catálogo, busca ou página de detalhe.
  // A vitrine dessas telas toca trailer, e é o mesmo defeito que fazia a
  // Netflix mandar "Home" como nome de obra.
  if (id === null) {
    lembrancaDoDisney = null
    ancoraDoDisney = null
    return null
  }

  // Outra reprodução: a lembrança da anterior não vale mais. Descartar ANTES
  // de ler é o que impede afirmar o episódio errado durante os segundos em que
  // o novo overlay ainda não apareceu — e afirmar errado é pior do que calar.
  if (lembrancaDoDisney !== null && lembrancaDoDisney.caminho !== caminho) {
    lembrancaDoDisney = null
  }

  // Uma varredura só para as duas leituras. Ela percorre dezenas de shadow
  // roots, e fazê-la duas vezes por batimento seria pagar o dobro pelo mesmo
  // resultado.
  const raizes = raizesComShadow(documento)

  const lido = doBlocoDeTitulo(raizes)
  if (lido !== null) lembrancaDoDisney = { caminho, dados: lido }

  let tempo = posicaoReal(raizes, caminho)
  // Sem âncora, a posição e a duração reais não existem — e quem assiste pelo
  // celular não mexe o mouse do computador para elas aparecerem. Então o
  // adapter pede os controles de volta, uma vez a cada poucos segundos, até
  // conseguir a leitura. Depois disso ele para sozinho.
  if (tempo === null) {
    acordarOsControles(documento, raizes)
    tempo = posicaoReal(raizes, caminho)
  }
  const dados = lembrancaDoDisney === null ? null : lembrancaDoDisney.dados

  const resposta = {
    pageId: id,
    // Ausentes quando o overlay nunca apareceu, e ausente é o certo: o backend
    // sabe desenhar um cartão sem posição, e não sabe desconfiar de uma
    // posição errada.
    adapterPosition: tempo === null ? null : tempo.posicao,
    adapterDuration: tempo === null ? null : tempo.duracao,
  }

  if (dados === null) {
    // Sem nome, o id ainda é identidade de reprodução válida: ele distingue
    // "episódio retomado" de "episódio seguinte" sem depender de nome nenhum.
    return resposta
  }

  return {
    ...resposta,
    workTitle: dados.workTitle ?? null,
    episodeTitle: dados.episodeTitle ?? null,
    seasonNumber: dados.seasonNumber ?? null,
    episodeNumber: dados.episodeNumber ?? null,
  }
}

/**
 * Quanto esperar entre duas tentativas de acordar os controles.
 *
 * Acordar faz o overlay aparecer na tela por alguns segundos. Uma vez, para
 * conseguir a única leitura que falta, é aceitável; a cada batimento seria a
 * interface piscando sozinha em cima do filme.
 */
const SEGUNDOS_ENTRE_TENTATIVAS = 6.0

let ultimoAcordar = 0

/**
 * Faz o player mostrar os controles, para o slider existir por um instante.
 *
 * ## Por que isto precisou existir
 *
 * A posição e a duração REAIS do Disney+ só vivem no slider, e o slider some
 * junto com o overlay depois de alguns segundos sem mouse. O desenho original
 * dependia de a pessoa mexer o mouse alguma vez — e quem assiste pelo celular
 * não mexe o mouse do computador nunca.
 *
 * O resultado, relatado em 26/08/2026 com WandaVision tocando: o cartão dizia
 * "ao vivo" e mostrava "2:34". Sem âncora, a duração fica ausente (o `<video>`
 * publica `Infinity`, recusado na validação) e a posição cai para o
 * `currentTime` do elemento — que é a janela DASH, e não o episódio.
 *
 * ## O gesto
 *
 * Um `mousemove` sintético sobre o player. Mostrar controles é reação a um
 * ouvinte de evento comum; não exige ativação do usuário, que é o que impede
 * um content script de pedir tela cheia por conta própria.
 *
 * Só acontece enquanto NÃO há âncora. Assim que uma leitura boa acontece, isto
 * para sozinho — e volta só se a âncora for invalidada (troca de episódio,
 * seek, troca de elemento).
 */
function acordarOsControles(documento, raizes) {
  const agora = Date.now() / 1000
  if (agora - ultimoAcordar < SEGUNDOS_ENTRE_TENTATIVAS) return
  ultimoAcordar = agora

  const video = videoDoConteudo(raizes)
  const alvo = video ?? acharEmQualquerRaiz(raizes, '.btm-media-player') ?? documento.body
  if (alvo === null || alvo === undefined) return

  let x = 0
  let y = 0
  try {
    const r = alvo.getBoundingClientRect()
    x = r.left + r.width / 2
    y = r.top + r.height / 2
  } catch {
    // Sem retângulo, o evento no meio da janela ainda alcança o player.
    x = (documento.defaultView?.innerWidth ?? 0) / 2
    y = (documento.defaultView?.innerHeight ?? 0) / 2
  }

  for (const tipo of ['mousemove', 'pointermove']) {
    try {
      alvo.dispatchEvent(new MouseEvent(tipo, {
        bubbles: true, cancelable: true, clientX: x, clientY: y,
      }))
    } catch {
      // Ambiente sem `MouseEvent` (o teste em jsdom antigo) não pode derrubar
      // a leitura: acordar é uma melhoria, não um requisito.
    }
  }
}

/** Só para os testes: nada pode vazar de um caso para o outro. */
function esquecerLembrancaDoDisney() {
  lembrancaDoDisney = null
  ancoraDoDisney = null
  ultimoAcordar = 0
}

// Sem `export`: content script declarado no manifesto NÃO é módulo, e um
// `import`/`export` aqui é erro de sintaxe — a aba fica sem script e nada
// acusa. Mesma decisão de `netflix.js` e `video-observer.js`.
