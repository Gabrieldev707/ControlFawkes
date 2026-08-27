/**
 * Fase 10 — o adapter da Netflix.
 *
 * Gate: "Netflix fornece metadata sem depender da SMTC para nome da obra."
 *
 * O arquivo observado é um content script CLÁSSICO: sem `export`, porque
 * content script declarado no manifesto não é módulo. Ele é lido e avaliado
 * aqui do mesmo jeito que o Chrome o carrega — o teste exercita o arquivo real,
 * não uma cópia adaptada. Mesma forma de `video-observer.test.ts`.
 */

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { beforeEach, describe, expect, it } from 'vitest'


const FONTE = readFileSync(resolve(__dirname, 'netflix.js'), 'utf8')

type Metadata = {
  workTitle?: string | null
  episodeTitle?: string | null
  seasonNumber?: number | null
  episodeNumber?: number | null
  pageId?: string | null
} | null

function carregar<T>(nome: string): T {
  return new Function(`${FONTE}\nreturn ${nome}`)() as T
}

/**
 * Tudo de uma vez, e não um `carregar` por função.
 *
 * A lembrança do adapter é uma variável de módulo, e cada avaliação da fonte
 * cria um fechamento novo. Carregar `lerNetflix` e `esquecerLembrancaDaNetflix`
 * em chamadas separadas daria duas lembranças diferentes, e o esquecimento não
 * alcançaria a leitura — um caso vazaria no seguinte sem nada acusar.
 */
const api = carregar<{
  lerNetflix: (d: Document, l: { pathname: string }) => Metadata
  lerMetadata: (d: Document, l: { pathname: string; hostname: string }) => Metadata
  temporadaEEpisodio: (t: string) => { temporada: number; episodio: number } | null
  mesmaMetadata: (a: Metadata, b: Metadata) => boolean
  esquecerLembrancaDaNetflix: () => void
}>(
  '{ lerNetflix, lerMetadata, temporadaEEpisodio, mesmaMetadata,'
  + ' esquecerLembrancaDaNetflix }',
)

const { lerNetflix, lerMetadata, temporadaEEpisodio, mesmaMetadata } = api

/** A página, do jeito que a Netflix a monta. */
function montarBarra(partes: string[], obra?: string) {
  const bloco = document.createElement('div')
  bloco.setAttribute('data-uia', 'video-title')
  if (obra !== undefined) {
    const h4 = document.createElement('h4')
    h4.textContent = obra
    bloco.appendChild(h4)
  }
  for (const parte of partes) {
    const span = document.createElement('span')
    span.textContent = parte
    bloco.appendChild(span)
  }
  document.body.appendChild(bloco)
}

const emWatch = { pathname: '/watch/81234567', hostname: 'www.netflix.com' }


beforeEach(() => {
  document.body.innerHTML = ''
  document.title = 'Netflix'
  api.esquecerLembrancaDaNetflix()
})


describe('temporada e episódio', () => {
  it.each([
    ['T2:E1', 2, 1],
    ['S2:E1', 2, 1],
    ['S02E04', 2, 4],
    ['Temporada 3: Episódio 12', 3, 12],
    ['Season 1: Episode 2', 1, 2],
    ['2x04', 2, 4],
  ])('lê %s', (texto, temporada, episodio) => {
    expect(temporadaEEpisodio(texto)).toEqual({ temporada, episodio })
  })

  it.each([
    // Zero não existe em nenhuma das duas contagens.
    ['T0:E0'],
    // Um ano não é temporada.
    ['1985'],
    // Nome de episódio comum não pode virar número.
    ['Um Escândalo em Belgravia'],
    [''],
  ])('não inventa número em %s', (texto) => {
    expect(temporadaEEpisodio(texto)).toBeNull()
  })
})


