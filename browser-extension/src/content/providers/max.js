/**
 * Fase 10 — o que só a página do Max sabe.
 *
 * ## O serviço em que a janela MENTE
 *
 * Os outros serviços ou nomeiam a obra na janela, ou não dizem nada. O Max faz
 * a terceira coisa, que é a pior: ele publica o nome do EPISÓDIO como se fosse
 * o da obra. Medido em 26/08/2026, com Lanternas T1 Ep.2 tocando:
 *
 *     document.title   "⁨Trust Fall⁩ • HBO Max"
 *
 * "Trust Fall" é o episódio — o mesmo "Salto no Escuro" que a página mostra em
 * português. A série chama-se "Lanternas", e a janela nunca disse isso.
 *
 * É o defeito que `PLATAFORMAS_COM_OBRA_NA_JANELA` existe para conter, e ele
 * já custou caro antes: em 18/08/2026, com Ben 10 tocando, a janela publicou
 * "⁨Fame⁩ • HBO Max" e o cartão anunciou que estava tocando algo chamado
 * "Fame". Conter não é resolver — sem adapter, o nome da série simplesmente
 * não existia em fonte nenhuma.
 *
 * ## O que a página entrega, e é generoso
 *
 *     [data-testid="player-ux-asset-title"]     "Lanternas"          a série
 *     [data-testid="player-ux-season-episode"]  "T1 Ep.2:"
 *     [data-testid="player-ux-asset-subtitle"]  "Salto no Escuro"    o episódio
 *
 * Três campos separados, com `data-testid` semânticos — `player-ux-*` é nome
 * escolhido, não gerado como as classes ao lado
 * (`Title-Fuse-Web-Play__sc-k9fw09-5`). E sem Shadow DOM nenhum.
 *
 * Há ainda um rótulo de acessibilidade com tudo junto, que serve de rede:
 *
 *     "Lanternas, Temporada 1 Episódio 2, Salto no Escuro"
 *
 * ## A armadilha do "Ep." com ponto
 *
 * "T1 Ep.2:" NÃO casa com o padrão que os outros adapters usam. O ponto entre
 * "Ep" e "2" quebra a expressão, e o resultado seria silencioso: temporada e
 * episódio descartados, com o texto inteiro virando nome de episódio.
 *
 * Reusar a regex dos outros arquivos sem medir esta grafia teria produzido
 * exatamente o tipo de falha que não acusa nada.
 *
 * ## O que este arquivo NÃO faz
 *
 * Tempo. O `<video>` do Max é honesto, e está medido:
 *
 *     currentTime 46.5   duration 3437.22   seekable [0, 3437.2]
 *
 * O "-56:31" que o player desenha bate com `3437 − 46,5`. Nada de `Infinity`,
 * nada de janela DASH. Declarar tempo aqui criaria disputa onde não há
 * defeito — é a mesma decisão do adapter do Prime, e pelo mesmo motivo.
 *
 * E não guarda lembrança: os elementos ficam no DOM com os controles
 * escondidos. Só o Disney+ remove o overlay inteiro.
 */

/* eslint-disable no-unused-vars */

/**
 * "T1 Ep.2:", "S1 E2", "T1:E2" → { temporada, episodio }.
 *
 * A primeira entrada é a grafia MEDIDA do Max, e ela existe separada por causa
 * do `\.?` depois do "Ep" — sem ele, "T1 Ep.2:" não casa com nada. As outras
 * duas são as formas que os outros serviços usam, mantidas porque o Max
 * traduz a interface e a grafia pode mudar com o idioma da conta.
 */
const PADROES_MAX = [
  /\b[ST](\d{1,2})\s*[:\s-]*\s*(?:EP?|EPIS[OÓ]DIO|EPISODE)\.?\s*(\d{1,3})\b/i,
  /\b(?:temporada|season)\s*(\d{1,2}).{0,4}(?:epis[oó]dio|episode)\s*(\d{1,3})\b/i,
  /\b(\d{1,2})x(\d{2,3})\b/,
]

