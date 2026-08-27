/**
 * Fase 10 — o que só a página da Netflix sabe.
 *
 * A Netflix é o único serviço em que as DUAS fontes do Windows são cegas ao
 * mesmo tempo, e isso está medido:
 *
 *     SMTC (Chrome)          publica "Netflix". O nome do site, nunca o do
 *                            conteúdo.
 *     título da janela       em `/watch`, "Netflix - Google Chrome". A Netflix
 *                            não põe o nome da obra no `document.title` da
 *                            página de reprodução.
 *
 * O resultado, no `historico.json` real deste computador: uma única linha de
 * Netflix em 13/08/2026, chamada "Netflix", com 120 segundos — a página de
 * catálogo. Nada mais, nunca. `_titulo_generico` zerava o título e o gravador
 * descartava a sessão inteira.
 *
 * Nenhuma leitura do Windows conserta isso, e é por isso que o Master Loop tem
 * uma regra permanente com o nome do serviço: "Netflix não pode depender de
 * SMTC para metadata da obra." Quem sabe é a página, e a extensão está dentro
 * dela.
 *
 * ## O que este arquivo faz, e o que ele tem proibido fazer
 *
 * Faz: obra, episódio, temporada, número do episódio.
 *
 * NÃO faz: relógio, `currentTime`, `duration`, play/pause, ciclo de vida do
 * `<video>`. Isso é do `video-observer.js`, que já funciona nos seis serviços,
 * e duplicar aqui criaria uma segunda verdade sobre o tempo — o critério de
 * implementação incorreta nº 11 do Master Loop, na forma de adapter.
 *
 * ## Por que uma CASCATA de estratégias, e não um seletor
 *
 * Porque o DOM da Netflix não é contrato nosso, e um seletor único é uma bomba
 * com relógio: no dia em que ele mudar, a metadata some inteira e nada acusa.
 * Cada estratégia aqui é independente e falha para `null` sem derrubar as
 * outras.
 *
 * E há um piso que NÃO depende de DOM nenhum: o id da URL (`/watch/81234567`).
 * Ele não é um nome, mas é uma identidade estável de reprodução — muda quando
 * o episódio muda, e é o que permite distinguir "mesmo episódio retomado" de
 * "próximo episódio" mesmo quando nenhum nome foi lido. Enquanto houver `id`,
 * a Fase 11 tem com o que trabalhar.
 *
 * ## A regra que vale mais do que acertar
 *
 * Não inventar. Um "T1 E1" chutado é pior do que número nenhum, porque a pessoa
 * acredita nele — é a mesma frase que a `temporada_e_episodio` do backend já
 * carrega. Quando nada casa, tudo aqui devolve `null`.
 */

/* eslint-disable no-unused-vars */

/** O id da reprodução na URL: `/watch/81234567` → "81234567". */
function idDaPagina(caminho) {
  const achado = /\/watch\/(\d+)/.exec(caminho || '')
  return achado === null ? null : achado[1]
}

/**
 * "T2:E1", "S2:E1", "Temporada 2: Episódio 1" → { temporada, episodio }.
 *
 * As grafias que a Netflix usa de verdade, e só elas. Inventar padrões "que
 * poderiam existir" só cria formas novas de casar errado — a lista curta é a
 * mesma decisão que `_PADROES_DE_EPISODIO` tomou no backend.
 */
const PADROES = [
  // "T2:E1", "S2 E1", "S02E04". O separador é opcional QUANDO há um "E"
  // depois — em "S02E04" o próprio "E" separa. E o primeiro grupo é `[ST]` e
  // não `[STE]`: "E1" sozinho não é temporada nenhuma.
  /\b[ST](\d{1,2})\s*(?:[:x\s-]\s*E?|E)P?\s*(\d{1,3})\b/i,
  /\b(?:temporada|season)\s*(\d{1,2}).{0,4}(?:epis[oó]dio|episode)\s*(\d{1,3})\b/i,
  /\b(\d{1,2})x(\d{2,3})\b/,
]

/**
 * "E1", "EP12" — o episódio SEM a temporada junto.
 *
 * É como a Netflix escreve quando já se sabe em que temporada se está: o
 * player mostra "E1" e mais nada. Medido em 26/08/2026, com Breaking Bad
 * tocando.
 *
 * Sem este reconhecimento, "E1" não casava com padrão nenhum e caía como NOME
 * do episódio — perdendo as duas coisas de uma vez: o número não ficava
 * estruturado, e o nome de verdade ("Piloto") era descartado porque a vaga já
 * estava ocupada.
 */
const SO_EPISODIO = /^E(?:P|PIS[OÓ]DIO)?\s*(\d{1,3})$/i

