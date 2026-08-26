import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ProfileScreen } from './ProfileScreen'


const credenciais = { deviceId: 'device-1', token: 'token-1' }

function perfilCom(continuar: unknown[]) {
  return {
    continuar,
    generos: [],
    plataformas: [],
    totalDeTitulos: continuar.length,
    totalDeSegundos: 400,
    conquistas: [],
    progresso: null,
  }
}

function responder(continuar: unknown[]) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => ({
    ok: true,
    json: async () => (
      String(url).includes('recommendations')
        ? { enabled: true, base: null, titles: [], filtrado: false }
        : perfilCom(continuar)
    ),
  })))
}

function renderizar() {
  return render(
    <ProfileScreen
      disabled={false}
      statusMessage=""
      statusError={false}
      credentials={credenciais}
      onResume={() => {}}
      onBack={() => {}}
    />,
  )
}


describe('ProfileScreen — continuar assistindo', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('diz quanto falta, que é a pergunta que dá nome à lista', async () => {
    // O backend já mandava `posicao` e `duracao` desde sempre e a tela ignorava
    // as duas: mostrava só o tempo somado, que responde "quanto disso eu vi" e
    // não "de onde eu continuo".
    responder([{
      titulo: 'A Casa do Dragão',
      platform: 'MAX',
      segundos: 4700,
      posicao: 2058,
      duracao: 4928,
      posterUrl: null,
    }])

    renderizar()

    expect(await screen.findByText('faltam 48 min')).toBeTruthy()
  })

  it('nunca mistura "quanto falta" com "quanto eu vi" na mesma faixa', async () => {
    // O defeito que este teste tranca: a versão anterior caía para o tempo
    // somado quando não havia posição, e aí um cartão dizia "faltam 48 min" e o
    // do lado dizia "1.1 h vistos" — duas perguntas diferentes no mesmo lugar
    // da tela, sem nada que dissesse qual das duas se está lendo.
    responder([
      {
        titulo: 'A Casa do Dragão',
        platform: 'MAX',
        segundos: 4700,
        posicao: 2058,
        duracao: 4928,
        posterUrl: null,
      },
      {
        titulo: 'Rick and Morty',
        platform: 'MAX',
        segundos: 4123,
        posicao: null,
        duracao: null,
        posterUrl: null,
      },
    ])

    renderizar()

    expect(await screen.findByText('faltam 48 min')).toBeTruthy()
    // O cartão sem posição não diz nada: vazio é "não sei", e um número que
    // responde outra pergunta seria pior do que o silêncio.
    expect(screen.queryByText(/vistos/)).toBeNull()
    expect(
      screen.getByRole('button', { name: 'Retomar Rick and Morty' }),
    ).toBeTruthy()
  })

  it('quanto falta chega a quem usa leitor de tela, no rótulo do botão', async () => {
    responder([{
      titulo: 'A Casa do Dragão',
      platform: 'MAX',
      segundos: 4700,
      posicao: 2058,
      duracao: 4928,
      posterUrl: null,
    }])

    renderizar()

    expect(
      await screen.findByRole('button', { name: 'Retomar A Casa do Dragão, faltam 48 min' }),
    ).toBeTruthy()
  })

  it('duração zerada não vira uma barra cheia', async () => {
    // Transmissão ao vivo chega com duração zero. Dividir por ela daria
    // infinito, e a barra apareceria cravada no fim de algo que não acabou.
    responder([{
      titulo: 'Libertadores 2026',
      platform: 'YOUTUBE',
      segundos: 1488,
      posicao: 600,
      duracao: 0,
      posterUrl: null,
    }])

    renderizar()

    expect(
      await screen.findByRole('button', { name: 'Retomar Libertadores 2026' }),
    ).toBeTruthy()
    expect(screen.queryByText(/falta/)).toBeNull()
  })

  it('mais de uma hora vira hora e minuto, não 92 min', async () => {
    responder([{
      titulo: 'Duna: Parte Dois',
      platform: 'MAX',
      segundos: 1200,
      posicao: 1200,
      duracao: 9720,
      posterUrl: null,
    }])

    renderizar()

    expect(await screen.findByText('faltam 2 h 22 min')).toBeTruthy()
  })
})