describe('a barra de título do player', () => {
  it('lê série: obra, temporada, episódio e nome do episódio', () => {
    montarBarra(['T2:E1', 'Um Escândalo em Belgravia'], 'Sherlock')

    expect(lerNetflix(document, emWatch)).toEqual({
      workTitle: 'Sherlock',
      episodeTitle: 'Um Escândalo em Belgravia',
      seasonNumber: 2,
      episodeNumber: 1,
      pageId: '81234567',
    })
  })

  it('lê filme: só a obra, e nada de episódio inventado', () => {
    montarBarra([], 'Duna: Parte Dois')

    expect(lerNetflix(document, emWatch)).toEqual({
      workTitle: 'Duna: Parte Dois',
      episodeTitle: null,
      seasonNumber: null,
      episodeNumber: null,
      pageId: '81234567',
    })
  })

  it('a obra vem da barra mesmo com a aba dizendo só "Netflix"', () => {
    // O gate literal: em `/watch` a aba diz "Netflix" e a SMTC diz "Netflix".
    // Se o nome saísse de uma das duas, a Netflix nunca teria nome.
    document.title = 'Netflix'
    montarBarra(['T1:E1', 'Piloto'], 'Rick and Morty')

    expect(lerNetflix(document, emWatch)?.workTitle).toBe('Rick and Morty')
  })

  it('a barra vence o título da aba', () => {
    // A aba pode estar na página de detalhe de OUTRA obra enquanto o player
    // toca esta. Quem descreve o que está tocando é a barra.
    document.title = 'Assistir Outra Coisa | Site oficial da Netflix'
    montarBarra(['T1:E1', 'Piloto'], 'Rick and Morty')

    expect(lerNetflix(document, emWatch)?.workTitle).toBe('Rick and Morty')
  })

  it('sem h4, o bloco inteiro é o nome do filme', () => {
    montarBarra(['Duna'])

    expect(lerNetflix(document, emWatch)?.workTitle).toBe('Duna')
  })
})


describe('o título da aba, como segunda estratégia', () => {
  it('tira o enfeite da página de detalhe', () => {
    document.title = 'Assistir Sherlock | Site oficial da Netflix'

    expect(lerNetflix(document, { pathname: '/title/70158331' })?.workTitle)
      .toBe('Sherlock')
  })

  it('separa obra, temporada e episódio na forma com dois-pontos', () => {
    document.title = 'Sherlock: Season 2: Um Escândalo em Belgravia - Netflix'

    // `episodeNumber` é `null` de propósito: essa forma NÃO traz o número do
    // episódio. Chutar um "E1" seria pior do que não dizer nada.
    expect(lerNetflix(document, emWatch)).toEqual({
      workTitle: 'Sherlock',
      episodeTitle: 'Um Escândalo em Belgravia',
      seasonNumber: 2,
      episodeNumber: null,
      pageId: '81234567',
    })
  })

  it('com os dois números presentes, os dois saem', () => {
    document.title = 'Sherlock: T2:E1: Um Escândalo em Belgravia - Netflix'

    expect(lerNetflix(document, emWatch)).toMatchObject({
      workTitle: 'Sherlock',
      seasonNumber: 2,
      episodeNumber: 1,
    })
  })

  it('"Season 2" no fim não vira parte do nome da obra', () => {
    // O bug medido no histórico real: "sherlock season 2" com 27175 segundos
    // numa linha só, sem pôster, porque esse nome não é obra em catálogo
    // nenhum.
    document.title = 'Sherlock Season 2 - Netflix'

    expect(lerNetflix(document, emWatch)?.workTitle).toBe('Sherlock')
  })
})


describe('o piso que não depende de DOM', () => {
  it('sem nome nenhum, o id da URL ainda é identidade', () => {
    document.title = 'Netflix'

    expect(lerNetflix(document, emWatch)).toEqual({ pageId: '81234567' })
  })

  it('sem nome e sem /watch, não há o que dizer', () => {
    document.title = 'Netflix'

    expect(lerNetflix(document, { pathname: '/browse' })).toBeNull()
  })

  it('o id muda quando o episódio muda', () => {
    document.title = 'Netflix'
    const um = lerNetflix(document, { pathname: '/watch/81234567' })
    const outro = lerNetflix(document, { pathname: '/watch/81234568' })

    expect(mesmaMetadata(um, outro)).toBe(false)
  })
})


describe('o registro de adapters', () => {
  it('só responde por netflix.com', () => {
    montarBarra(['T1:E1', 'Piloto'], 'Rick and Morty')

    expect(lerMetadata(document, emWatch)?.workTitle).toBe('Rick and Morty')
    expect(lerMetadata(document, { ...emWatch, hostname: 'www.primevideo.com' })).toBeNull()
    // E o sufixo não pode casar por acaso.
    expect(lerMetadata(document, { ...emWatch, hostname: 'naonetflix.com' })).toBeNull()
  })

  it('DOM hostil não derruba o content script', () => {
    const explosivo = {
      title: 'Netflix',
      querySelector: () => { throw new Error('boom') },
    } as unknown as Document

    expect(lerMetadata(explosivo, emWatch)).toBeNull()
  })
})