/** "T2", "Temporada 2" — a temporada sozinha, no bloco dela. */
const SO_TEMPORADA = /^(?:T|S|TEMPORADA|SEASON)\s*(\d{1,2})$/i

function soEpisodio(texto) {
  if (typeof texto !== 'string') return null
  const achado = SO_EPISODIO.exec(texto.trim())
  if (achado === null) return null
  const numero = Number(achado[1])
  return numero >= 1 && numero <= 999 ? numero : null
}

function soTemporada(texto) {
  if (typeof texto !== 'string') return null
  const achado = SO_TEMPORADA.exec(texto.trim())
  if (achado === null) return null
  const numero = Number(achado[1])
  return numero >= 1 && numero <= 50 ? numero : null
}

function temporadaEEpisodio(texto) {
  if (typeof texto !== 'string' || texto === '') return null
  for (const padrao of PADROES) {
    const achado = padrao.exec(texto)
    if (achado === null) continue
    const temporada = Number(achado[1])
    const episodio = Number(achado[2])
    // Zero não existe em nenhuma das duas contagens; número alto demais é ano
    // ou pedaço do nome.
    if (temporada >= 1 && temporada <= 50 && episodio >= 1 && episodio <= 999) {
      return { temporada, episodio }
    }
  }
  return null
}

function texto(no) {
  if (no === null || no === undefined) return null
  const bruto = (no.textContent || '').replace(/\s+/g, ' ').trim()
  return bruto === '' ? null : bruto
}

/**
 * A barra de título do player.
 *
 * `data-uia` é o atributo que a Netflix usa para a automação de teste dela
 * própria, e por isso é o mais estável que a página oferece — bem mais do que
 * as classes, que são geradas e mudam a cada build.
 *
 * Numa série o bloco tem três partes: a obra num `h4`, o "T2:E1" e o nome do
 * episódio. Num filme só a primeira existe.
 */
function daBarraDeTitulo(raiz) {
  const bloco = raiz.querySelector('[data-uia="video-title"]')
  if (bloco === null) return null

  const obra = texto(bloco.querySelector('h4'))
  // Os irmãos do `h4`, na ordem em que a página os põe.
  const partes = []
  for (const filho of bloco.children) {
    if (filho.tagName === 'H4') continue
    const conteudo = texto(filho)
    if (conteudo !== null) partes.push(conteudo)
  }

  // Sem `h4` o bloco inteiro costuma ser o nome do filme.
  if (obra === null) {
    const tudo = texto(bloco)
    return tudo === null ? null : { workTitle: tudo }
  }

  const resultado = { workTitle: obra }
  for (const parte of partes) {
    const numeros = temporadaEEpisodio(parte)
    if (numeros !== null) {
      resultado.seasonNumber = numeros.temporada
      resultado.episodeNumber = numeros.episodio
      continue
    }
    // Os dois separados, que é como a Netflix escreve na maior parte do tempo.
    const episodio = soEpisodio(parte)
    if (episodio !== null) {
      resultado.episodeNumber = episodio
      continue
    }
    const temporada = soTemporada(parte)
    if (temporada !== null) {
      resultado.seasonNumber = temporada
      continue
    }
    // O que sobra é NOME. Reconhecer os números antes é o que devolve a vaga
    // ao nome de verdade — antes "E1" a ocupava e "Piloto" era descartado.
    if (resultado.episodeTitle === undefined) resultado.episodeTitle = parte
  }
  return resultado
}

/**
 * O título da aba, quando ela diz alguma coisa.
 *
 * Em `/watch` costuma ser só "Netflix" — e é justamente por isso que este
 * arquivo existe. Mas nas páginas de detalhe a Netflix escreve
 * "Assistir Sherlock | Site oficial da Netflix", e daí sai o nome da obra.
 * Segunda estratégia, nunca a primeira.
 */
const RUIDO_DO_TITULO = [
  /^\(\d+\)\s*/,
  /^assistir\s+/i,
  /^watch\s+/i,
  /\s*\|\s*site oficial d[ao]\s+netflix\s*$/i,
  /\s*\|\s*netflix official site\s*$/i,
  /\s*[-|]\s*netflix\s*$/i,
]

