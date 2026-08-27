/**
 * SONDA DE DOM — leia e cole o resultado de volta.
 *
 * Como usar, com o EPISÓDIO TOCANDO (não a tela de catálogo):
 *   1. F12 na aba do serviço  ->  aba "Console"
 *   2. cole isto tudo e Enter
 *   3. copie o que sair (ele já sai como texto pronto)
 *
 * Ela só LÊ. Não clica, não muda nada, não manda nada para lugar nenhum.
 *
 * Existe porque os adapters têm de ser escritos do DOM MEDIDO. Escrever
 * seletor de cabeça foi o erro que quebrou Prime, Disney+ e Max enquanto a
 * Netflix — a única medida — funcionava.
 */
(() => {
  const LIMITE_TEXTO = 140
  const MAX_LINHAS = 60

  // Sinais de que um texto fala de episódio/temporada. Amplo de propósito:
  // aqui a sonda ainda não sabe o formato — descobri-lo é o objetivo.
  const CHEIRA_A_EPISODIO =
    /\b(?:S|T|E|EP|Season|Temporada|Epis[oó]dio|Episode)\s*\d{1,3}\b|\b\d{1,2}\s*x\s*\d{1,3}\b/i

  // Atributos que os serviços usam para a automação de teste deles próprios —
  // os mais estáveis que uma página oferece. As CLASSES são geradas e mudam a
  // cada build, então elas entram só como último recurso, truncadas.
  const ATRIBUTOS = [
    'data-testid', 'data-uia', 'data-automation-id', 'data-test-id',
    'data-cy', 'data-qa', 'aria-label', 'role', 'itemprop',
  ]

  const texto = (el) => (el.textContent || '').replace(/\s+/g, ' ').trim()

  const descrever = (el) => {
    const attrs = {}
    for (const nome of ATRIBUTOS) {
      const valor = el.getAttribute?.(nome)
      if (valor) attrs[nome] = valor.slice(0, 60)
    }
    const cls = (el.className && typeof el.className === 'string')
      ? el.className.slice(0, 70) : ''
    if (cls) attrs.class = cls
    return { tag: el.tagName.toLowerCase(), attrs, txt: texto(el).slice(0, LIMITE_TEXTO) }
  }

  const saida = {
    host: location.hostname,
    path: location.pathname,
    documentTitle: document.title,
    videos: [],
    og: {},
    jsonld: [],
    marcados: [],   // elementos com atributo de automação e texto curto
    episodicos: [], // qualquer texto da página que cheire a T/E
  }

  // ── o(s) <video> e o que existe em volta ────────────────────────────────
  for (const v of document.querySelectorAll('video')) {
    saida.videos.push({
      src: (v.currentSrc || v.src || '').slice(0, 60),
      currentTime: Number(v.currentTime?.toFixed(1)),
      duration: Number(v.duration?.toFixed(1)),
      paused: v.paused,
      // A cadeia de ancestrais nomeia o contêiner do player, e é por ela que
      // se encontra a barra de título sem varrer a página inteira.
      ancestrais: (() => {
        const cadeia = []
        let no = v.parentElement
        for (let i = 0; i < 8 && no; i += 1, no = no.parentElement) {
          cadeia.push(descrever(no))
        }
        return cadeia
      })(),
    })
  }

  // ── metadata declarada, que às vezes já entrega tudo de graça ───────────
  for (const m of document.querySelectorAll('meta[property], meta[name]')) {
    const chave = m.getAttribute('property') || m.getAttribute('name')
    if (/title|description|video|episode|season/i.test(chave)) {
      saida.og[chave] = (m.getAttribute('content') || '').slice(0, LIMITE_TEXTO)
    }
  }
  for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
    saida.jsonld.push((s.textContent || '').replace(/\s+/g, ' ').slice(0, 400))
  }

  // ── elementos com atributo de automação ────────────────────────────────
  const seletor = ATRIBUTOS.map((a) => `[${a}]`).join(',')
  const vistos = new Set()
  for (const el of document.querySelectorAll(seletor)) {
    const t = texto(el)
    // Texto vazio não diz nada; texto longo é um contêiner que engoliu a
    // página inteira e não é um rótulo.
    if (t === '' || t.length > LIMITE_TEXTO) continue
    if (vistos.has(t)) continue
    vistos.add(t)
    saida.marcados.push(descrever(el))
    if (saida.marcados.length >= MAX_LINHAS) break
  }

  // ── qualquer coisa que pareça temporada/episódio, com ou sem atributo ───
  const anda = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
  const jaVi = new Set()
  for (let no = anda.nextNode(); no; no = anda.nextNode()) {
    const t = (no.textContent || '').replace(/\s+/g, ' ').trim()
    if (t === '' || t.length > LIMITE_TEXTO) continue
    if (!CHEIRA_A_EPISODIO.test(t)) continue
    if (jaVi.has(t)) continue
    jaVi.add(t)
    const pai = no.parentElement
    saida.episodicos.push({ txt: t, pai: pai ? descrever(pai) : null })
    if (saida.episodicos.length >= MAX_LINHAS) break
  }

  const json = JSON.stringify(saida, null, 1)
  console.log(json)
  try {
    copy(json)
    console.log('%c>>> COPIADO. É só colar para o Claude.', 'color:#0a0;font-weight:bold')
  } catch {
    console.log('>>> selecione o JSON acima e copie.')
  }
  return `sonda: ${saida.videos.length} video(s), ${saida.marcados.length} marcados, ${saida.episodicos.length} episódicos`
})()
