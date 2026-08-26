import { act, fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'

import { NowPlayingCard } from './NowPlayingCard'


const sessao = {
  title: 'Duna: Parte Dois',
  artist: null,
  app: 'Chrome',
  platform: null,
  playing: true,
  positionSeconds: 90,
  durationSeconds: 3600,
  thumbnailId: null,
}

function renderCard(overrides = {}, credentials: { deviceId: string; token: string } | null = null) {
  return render(
    <NowPlayingCard
      session={{ ...sessao, ...overrides }}
      apiBaseUrl="http://192.168.0.1:8100"
      credentials={credentials}
    />,
  )
}


describe('NowPlayingCard', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: false })))
  })

  it('mostra o que está tocando e o progresso', () => {
    renderCard()

    expect(screen.getByText('Duna: Parte Dois')).toBeTruthy()
    expect(screen.getByText('1:30')).toBeTruthy()
    expect(screen.getByText('1:00:00')).toBeTruthy()
  })

  it('diz pausado quando está pausado', () => {
    renderCard({ playing: false })

    expect(screen.getByText(/Pausado/)).toBeTruthy()
  })

  it('expõe o progresso para leitor de tela', () => {
    renderCard()

    const barra = screen.getByRole('progressbar', { name: 'Progresso' })
    expect(barra.getAttribute('aria-valuenow')).toBe('90')
    expect(barra.getAttribute('aria-valuemax')).toBe('3600')
  })

  it('não mostra barra quando a duração é desconhecida', () => {
    // Rádio e transmissão ao vivo não têm fim; uma barra ali seria invenção.
    renderCard({ durationSeconds: null })

    expect(screen.queryByRole('progressbar')).toBeNull()
  })

  it('não busca a capa sem credenciais', () => {
    // A capa é recurso autenticado; pedir sem token só geraria 401.
    renderCard({ thumbnailId: 'abc123' }, null)

    expect(fetch).not.toHaveBeenCalled()
  })

  it('busca a capa com os cabeçalhos do pareamento', () => {
    renderCard({ thumbnailId: 'abc123' }, { deviceId: 'd1', token: 't1' })

    expect(fetch).toHaveBeenCalledWith(
      'http://192.168.0.1:8100/now-playing/thumbnail/abc123',
      { headers: { 'X-Device-Id': 'd1', 'X-Device-Token': 't1' } },
    )
  })
})

describe('NowPlayingCard minutagem ao vivo', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: false })))
  })

  it('mostra o tempo decorrido mesmo sem duração conhecida', () => {
    // Transmissão ao vivo não tem fim. Antes a minutagem sumia inteira nesse
    // caso — o cartão ficava sem nenhum tempo, que é justamente o que o
    // usuário queria ver.
    renderCard({ positionSeconds: 3725, durationSeconds: null })

    expect(screen.getByText('1:02:05')).toBeTruthy()
    expect(screen.getByText('ao vivo')).toBeTruthy()
  })

  it('não desenha barra sem duração, porque não há proporção a mostrar', () => {
    renderCard({ positionSeconds: 3725, durationSeconds: null })

    expect(screen.queryByRole('progressbar')).toBeNull()
  })

  it('não inventa 0:00 quando a posição é desconhecida', () => {
    // A linha do tempo congelada do Chrome deixa a posição nula. Mostrar
    // "0:00 / 2:38:52" afirmaria que o filme está no começo.
    renderCard({ positionSeconds: null, durationSeconds: 9532 })

    expect(screen.queryByText('0:00')).toBeNull()
    expect(screen.queryByRole('progressbar')).toBeNull()
  })

  it('com posição e duração, mostra os dois e a barra', () => {
    renderCard({ positionSeconds: 4706, durationSeconds: 9532 })

    expect(screen.getByText('1:18:26')).toBeTruthy()
    expect(screen.getByText('2:38:52')).toBeTruthy()
    expect(screen.getByRole('progressbar')).toBeTruthy()
  })

  it('com a posição travada, ainda mostra a minutagem', () => {
    // O servidor manda a posição marcada como velha em vez de mandar nula. A
    // versão anterior sumia com o bloco inteiro no meio do filme só porque o
    // serviço demorou a publicar o próximo valor.
    renderCard({ positionSeconds: 4706, durationSeconds: 9532, positionStale: true })

    expect(screen.getByText('1:18:26')).toBeTruthy()
    expect(screen.getByRole('progressbar')).toBeTruthy()
  })

  it('com a posição travada, o tempo não anda sozinho', () => {
    // Contar a partir de um número que o serviço parou de atualizar seria
    // inventar um avanço que ninguém mediu.
    vi.useFakeTimers()
    try {
      renderCard({ positionSeconds: 4706, durationSeconds: 9532, positionStale: true })
      act(() => { vi.advanceTimersByTime(10_000) })

      expect(screen.getByText('1:18:26')).toBeTruthy()
    } finally {
      vi.useRealTimers()
    }
  })

  it('sem o aviso, o tempo continua andando sozinho', () => {
    // A contagem local é o que evita uma mensagem por segundo por celular;
    // ela não pode morrer junto com a correção.
    vi.useFakeTimers()
    try {
      renderCard({ positionSeconds: 4706, durationSeconds: 9532 })
      act(() => { vi.advanceTimersByTime(10_000) })

      expect(screen.queryByText('1:18:26')).toBeNull()
      expect(screen.getByText('1:18:36')).toBeTruthy()
    } finally {
      vi.useRealTimers()
    }
  })
})