function doTituloDaAba(titulo) {
  let limpo = (titulo || '').trim()
  for (const padrao of RUIDO_DO_TITULO) limpo = limpo.replace(padrao, '').trim()
  if (limpo === '' || /^netflix$/i.test(limpo)) return null

  // "Sherlock: Season 2: Um Escândalo em Belgravia" — a forma com dois-pontos,
  // que é como a Netflix escreve quando escreve.
  //
  // Repare no que ela NÃO traz: o número do episódio. "Season 2" diz a
  // temporada e nada mais, e o nome do episódio não carrega número. Devolver
  // `episodeNumber` aqui seria inventar — e um "E1" chutado é pior do que
  // número nenhum, porque a pessoa acredita nele.
  const pedacos = limpo.split(':').map((p) => p.trim()).filter((p) => p !== '')
  if (pedacos.length >= 2) {
    const soTemporada = /^(?:season|temporada)\s*(\d{1,2})$/i
    let temporada = null
    const restantes = []
    for (const pedaco of pedacos) {
      const achado = soTemporada.exec(pedaco)
      if (achado !== null) temporada = Number(achado[1])
      else restantes.push(pedaco)
    }
    if (temporada !== null && restantes.length >= 1) {
      return {
        workTitle: restantes[0],
        episodeTitle: restantes.length > 1 ? restantes[restantes.length - 1] : null,
        seasonNumber: temporada,
      }
    }
  }

  // "Sherlock: T2:E1: Um Escândalo" — quando os DOIS números estão lá.
  const numeros = temporadaEEpisodio(limpo)
  if (numeros !== null && pedacos.length >= 2) {
    const resultado = {
      workTitle: pedacos[0],
      seasonNumber: numeros.temporada,
      episodeNumber: numeros.episodio,
    }
    const ultimo = pedacos[pedacos.length - 1]
    if (temporadaEEpisodio(ultimo) === null) resultado.episodeTitle = ultimo
    return resultado
  }
  // Sem números: "Season 2" no fim ainda diz menos que o nome da série.
  const semTemporada = limpo
    .replace(/\s*[-–—:]?\s+(?:season|temporada)\s*\d+\s*$/i, '')
    .trim()
  return { workTitle: semTemporada === '' ? limpo : semTemporada }
}

/**
 * O que a página sabe do que está tocando. `null` quando não sabe nada.
 *
 * A ordem é a da confiança: a barra do player descreve o que ESTÁ tocando; o
 * título da aba descreve a PÁGINA, que pode ser a de detalhe de outra obra.
 * Nunca o contrário.
 */
/**
 * A última leitura boa, presa ao id da reprodução.
 *
 * A barra `data-uia="video-title"` só existe enquanto os controles estão na
 * tela — o mesmo defeito do Disney+, e eu tinha dado lembrança só a ele.
 *
 * Funcionava por acidente: o estado da ponte herda `workTitle` entre
 * batimentos, então o nome sobrevivia enquanto a sessão sobrevivesse. Mas essa
 * memória é do SERVIDOR, e ela zera quando ele reinicia. Medido em 27/08/2026,
 * logo depois de um restart com Breaking Bad tocando:
 *
 *     host.log   tem=pageId+active      sem workTitle
 *     cartão     "Netflix"              sem episódio
 *
 * Aqui a lembrança é da PÁGINA, e ela sobrevive ao servidor. Presa ao
 * `/watch/<id>`, que muda quando o episódio muda — então o episódio seguinte
 * descarta a lembrança do anterior sozinho.
 */
let lembrancaDaNetflix = null

function lerNetflix(documento = document, local = location) {
  const id = idDaPagina(local.pathname)
  // O título da aba só descreve uma OBRA nas páginas de obra.
  //
  // Em `/browse` ele é o nome da SEÇÃO, e a vitrine da home toca um trailer de
  // quarenta segundos enquanto isso. Medido em 25/08/2026, com o diagnóstico ao
  // vivo e o Fight Club aberto noutra aba:
  //
  //   NETFLIX playing pos=0.0/47.7   workTitle='Home'        <- a vitrine
  //   NETFLIX paused  pos=222/8352   workTitle='Fight Club'  <- o filme
  //
  // "Home" ia para o backend como nome de obra. Só não virou uma linha de
  // histórico chamada "Home" porque `_titulo_generico` a barrou do outro lado —
  // e depender disso é depender de uma lista de palavras que nunca vai estar
  // completa. A página sabe que não é uma obra; ela é quem tem de dizer.
  const paginaDeObra = /\/(watch|title)\//.test(local.pathname || '')
  const achado = daBarraDeTitulo(documento)
    || (paginaDeObra ? doTituloDaAba(documento.title) : null)

  // Outra reprodução: a lembrança da anterior não vale mais. Descartar ANTES
  // de ler é o que impede afirmar o episódio errado durante os segundos em que
  // a barra da nova ainda não apareceu.
  if (lembrancaDaNetflix !== null && lembrancaDaNetflix.id !== id) {
    lembrancaDaNetflix = null
  }

  const lido = achado ?? (lembrancaDaNetflix === null ? null : lembrancaDaNetflix.dados)
  if (achado !== null && id !== null) lembrancaDaNetflix = { id, dados: achado }

  if (lido === null) {
    // Sem nome nenhum. O id ainda é uma identidade de reprodução válida, e
    // devolvê-lo sozinho é diferente de devolver nada: a Fase 11 distingue
    // episódio retomado de episódio seguinte só com ele.
    return id === null ? null : { pageId: id }
  }

  return {
    workTitle: lido.workTitle ?? null,
    episodeTitle: lido.episodeTitle ?? null,
    seasonNumber: lido.seasonNumber ?? null,
    episodeNumber: lido.episodeNumber ?? null,
    pageId: id,
  }
}