describe('continuar assistindo diz DE ONDE continuar', () => {
  /**
   * O relato de 18/08/2026: "continuar assistindo, mas continuar assistindo de
   * onde? não fala nada pro usuário".
   *
   * O cartão só tinha o que dizer quando havia posição — e numa série quase
   * nunca há, porque a posição é do EPISÓDIO e não da obra. Então a lista
   * mostrava o nome e mais nada.
   */
  it('mostra em que episódio a pessoa parou', async () => {
    responder([{
      titulo: 'Ben 10: Supremacia Alienígena', platform: 'MAX',
      segundos: 7850, posicao: null, duracao: null, posterUrl: null,
      episodio: 'Enganados',
    }])

    renderizar()

    expect(await screen.findByText('Ben 10: Supremacia Alienígena')).toBeTruthy()
    expect(screen.getByText('Enganados')).toBeTruthy()
  })

  it('o episódio entra no rótulo de quem usa leitor de tela', async () => {
    responder([{
      titulo: 'Ben 10', platform: 'MAX', segundos: 7850,
      posicao: null, duracao: null, posterUrl: null, episodio: 'Enganados',
    }])

    renderizar()

    expect(await screen.findByRole('button', { name: 'Retomar Ben 10, Enganados' }))
      .toBeTruthy()
  })

  /**
   * A trava que a primeira versão desta correção quebrou.
   *
   * O episódio vai numa LINHA PRÓPRIA, e não no lugar do tempo. O slot de
   * tempo responde "quanto falta" e só isso — pôr ali "8,5 h vistas" num
   * cartão e "faltam 20 min" no cartão do lado são duas perguntas diferentes
   * no mesmo lugar da tela, e quem lê não sabe qual está lendo.
   */
  it('o episódio não ocupa o lugar do tempo', async () => {
    responder([{
      titulo: 'Um Filme', platform: 'MAX', segundos: 3000,
      posicao: 3000, duracao: 6000, posterUrl: null, episodio: 'Um Episódio',
    }])

    const { container } = renderizar()

    await screen.findByText('Um Filme')
    // Os dois aparecem, cada um no seu lugar.
    expect(container.querySelector('.continuar-card__episodio')?.textContent)
      .toBe('Um Episódio')
    expect(container.querySelector('.continuar-card__tempo')?.textContent)
      .toContain('faltam')
  })

  it('sem episódio, o cartão não inventa uma linha vazia', async () => {
    responder([{
      titulo: 'Loki', platform: 'DISNEY_PLUS', segundos: 30444,
      posicao: null, duracao: null, posterUrl: null, episodio: null,
    }])

    const { container } = renderizar()

    await screen.findByText('Loki')
    expect(container.querySelector('.continuar-card__episodio')).toBeNull()
  })

  it('recarrega ao voltar para a aba', async () => {
    // Medido em 25/08/2026: a tela buscava uma vez e nunca mais. Um episódio
    // inteiro depois, o cartão ainda anunciava a posição do anterior — e nada
    // dizia que aquilo era um retrato velho.
    responder([{
      titulo: 'A Casa do Dragão',
      platform: 'MAX',
      segundos: 4700,
      posicao: 2058,
      duracao: 4928,
      posterUrl: null,
    }])
    const chamadas = () => (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls
      .filter(([url]) => String(url).endsWith('/profile')).length

    renderizar()
    await screen.findByText('A Casa do Dragão')
    const antes = chamadas()

    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'))
    })

    expect(chamadas()).toBeGreaterThan(antes)
  })

  it('não mostra tempo de episódio sem dizer QUAL episódio', async () => {
    // Medido em 25/08/2026: o cartão do Invincible anunciava "37:08 de 48:41"
    // enquanto a pessoa assistia outro episódio. Os números descreviam a última
    // reprodução gravada; a frase montada com eles é que era falsa.
    responder([{
      titulo: 'INVINCIBLE',
      platform: 'PRIME_VIDEO',
      segundos: 6890,
      posicao: null,
      duracao: null,
      posicaoDoEpisodio: 2228,
      duracaoDoEpisodio: 2921,
      episodio: null,
      posterUrl: null,
    }])

    renderizar()

    expect(await screen.findByText('INVINCIBLE')).toBeTruthy()
    expect(screen.queryByText(/37:08/)).toBeNull()
  })

  it('mostra o tempo quando o episódio tem nome', async () => {
    // O par: com o episódio identificado, os números têm dono e valem.
    responder([{
      titulo: 'INVINCIBLE',
      platform: 'PRIME_VIDEO',
      segundos: 6890,
      posicao: null,
      duracao: null,
      posicaoDoEpisodio: 2228,
      duracaoDoEpisodio: 2921,
      episodio: 'T1 E4',
      posterUrl: null,
    }])

    renderizar()

    expect(await screen.findByText('T1 E4 · 37:08 de 48:41')).toBeTruthy()
  })
})
