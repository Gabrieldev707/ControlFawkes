import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { RemoteControlScreen } from './RemoteControlScreen'


/** Estado padrão dos testes: conectado e com algo tocando. */
const TOCANDO = {
  title: 'Duna',
  artist: null,
  app: 'Chrome',
  platform: null,
  playing: true,
  positionSeconds: 10,
  durationSeconds: 100,
  thumbnailId: null,
}

function renderScreen(overrides: Partial<Parameters<typeof RemoteControlScreen>[0]> = {}) {
  const callbacks = {
    onAction: vi.fn(),
    onNavigationAction: vi.fn(),
    onPointerAction: vi.fn(),
    onKey: vi.fn(),
    onSetVolume: vi.fn(),
    onVolumeDelta: vi.fn(),
    onNavigate: vi.fn(),
    onToggleMute: vi.fn(),
    onBack: vi.fn(),
  }
  render(
    <RemoteControlScreen
      disabled={false}
      connected={true}
      navigationDisabled={false}
      currentAction={null}
      currentNavigationAction={null}
      muted={false}
      volumeLevel={42}
      statusMessage="Computador pronto."
      statusError={false}
      nowPlaying={TOCANDO}
      {...callbacks}
      {...overrides}
    />,
  )
  return callbacks
}


describe('RemoteControlScreen', () => {
  it('renders the essential remote groups in primary-use order', () => {
    renderScreen()

    expect(screen.getByRole('heading', { name: 'Controle' })).toBeTruthy()
    // `application` e não `group`: a superfície interpreta gestos próprios, e
    // é esse papel que faz o leitor de tela repassar as teclas em vez de
    // consumi-las na própria navegação.
    expect(screen.getByRole('application', { name: 'Controle direcional' })).toBeTruthy()
    expect(screen.getByRole('group', { name: 'Controles de reprodução' })).toBeTruthy()
    expect(screen.getByRole('region', { name: 'Volume do Windows' })).toBeTruthy()
    expect(screen.getByRole('group', { name: 'Ações secundárias' })).toBeTruthy()
    expect(screen.getByRole('navigation', { name: 'Ferramentas do controle' })).toBeTruthy()
  })

  it('mantém as setas como botões de verdade, além do gesto', () => {
    // Gesto sozinho seria inacessível para leitor de tela e para quem tem
    // limitação motora — e é o botão que ensina o gesto a quem chega agora.
    const { onNavigationAction } = renderScreen()

    for (const nome of ['Cima', 'Baixo', 'Esquerda', 'Direita', 'OK', 'Voltar na TV']) {
      expect(screen.getByRole('button', { name: nome })).toBeTruthy()
    }

    fireEvent.click(screen.getByRole('button', { name: 'OK' }))
    expect(onNavigationAction).toHaveBeenCalledWith('NAVIGATE_CONFIRM')
  })

  it('routes directional and media actions through their closed callbacks', () => {
    const { onAction, onNavigationAction } = renderScreen()

    fireEvent.pointerDown(screen.getByRole('button', { name: 'Cima' }))
    fireEvent.click(screen.getByRole('button', { name: 'Play/Pause' }))

    expect(onNavigationAction).toHaveBeenCalledWith('NAVIGATE_UP')
    expect(onAction).toHaveBeenCalledWith('MEDIA_PLAY_PAUSE')
  })

  it('ajusta o volume arrastando, e diz de quem é o volume', () => {
    // Quatro caixas iguais lado a lado não diziam qual era a importante, e
    // ajustar de 5 em 5 pedia uma fileira de toques. Agora o controle é um só.
    const { onToggleMute, onSetVolume } = renderScreen({ volumeTarget: 'Chrome' })
    const volume = screen.getByRole('region', { name: 'Volume do Chrome' })

    expect(within(volume).getByText('42%')).toBeTruthy()
    expect(within(volume).getByText('Chrome')).toBeTruthy()

    fireEvent.change(within(volume).getByRole('slider', { name: 'Nível do volume' }), {
      target: { value: '70' },
    })
    fireEvent.click(within(volume).getByRole('button', { name: 'Ativar mudo' }))

    expect(onSetVolume).toHaveBeenCalledWith(70)
    expect(onToggleMute).toHaveBeenCalledOnce()
  })

  it('mostra o Windows como alvo quando não é o volume de um aplicativo', () => {
    renderScreen()

    expect(screen.getByRole('region', { name: 'Volume do Windows' })).toBeTruthy()
  })

  it('describes mute from server-confirmed state and exposes active actions', () => {
    renderScreen({
      muted: true,
      currentAction: 'MEDIA_PLAY_PAUSE',
      currentNavigationAction: 'NAVIGATE_LEFT',
    })

    expect(screen.getByRole('button', { name: 'Desativar mudo' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Play/Pause' }).getAttribute('data-active')).toBe('true')
    expect(screen.getByRole('button', { name: 'Esquerda' }).getAttribute('data-active')).toBe('true')
  })

  it('keeps secondary actions lower in the hierarchy but functional', () => {
    const { onAction } = renderScreen()
    const secondary = screen.getByRole('group', { name: 'Ações secundárias' })

    fireEvent.click(within(secondary).getByRole('button', { name: 'Voltar 10 segundos' }))
    fireEvent.click(within(secondary).getByRole('button', { name: 'Fullscreen' }))

    expect(onAction).toHaveBeenNthCalledWith(1, 'MEDIA_SEEK_BACK')
    expect(onAction).toHaveBeenNthCalledWith(2, 'MEDIA_FULLSCREEN')
  })

  it('opens touchpad, keyboard and detailed volume without sending a system action', () => {
    const { onNavigate, onAction } = renderScreen()

    fireEvent.click(screen.getByRole('button', { name: 'Abrir touchpad' }))
    fireEvent.click(screen.getByRole('button', { name: 'Abrir teclado' }))
    fireEvent.click(screen.getByRole('button', { name: 'Abrir volume detalhado' }))

    expect(onNavigate).toHaveBeenNthCalledWith(1, 'TOUCHPAD')
    expect(onNavigate).toHaveBeenNthCalledWith(2, 'KEYBOARD')
    expect(onNavigate).toHaveBeenNthCalledWith(3, 'VOLUME')
    expect(onAction).not.toHaveBeenCalled()
  })

  it('disables every remote command while leaving local navigation available', () => {
    renderScreen({ disabled: true, connected: false })

    expect((screen.getByRole('button', { name: 'Cima' }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: 'Play/Pause' }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole('slider', { name: 'Nível do volume' }) as HTMLInputElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: 'Ativar mudo' }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: 'Abrir touchpad' }) as HTMLButtonElement).disabled).toBe(false)
    expect((screen.getByRole('button', { name: 'Voltar' }) as HTMLButtonElement).disabled).toBe(false)
    expect(screen.getByText('OFFLINE')).toBeTruthy()
    expect(screen.queryByText('AO VIVO')).toBeNull()
  })

  it('announces backend errors honestly', () => {
    renderScreen({ statusMessage: 'Nenhuma mídia ativa foi identificada.', statusError: true })

    expect(screen.getByRole('alert').textContent).toBe('Nenhuma mídia ativa foi identificada.')
  })
})