describe('NowPlayingCard capa', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: false })))
  })

  it('usa o pôster do catálogo quando o aplicativo não publica capa', () => {
    // O navegador não publica capa nenhuma, então todo filme ficava com o
    // disco cinza. O catálogo já sabe achar o título; falta usar o pôster.
    const { container } = renderCard({
      thumbnailId: null,
      posterUrl: 'https://image.tmdb.org/t/p/w185/duna.jpg',
    })

    const imagem = container.querySelector('.now-playing__cover img')
    expect(imagem?.getAttribute('src')).toBe('https://image.tmdb.org/t/p/w185/duna.jpg')
  })

  it('sem capa e sem pôster, mostra o disco em vez de uma imagem quebrada', () => {
    const { container } = renderCard({ thumbnailId: null, posterUrl: null })

    expect(container.querySelector('.now-playing__cover img')).toBeNull()
  })

  it('usa o logo do serviço quando não há capa nem pôster', () => {
    // Um jogo ao vivo no YouTube não está no catálogo de filmes e o navegador
    // não publica capa. O disco genérico não dizia nada; o logo diz de onde o
    // que está tocando veio.
    const { container } = renderCard({ platform: 'YOUTUBE', title: 'Flamengo x Palmeiras' })

    const logo = container.querySelector('.now-playing__logo')
    expect(logo?.getAttribute('src')).toBe('/platforms/youtube.svg')
  })

  it('a capa do aplicativo continua vencendo o logo', () => {
    const { container } = renderCard({
      platform: 'NETFLIX',
      posterUrl: 'https://image.tmdb.org/t/p/w185/duna.jpg',
    })

    expect(container.querySelector('.now-playing__logo')).toBeNull()
    expect(container.querySelector('.now-playing__cover img')?.getAttribute('src'))
      .toBe('https://image.tmdb.org/t/p/w185/duna.jpg')
  })

  it('cai para o logo quando o pôster não carrega', () => {
    // Só na rede local, sem internet, o celular não alcança image.tmdb.org e o
    // navegador desenharia o ícone de imagem quebrada — que parece defeito do
    // controle, não do link.
    const { container } = renderCard({
      platform: 'NETFLIX',
      posterUrl: 'https://image.tmdb.org/t/p/w185/duna.jpg',
    })

    fireEvent.error(container.querySelector('.now-playing__cover img')!)

    expect(container.querySelector('.now-playing__logo')?.getAttribute('src'))
      .toBe('/platforms/netflix.svg')
  })

  it('nunca mostra o identificador de pacote no lugar do nome do serviço', () => {
    // Medido na tela: a API de mídia do Windows devolve o identificador do
    // pacote, e "SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify" apareceu inteiro
    // ao lado de "Tocando agora".
    renderCard({
      app: 'SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify',
      platform: 'SPOTIFY',
    })

    expect(screen.queryByText(/SpotifyAB/)).toBeNull()
    expect(screen.queryByText(/· Spotify$/)).not.toBeNull()
  })

  it('sem plataforma conhecida, um identificador de pacote não vira legenda', () => {
    renderCard({
      app: 'SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify',
      platform: null,
    })

    expect(screen.queryByText(/SpotifyAB/)).toBeNull()
    // Some a legenda inteira, mas o cartão segue dizendo o que faz.
    expect(screen.queryByText('Tocando agora')).not.toBeNull()
  })

  it('numa série, diz a série e o episódio', () => {
    // O cartão mostrava só uma das duas — e era o episódio, que sozinho não
    // diz nem que série é.
    renderCard({ title: 'Rick and Morty', episode: 'Campo dos Sonhos' })

    expect(screen.getByText('Rick and Morty')).toBeTruthy()
    expect(screen.getByText('Campo dos Sonhos')).toBeTruthy()
  })

  it('sem episódio, o artista continua no lugar dele', () => {
    renderCard({ title: 'Bohemian Rhapsody', artist: 'Queen', episode: null })

    expect(screen.getByText('Queen')).toBeTruthy()
  })
})

