import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { RemoteControlScreen } from './RemoteControlScreen'


function renderScreen(muted = false) {
  const onAction = vi.fn()
  const onNavigate = vi.fn()
  const onToggleMute = vi.fn()
  render(
    <RemoteControlScreen
      disabled={false}
      currentAction={null}
      currentVolumeAction={null}
      muted={muted}
      statusMessage="Computador pronto."
      statusError={false}
      onAction={onAction}
      onToggleMute={onToggleMute}
      onNavigate={onNavigate}
      onBack={vi.fn()}
    />,
  )
  return { onAction, onNavigate, onToggleMute }
}


describe('RemoteControlScreen', () => {
  it('separates system volume and mute from active-player media controls', () => {
    const { onAction, onNavigate, onToggleMute } = renderScreen()

    expect(screen.getByRole('heading', { name: 'Sistema' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Mídia' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Abrir controles de volume' }))
    fireEvent.click(screen.getByRole('button', { name: 'Ativar mudo' }))
    fireEvent.click(screen.getByRole('button', { name: 'Play/Pause' }))

    expect(onNavigate).toHaveBeenCalledWith('VOLUME')
    expect(onToggleMute).toHaveBeenCalledOnce()
    expect(onAction).toHaveBeenCalledWith('MEDIA_PLAY_PAUSE')
  })

  it('describes the mute action from the real system state', () => {
    renderScreen(true)

    expect(screen.getByRole('button', { name: 'Desativar mudo' })).toBeTruthy()
  })
})
