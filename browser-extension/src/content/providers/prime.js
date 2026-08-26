/**
 * Fase 10 — o que só a página do Prime Video sabe.
 *
 * ## O que foi MEDIDO (26/08/2026, Batman: The Animated Series S3 E7 tocando)
 *
 *     document.title   "Prime Video: Batman: The Animated Series: Volume 3"
 *     location         /detail/0HNVIQ8ZNGW9S1S37714VTRY55
 *
 * O título da aba nomeia a OBRA — e com o empacotamento da Amazon junto
 * ("Volume 3"), que não é parte do nome da série. Episódio e temporada não
 * aparecem nele em lugar nenhum.
 *
 * `navigator.mediaSession` está vazio (`playbackState: "none"`), igual ao
 * Disney+. Nenhuma fonte do Windows sabe o episódio.
 *
 * A página sabe, em DOM comum — sem Shadow DOM nenhum, ao contrário do
 * Disney+:
 *
 *     div.atvwebplayersdk-title-text     "Batman: The Animated Series"
 *     span.atvwebplayersdk-episode-info  "S3 E7 Fire from Olympus"
 *
 * `atvwebplayersdk-` é o prefixo do SDK do player da Amazon, e os dois nomes
 * são semânticos — "texto do título", "informação do episódio" —, não gerados
 * como as classes do resto da página (`_36qUej`, `f6gi9c2`).
 *
 * ## O que NÃO é preciso aqui, e é bom dizer por quê
 *
 * **Tempo.** O `<video>` do Prime é honesto, e isso está medido:
 *
 *     currentTime 1213.9   duration 1329.184   seekable até 1329.2
 *
 * 1329 segundos são 22 minutos, e batem com o `episode-runtime` que a própria
 * página publica. Nada de `Infinity`, nada de janela DASH. A posição e a
 * duração do Prime sempre estiveram certas, e este adapter não toca nelas —
 * declará-las aqui criaria disputa onde não há defeito.
 *
 * **Lembrança.** Os dois elementos continuam no DOM quando os controles somem;
 * o que muda é só terem área na tela (`getClientRects()` vazio). O Disney+
 * remove o overlay inteiro e por isso precisa de memória; o Prime não. Guardar
 * "a última leitura boa" aqui só criaria uma forma de afirmar episódio velho.
 *
 * ## As três armadilhas da página, todas medidas
 *
 * A varredura achou TRÊS textos com "S3 E7" ou "Season", e dois mentiriam:
 *
 *     "S3 E7 Fire from Olympus"  .atvwebplayersdk-episode-info   ← o que toca
 *     "Resume S3 E7"             div.dv-node-dp-action-box       botão
 *     "Season 3" / "Season 1..4" div._3R4jka                     seletor
 *
 * E o botão "Resume" estava VISÍVEL enquanto o do player estava escondido —
 * então "pegar o que está na tela" escolheria exatamente o errado. É a mesma
 * armadilha da fileira "A seguir" do Disney+, com outra cara.
 *
 * A terceira: `document.querySelector('.atvwebplayersdk-player-container')`
 * NÃO contém esses elementos. A página de detalhe monta mais de um player (há
 * prévias), e o primeiro container não é o que está tocando. Por isso a busca
 * sobe a partir do `<video>` que tem imagem, em vez de descer a partir de um
 * container escolhido a esmo.
 */

/* eslint-disable no-unused-vars */

/**
 * Quantos ancestrais subir a partir do `<video>` procurando o título.
 *
 * Generoso porque a árvore do Prime é funda: o caminho medido do
 * `.atvwebplayersdk-episode-info` até o `.atvwebplayersdk-player-container` já
 * tem TREZE níveis, e a profundidade do `<video>` não foi medida. Subir de
 * menos faria a busca falhar em silêncio — e um teto curto não protege de
 * nada, porque `querySelector` num ancestral alto continua barato.
 */
const ALTURA_DA_BUSCA_PRIME = 20

const PADROES_PRIME = [
  /\b[ST](\d{1,2})\s*(?:[:x\s-]\s*E?|E)P?\s*(\d{1,3})\b/i,
  /\b(?:temporada|season)\s*(\d{1,2}).{0,4}(?:epis[oó]dio|episode)\s*(\d{1,3})\b/i,
  /\b(\d{1,2})x(\d{2,3})\b/,
]

function temporadaEEpisodioPrime(texto) {
  if (typeof texto !== 'string' || texto === '') return null
  for (const padrao of PADROES_PRIME) {
    const achado = padrao.exec(texto)
    if (achado === null) continue
    const temporada = Number(achado[1])
    const episodio = Number(achado[2])
    if (temporada >= 1 && temporada <= 50 && episodio >= 1 && episodio <= 999) {
      return { temporada, episodio, marcador: achado[0] }
    }
  }
  return null
}

function textoPrime(no) {
  if (!no) return null
  const bruto = (no.textContent || '').replace(/\s+/g, ' ').trim()
  return bruto === '' ? null : bruto
}

