import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { RemoteControlScreen } from './RemoteControlScreen'


function renderScreen(overrides: Partial<Parameters<typeof RemoteControlScreen>[0]> = {}) {
  const callbacks = {
    onAction: vi.fn(),
    onNavigationAction: vi.fn(),
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
      currentVolumeAction={null}
      muted={false}
      volumeLevel={42}
      statusMessage="Computador pronto."
      statusError={false}
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
    expect(screen.getByRole('group', { name: 'Controle direcional' })).toBeTruthy()
    expect(screen.getByRole('group', { name: 'Controles de reprodução' })).toBeTruthy()
    expect(screen.getByRole('group', { name: 'Volume rápido' })).toBeTruthy()
    expect(screen.getByRole('group', { name: 'Ações secundárias' })).toBeTruthy()
    expect(screen.getByRole('navigation', { name: 'Ferramentas do controle' })).toBeTruthy()
  })

  it('routes directional and media actions through their closed callbacks', () => {
    const { onAction, onNavigationAction } = renderScreen()

    fireEvent.pointerDown(screen.getByRole('button', { name: 'Cima' }))
    fireEvent.click(screen.getByRole('button', { name: 'Play/Pause' }))

    expect(onNavigationAction).toHaveBeenCalledWith('NAVIGATE_UP')
    expect(onAction).toHaveBeenCalledWith('MEDIA_PLAY_PAUSE')
  })

  it('provides one-tap volume down, mute and volume up with a real level', () => {
    const { onToggleMute, onVolumeDelta } = renderScreen()
    const volume = screen.getByRole('group', { name: 'Volume rápido' })

    expect(within(volume).getByText('42%')).toBeTruthy()
    fireEvent.click(within(volume).getByRole('button', { name: 'Diminuir volume' }))
    fireEvent.click(within(volume).getByRole('button', { name: 'Ativar mudo' }))
    fireEvent.click(within(volume).getByRole('button', { name: 'Aumentar volume' }))

    expect(onVolumeDelta).toHaveBeenNthCalledWith(1, -5)
    expect(onVolumeDelta).toHaveBeenNthCalledWith(2, 5)
    expect(onToggleMute).toHaveBeenCalledOnce()
  })

  it('describes mute from server-confirmed state and exposes active actions', () => {
    renderScreen({
      muted: true,
      currentAction: 'MEDIA_PLAY_PAUSE',
      currentNavigationAction: 'NAVIGATE_LEFT',
      currentVolumeAction: 'SYSTEM_MUTE_TOGGLE',
    })

    expect(screen.getByRole('button', { name: 'Desativar mudo' }).getAttribute('data-active')).toBe('true')
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
    expect((screen.getByRole('button', { name: 'Diminuir volume' }) as HTMLButtonElement).disabled).toBe(true)
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