describe('o tempo decorrido não passa do fim', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: false })))
  })

  /**
   * O relato de 17/08/2026: "a visualização de tempo tá bugando".
   *
   * A barra era limitada a 100% e o NÚMERO não era. O contador roda no próprio
   * celular a partir da última posição recebida, e quando o site para de
   * publicar posição nova — que é o estado normal desta máquina, com a SMTC
   * pendurada — nada o segura. O episódio acaba, o contador continua, e a
   * tela mostra um decorrido maior que o total.
   */
  it('para no fim em vez de contar para sempre', () => {
    vi.useFakeTimers()
    try {
      render(
        <NowPlayingCard
          session={{ ...sessao, positionSeconds: 3590, durationSeconds: 3600 }}
          apiBaseUrl="http://192.168.0.1:8100"
          credentials={null}
        />,
      )

      // Um minuto de relógio depois do fim do que estava tocando.
      act(() => { vi.advanceTimersByTime(70_000) })

      // Decorrido e total marcam a mesma coisa: o fim. Antes o decorrido
      // marcava 1:01:00 num total de 1:00:00.
      const barra = screen.getByRole('progressbar')
      expect(barra.getAttribute('aria-valuenow')).toBe('3600')
      expect(screen.getAllByText('1:00:00')).toHaveLength(2)
      expect(screen.queryByText('1:01:00')).toBeNull()
    } finally {
      vi.useRealTimers()
    }
  })

  it('sem duração conhecida o tempo continua correndo', () => {
    vi.useFakeTimers()
    try {
      render(
        <NowPlayingCard
          session={{ ...sessao, positionSeconds: 10, durationSeconds: null }}
          apiBaseUrl="http://192.168.0.1:8100"
          credentials={null}
        />,
      )

      act(() => { vi.advanceTimersByTime(20_000) })

      // Transmissão ao vivo: não há fim para segurar o contador.
      expect(screen.getByText('0:30')).toBeTruthy()
      expect(screen.getByText('ao vivo')).toBeTruthy()
    } finally {
      vi.useRealTimers()
    }
  })
})