describe('mudança de metadata', () => {
  it('a mesma leitura duas vezes é a mesma metadata', () => {
    montarBarra(['T1:E1', 'Piloto'], 'Rick and Morty')
    const antes = lerNetflix(document, emWatch)
    const depois = lerNetflix(document, emWatch)

    expect(mesmaMetadata(antes, depois)).toBe(true)
  })

  it('o episódio seguinte é metadata diferente', () => {
    montarBarra(['T1:E1', 'Piloto'], 'Rick and Morty')
    const primeiro = lerNetflix(document, emWatch)

    document.body.innerHTML = ''
    montarBarra(['T1:E2', 'Lawnmower Dog'], 'Rick and Morty')
    const segundo = lerNetflix(document, emWatch)

    expect(mesmaMetadata(primeiro, segundo)).toBe(false)
    // E a OBRA não mudou: é isso que a Fase 11 vai precisar distinguir.
    expect(primeiro?.workTitle).toBe(segundo?.workTitle)
  })
})


describe('a vitrine da home não é uma obra', () => {
  it('o nome da seção não vira workTitle', () => {
    // Medido em 25/08/2026: a vitrine da home toca um trailer de 40s e o
    // título da aba é "Home". Isso chegava ao backend como nome de obra.
    document.title = 'Home - Netflix'

    expect(lerNetflix(document, { pathname: '/browse' })).toBeNull()
  })

  it.each([['/'], ['/browse'], ['/latest'], ['/my-list']])(
    'nenhuma página de navegação (%s) nomeia obra',
    (caminho) => {
      document.title = 'Minha lista - Netflix'

      expect(lerNetflix(document, { pathname: caminho })).toBeNull()
    },
  )

  it('a página de detalhe continua nomeando a obra', () => {
    // O par: `/title/` descreve UMA obra, e o nome ali é dela.
    document.title = 'Assistir Sherlock | Site oficial da Netflix'

    expect(lerNetflix(document, { pathname: '/title/70158331' })?.workTitle)
      .toBe('Sherlock')
  })

  it('a barra do player vence mesmo fora de /watch', () => {
    // Se o player está montado, ele descreve o que TOCA — e isso vale mais que
    // o caminho da URL.
    document.title = 'Home - Netflix'
    montarBarra([], 'Fight Club')

    expect(lerNetflix(document, { pathname: '/browse' })?.workTitle).toBe('Fight Club')
  })
})



// ── A lembrança, e o restart que a expôs ──────────────────────────────────
//
// A barra `data-uia="video-title"` só existe enquanto os controles estão na
// tela — o mesmo defeito do Disney+, e eu tinha dado lembrança só a ele.
//
// Funcionava por acidente: o estado da ponte herda `workTitle` entre
// batimentos, então o nome sobrevivia enquanto a SESSÃO DO SERVIDOR
// sobrevivesse. Medido em 27/08/2026, logo depois de reiniciar o backend com
// Breaking Bad tocando:
//
//     host.log   tem=pageId+active      sem workTitle
//     cartão     "Netflix"              sem episódio
//
// A memória do servidor zera; a da página, não.

describe('a barra que some com os controles', () => {
  it('continua nomeando a obra depois de a barra sair do DOM', () => {
    montarBarra(['T2:E1', 'Um Escândalo'], 'Sherlock')
    expect(lerNetflix(document, emWatch)?.workTitle).toBe('Sherlock')

    // Controles escondidos: a Netflix remove o bloco inteiro.
    document.body.innerHTML = ''

    const lida = lerNetflix(document, emWatch)
    expect(lida?.workTitle).toBe('Sherlock')
    expect(lida?.episodeNumber).toBe(1)
  })

  it('esquece quando o EPISÓDIO muda, mesmo sem ler o novo', () => {
    // Repetir o anterior aqui poria o episódio errado no histórico — pior do
    // que não dizer nada.
    montarBarra(['T2:E1', 'Um Escândalo'], 'Sherlock')
    lerNetflix(document, emWatch)

    document.body.innerHTML = ''
    const outro = lerNetflix(document, { pathname: '/watch/99999999' })

    expect(outro).toEqual({ pageId: '99999999' })
  })

  it('a barra ATUAL vence a lembrança', () => {
    montarBarra(['T2:E1', 'Um Escândalo'], 'Sherlock')
    lerNetflix(document, emWatch)

    document.body.innerHTML = ''
    montarBarra(['T2:E2', 'Os Cães de Baskerville'], 'Sherlock')

    expect(lerNetflix(document, emWatch)?.episodeNumber).toBe(2)
  })

  it('sem nunca ter lido, devolve só a identidade', () => {
    expect(lerNetflix(document, emWatch)).toEqual({ pageId: '81234567' })
  })
})