function temporadaEEpisodioMax(texto) {
  if (typeof texto !== 'string' || texto === '') return null
  for (const padrao of PADROES_MAX) {
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

function textoMax(documento, seletor) {
  let no
  try {
    no = documento.querySelector(seletor)
  } catch {
    return null
  }
  if (no === null) return null
  // O `:` do fim de "T1 Ep.2:" é pontuação de layout, não dado.
  const bruto = (no.textContent || '').replace(/\s+/g, ' ').trim().replace(/[:\s]+$/, '')
  return bruto === '' ? null : bruto
}

/**
 * A rede: o rótulo de acessibilidade, que traz os três campos numa string.
 *
 * "Lanternas, Temporada 1 Episódio 2, Salto no Escuro"
 *
 * Existe porque os `data-testid` são contrato de teste da HBO, não nosso — e
 * o dia em que eles mudarem não pode ser o dia em que o Max volta a publicar
 * o nome do episódio como se fosse a série. Este rótulo é escrito para leitor
 * de tela, e texto de acessibilidade costuma sobreviver a redesenho.
 */
function doRotuloAcessivel(documento) {
  let candidatos
  try {
    candidatos = documento.querySelectorAll('[class*="VisiblyHidden"]')
  } catch {
    return null
  }
  for (const no of candidatos) {
    const texto = (no.textContent || '').replace(/\s+/g, ' ').trim()
    const numeros = temporadaEEpisodioMax(texto)
    if (numeros === null) continue
    const partes = texto.split(',').map((p) => p.trim()).filter((p) => p !== '')
    // "Obra, Temporada N Episódio M, Nome" — três pedaços, nesta ordem. Menos
    // do que isso não dá para separar obra de episódio, e chutar qual é qual
    // poria o nome do episódio na linha da obra: o defeito que este arquivo
    // inteiro existe para desfazer.
    if (partes.length < 3) return null
    return {
      obra: partes[0],
      temporada: numeros.temporada,
      episodio: numeros.episodio,
      nome: partes[partes.length - 1],
    }
  }
  return null
}

/** O id da reprodução: `/video/watch/ce67d50b-0a2d-...`. Muda por episódio. */
function idDaPaginaMax(caminho) {
  const achado = /\/watch\/([0-9a-f][0-9a-f-]{7,})/i.exec(caminho || '')
  return achado === null ? null : achado[1]
}

function lerMax(documento = document, local = location) {
  const id = idDaPaginaMax(local.pathname || '')
  // Fora de `/video/watch` não há reprodução: é catálogo ou página de detalhe.
  if (id === null) return null

  const obra = textoMax(documento, '[data-testid="player-ux-asset-title"]')
  const marcador = textoMax(documento, '[data-testid="player-ux-season-episode"]')
  const nome = textoMax(documento, '[data-testid="player-ux-asset-subtitle"]')

  if (obra !== null) {
    const resultado = {
      workTitle: obra,
      episodeTitle: nome,
      seasonNumber: null,
      episodeNumber: null,
      pageId: id,
    }
    const numeros = temporadaEEpisodioMax(marcador ?? '')
    if (numeros !== null) {
      resultado.seasonNumber = numeros.temporada
      resultado.episodeNumber = numeros.episodio
    }
    return resultado
  }

  const rede = doRotuloAcessivel(documento)
  if (rede !== null) {
    return {
      workTitle: rede.obra,
      episodeTitle: rede.nome,
      seasonNumber: rede.temporada,
      episodeNumber: rede.episodio,
      pageId: id,
    }
  }

  // Sem nome, o id ainda é identidade de reprodução válida — e no Max ele é
  // por EPISÓDIO, então distingue "retomado" de "próximo" sozinho.
  //
  // Devolver isto em vez de `null` importa mais aqui do que nos outros
  // serviços: sem adapter, o nome que chega é o do episódio vindo da janela, e
  // `PLATAFORMAS_COM_OBRA_NA_JANELA` o barra como obra. O resultado é uma
  // reprodução conhecida e sem nome — que é o certo, e é melhor do que
  // "Trust Fall" na linha da série.
  return { pageId: id }
}

// Sem `export`: content script declarado no manifesto NÃO é módulo, e um
// `import`/`export` aqui é erro de sintaxe — a aba fica sem script e nada
// acusa. Mesma decisão de `netflix.js`, `disney.js` e `prime.js`.