/**
 * O `<video>` que tem imagem — o MAIOR deles. `null` quando não há nenhum.
 *
 * Medido: a página mantém um segundo elemento parado, com `videoWidth` zero.
 * Esse é o que precisa ficar de fora.
 *
 * A primeira versão disto exigia EXATAMENTE um, e devolvia `null` com dois ou
 * mais — copiado do adapter do Disney+, onde a regra tem motivo: lá o player
 * declara `has-interstitials` e usa um segundo elemento para anúncio, com
 * outra origem de tempo, e ancorar no errado estragaria a posição.
 *
 * Aqui não há nada disso. Este adapter não declara tempo nenhum — o `<video>`
 * do Prime é honesto e o `video-observer` já cuida dele. O vídeo serve para
 * uma pergunta só: "há reprodução acontecendo?". Exigir unicidade para
 * responder isso era rigor emprestado de um problema que o Prime não tem, e
 * teria calado o adapter inteiro no dia em que a página abrisse uma prévia.
 *
 * Copiar a forma de uma regra sem copiar a razão dela é o mesmo erro que me
 * fez inventar formato de título — só que virado do avesso.
 */
function videoDoConteudoPrime(documento) {
  let videos
  try {
    videos = documento.querySelectorAll('video')
  } catch {
    return null
  }
  let melhor = null
  for (const video of videos) {
    if (video.videoWidth > 0 && (melhor === null || video.videoWidth > melhor.videoWidth)) {
      melhor = video
    }
  }
  return melhor
}

/**
 * O bloco do player que pertence AO vídeo que está tocando.
 *
 * Sobe a partir do elemento em vez de descer a partir de um container: a
 * página tem mais de um `.atvwebplayersdk-player-container`, e escolher "o
 * primeiro" pegaria o de prévia. Subindo, o primeiro ancestral que contém um
 * título é necessariamente o do player deste vídeo.
 */
function doPlayerDoVideo(video) {
  let no = video.parentElement
  for (let i = 0; i < ALTURA_DA_BUSCA_PRIME && no; i += 1, no = no.parentElement) {
    let titulo
    try {
      titulo = no.querySelector('.atvwebplayersdk-title-text')
    } catch {
      titulo = null
    }
    if (titulo !== null) {
      return {
        obra: textoPrime(titulo),
        legenda: textoPrime(no.querySelector('.atvwebplayersdk-episode-info')),
      }
    }
  }
  return null
}

/**
 * A rede de segurança, quando subir não encontra nada.
 *
 * Só vale com UM título na página inteira: dois seriam dois players, e aí
 * escolher é adivinhar. Existe porque o dia em que a Amazon mudar o
 * aninhamento não pode ser o dia em que a metadata some inteira.
 */
function doDocumentoInteiro(documento) {
  let titulos
  let episodios
  try {
    titulos = documento.querySelectorAll('.atvwebplayersdk-title-text')
    episodios = documento.querySelectorAll('.atvwebplayersdk-episode-info')
  } catch {
    return null
  }
  if (titulos.length !== 1) return null
  return {
    obra: textoPrime(titulos[0]),
    legenda: episodios.length === 1 ? textoPrime(episodios[0]) : null,
  }
}

function lerPrime(documento = document, _local = location) {
  // Sem vídeo com imagem não há reprodução a descrever. É o guarda que impede
  // afirmar o último episódio lido quando a pessoa já fechou o player e está
  // só navegando pelo catálogo — os elementos do SDK podem ficar para trás.
  const video = videoDoConteudoPrime(documento)
  if (video === null) return null

  const lido = doPlayerDoVideo(video) ?? doDocumentoInteiro(documento)
  if (lido === null || lido.obra === null) return null

  const resultado = {
    workTitle: lido.obra,
    episodeTitle: null,
    seasonNumber: null,
    episodeNumber: null,
    // Sem `pageId`, e de propósito. A URL medida é `/detail/0HNVIQ8ZN...`, que
    // identifica a SÉRIE e não o episódio: ela não muda quando o episódio muda.
    // Mandá-la faria dois episódios diferentes parecerem a mesma reprodução, e
    // o histórico deixaria de perceber a troca. Sem ela, a identidade sai de
    // temporada + episódio + duração, que aqui são todos conhecidos.
    pageId: null,
  }

  if (lido.legenda === null) return resultado

  const numeros = temporadaEEpisodioPrime(lido.legenda)
  if (numeros === null) {
    // Grafia que ainda não vimos. Vira NOME de episódio, sem número: um
    // "T1 E1" chutado é pior do que número nenhum, porque a pessoa acredita.
    resultado.episodeTitle = lido.legenda
    return resultado
  }

  resultado.seasonNumber = numeros.temporada
  resultado.episodeNumber = numeros.episodio
  const nome = lido.legenda
    .replace(numeros.marcador, '')
    .replace(/^[\s:·|–—-]+/, '')
    .trim()
  if (nome !== '') resultado.episodeTitle = nome
  return resultado
}

// Sem `export`: content script declarado no manifesto NÃO é módulo, e um
// `import`/`export` aqui é erro de sintaxe — a aba fica sem script e nada
// acusa. Mesma decisão de `netflix.js` e `disney.js`.