/** Só para os testes: a lembrança não pode vazar de um caso para o outro. */
function esquecerLembrancaDaNetflix() {
  lembrancaDaNetflix = null
}

/** Duas leituras descrevem a mesma coisa? Serve para emitir MEDIA_CHANGED. */
function mesmaMetadata(uma, outra) {
  if (uma === null || outra === null) return uma === outra
  const campos = ['workTitle', 'episodeTitle', 'seasonNumber', 'episodeNumber', 'pageId']
  return campos.every((campo) => (uma[campo] ?? null) === (outra[campo] ?? null))
}

/**
 * O registro de adapters, por hostname.
 *
 * A regra permanente do Master Loop continua valendo — "não criar adapters sem
 * necessidade comprovada" —, e a palavra que manda nela é COMPROVADA. A versão
 * anterior deste comentário dizia que "Prime Video, Disney+, Max e YouTube já
 * nomeiam a obra na janela, então não precisam de adapter". Isso nunca foi
 * medido: foi suposto, e estava errado.
 *
 * Medido no Disney+ em 26/08/2026, com Gavião Arqueiro T1:E1 tocando:
 *
 *     document.title            "Gavião Arqueiro | Disney+"   só a obra
 *     navigator.mediaSession    vazio, playbackState "none"
 *     «title-bug» ▸ .title-btn  "Gavião Arqueiro" + "T1:E1 Nunca Conheça..."
 *
 * A obra chega pela janela, sim — e o episódio e a temporada NÃO chegam por
 * fonte nenhuma do Windows. Era esse o defeito que fazia o Disney+ gravar
 * série sem T e sem E enquanto a Netflix gravava as duas: não era falta de
 * dado, era falta de adapter. Ver `disney.js`.
 *
 * Prime Video e Max seguem sem adapter porque ainda não foram medidos, e não
 * porque se saiba que eles não precisam. A diferença entre as duas frases é o
 * que este comentário passou a existir para guardar.
 *
 * As funções são chamadas por dentro de uma seta em vez de referenciadas
 * direto: cada adapter mora no seu arquivo, e um `ler: lerDisney` aqui seria
 * avaliado na carga deste — quebrando com `ReferenceError` se a ordem do
 * manifesto mudasse. A seta só resolve o nome na hora de usar.
 */
const ADAPTERS = [
  {
    casa: (host) => /(^|\.)netflix\.com$/.test(host),
    ler: (documento, local) => lerNetflix(documento, local),
  },
  {
    casa: (host) => /(^|\.)disneyplus\.com$/.test(host),
    ler: (documento, local) => lerDisney(documento, local),
  },
  {
    // O Prime também reproduz em `amazon.com` — é o mesmo player, e
    // `plataforma_do_host` no backend já trata os dois como PRIME_VIDEO. O
    // adapter só afirma alguma coisa quando acha o SDK do player e um `<video>`
    // com imagem, então a loja da Amazon não produz leitura nenhuma.
    casa: (host) => /(^|\.)(primevideo\.com|amazon\.com(\.br)?)$/.test(host),
    ler: (documento, local) => lerPrime(documento, local),
  },
  {
    casa: (host) => /(^|\.)(hbomax\.com|max\.com)$/.test(host),
    ler: (documento, local) => lerMax(documento, local),
  },
]

function lerMetadata(documento = document, local = location) {
  const host = (local.hostname || '').toLowerCase()
  for (const adapter of ADAPTERS) {
    if (adapter.casa(host)) {
      try {
        return adapter.ler(documento, local)
      } catch {
        // DOM hostil não pode derrubar o content script. Sem metadata é um
        // estado que o resto do sistema já sabe tratar.
        return null
      }
    }
  }
  return null
}

// Sem `export`: content script declarado no manifesto NÃO é módulo, e um
// `import`/`export` aqui é erro de sintaxe — a aba fica sem script e nada
// acusa. Mesma decisão de `video-observer.js`, e o teste alcança estas funções
// do mesmo jeito que alcança `criarObservador`: avaliando o arquivo real.