describe('quando o nome lido não é o da obra', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: false })))
  })

  /**
   * Medido em 18/08/2026 com Ben 10 tocando: a janela do Max publica
   * "⁨Fame⁩ • HBO Max", e "Fame" é o EPISÓDIO — o Max nunca publica o nome da
   * série. Com a API de mídia do Windows pendurada não sobra ninguém que saiba
   * dizer "Ben 10", e o cartão mostrava "Fame" no lugar da obra.
   */
  it('diz que é episódio em vez de fingir que é a obra', () => {
    render(
      <NowPlayingCard
        session={{ ...sessao, title: 'Fame', platform: 'MAX', titleIsWork: false }}
        apiBaseUrl="http://192.168.0.1:8100"
        credentials={null}
      />,
    )

    // O nome continua na tela: é a única pista do que está tocando.
    expect(screen.getByText('Fame')).toBeTruthy()
    // O que muda é a frase que o cartão monta em volta dele.
    expect(screen.getByText('Episódio · série não identificada')).toBeTruthy()
  })

  it('com a obra identificada, o episódio aparece normalmente', () => {
    render(
      <NowPlayingCard
        session={{
          ...sessao, title: 'Ben 10', episode: 'Fame',
          platform: 'MAX', titleIsWork: true,
        }}
        apiBaseUrl="http://192.168.0.1:8100"
        credentials={null}
      />,
    )

    expect(screen.getByText('Ben 10')).toBeTruthy()
    expect(screen.getByText('Fame')).toBeTruthy()
    expect(screen.queryByText('Episódio · série não identificada')).toBeNull()
  })

  it('sem o campo, nada muda para quem já funcionava', () => {
    render(
      <NowPlayingCard
        session={{ ...sessao, title: 'Duna', episode: null }}
        apiBaseUrl="http://192.168.0.1:8100"
        credentials={null}
      />,
    )

    expect(screen.getByText('Duna')).toBeTruthy()
    expect(screen.queryByText('Episódio · série não identificada')).toBeNull()
  })

  it('vira o ícone assim que o dedo sai, sem esperar o servidor', () => {
    // Medido em 25/08/2026: na Netflix o `playing` do servidor nunca vira
    // false — a API de mídia do Windows congela e o socorro pela janela manda
    // `true` chumbado. O ícone ficava em "Pausar" para sempre.
    const onTogglePlay = vi.fn()
    render(
      <NowPlayingCard
        session={{ ...sessao, playing: true }}
        apiBaseUrl="http://192.168.0.1:8100"
        credentials={null}
        onTogglePlay={onTogglePlay}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Pausar' }))

    expect(onTogglePlay).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: 'Continuar' })).toBeTruthy()
    expect(screen.getByText(/Pausado/)).toBeTruthy()
  })

  it('o servidor manda: quando ele contradiz, o palpite sai', () => {
    const { rerender } = render(
      <NowPlayingCard
        session={{ ...sessao, playing: true }}
        apiBaseUrl="http://192.168.0.1:8100"
        credentials={null}
        onTogglePlay={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Pausar' }))
    expect(screen.getByRole('button', { name: 'Continuar' })).toBeTruthy()

    // O servidor responde que continua tocando: ele é a autoridade.
    rerender(
      <NowPlayingCard
        session={{ ...sessao, playing: false }}
        apiBaseUrl="http://192.168.0.1:8100"
        credentials={null}
        onTogglePlay={vi.fn()}
      />,
    )
    rerender(
      <NowPlayingCard
        session={{ ...sessao, playing: true }}
        apiBaseUrl="http://192.168.0.1:8100"
        credentials={null}
        onTogglePlay={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: 'Pausar' })).toBeTruthy()
  })

  it('o palpite não atravessa a troca de obra', () => {
    const { rerender } = render(
      <NowPlayingCard
        session={{ ...sessao, playing: true }}
        apiBaseUrl="http://192.168.0.1:8100"
        credentials={null}
        onTogglePlay={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Pausar' }))
    expect(screen.getByRole('button', { name: 'Continuar' })).toBeTruthy()

    rerender(
      <NowPlayingCard
        session={{ ...sessao, title: 'Outra obra', playing: true }}
        apiBaseUrl="http://192.168.0.1:8100"
        credentials={null}
        onTogglePlay={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: 'Pausar' })).toBeTruthy()
  })
})
