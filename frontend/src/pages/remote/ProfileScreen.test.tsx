import { render, screen } from '@testing-library/react'
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