describe('RemoteControlScreen em tela de login', () => {
  it('manda Tab para andar entre campos, sem sair do controle', () => {
    // Tela de login e seleção de perfil não andam com seta: andam com Tab.
    // Sem isto, entrar numa conta exigia ir para a tela de teclado ou mirar
    // cada campo com o cursor.
    const { onKey, onNavigationAction } = renderScreen()

    fireEvent.click(screen.getByRole('button', { name: 'Próximo campo' }))

    expect(onKey).toHaveBeenCalledWith('TAB')
    expect(onNavigationAction).not.toHaveBeenCalled()
  })
})

describe('RemoteControlScreen sem mídia tocando', () => {
  it('trata "nada tocando" como estado normal, não como erro', () => {
    // Antes, cada toque no play virava "nenhuma plataforma de mídia ativa" — o
    // controle parecia quebrado justamente na situação mais comum: pegar o
    // celular antes de começar a assistir.
    renderScreen({ nowPlaying: null })

    expect(screen.getByRole('region', { name: 'Nada tocando' })).toBeTruthy()
    expect(screen.getByText('Nada tocando agora')).toBeTruthy()
  })

  it('desliga só os controles de reprodução, não a tela inteira', () => {
    renderScreen({ nowPlaying: null })

    // Sem o que controlar, o play mente se ficar ativo.
    expect((screen.getByRole('button', { name: 'Play/Pause' }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: 'Fullscreen' }) as HTMLButtonElement).disabled).toBe(true)
    // O resto não depende de mídia e continua valendo.
    expect((screen.getByRole('button', { name: 'Cima' }) as HTMLButtonElement).disabled).toBe(false)
    expect((screen.getByRole('slider', { name: 'Nível do volume' }) as HTMLInputElement).disabled).toBe(false)
    expect((screen.getByRole('button', { name: 'Próximo campo' }) as HTMLButtonElement).disabled).toBe(false)
  })

  it('oferece a saída em vez de deixar a pessoa parada', () => {
    const { onNavigate } = renderScreen({ nowPlaying: null })

    fireEvent.click(screen.getByRole('button', { name: 'Abrir plataformas' }))

    expect(onNavigate).toHaveBeenCalledWith('PLATFORMS')
  })

  it('com mídia tocando, os controles voltam e o cartão some', () => {
    renderScreen({ nowPlaying: TOCANDO })

    expect(screen.queryByRole('region', { name: 'Nada tocando' })).toBeNull()
    expect((screen.getByRole('button', { name: 'Play/Pause' }) as HTMLButtonElement).disabled).toBe(false)
    expect(screen.getByRole('region', { name: 'Tocando agora' })).toBeTruthy()
  })

  it('enquanto não conectou, diz que está procurando em vez de afirmar', () => {
    renderScreen({ nowPlaying: null, connected: false })

    expect(screen.getByText('Procurando o que está tocando…')).toBeTruthy()
  })
})
