import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { VolumeScreen } from './VolumeScreen'


describe('VolumeScreen', () => {
  it('shows the real state and exposes only fixed volume actions', () => {
    const onSetLevel = vi.fn()
    const onDelta = vi.fn()
    const onToggleMute = vi.fn()

    render(
      <VolumeScreen
        disabled={false}
        loading={false}
        level={42}
        muted={false}
        statusMessage="Volume: 42%."
        statusError={false}
        onSetLevel={onSetLevel}
        onDelta={onDelta}
        onToggleMute={onToggleMute}
        onBack={vi.fn()}
      />,
    )

    const slider = screen.getByRole('slider', { name: 'Volume do computador' })
    expect((slider as HTMLInputElement).value).toBe('42')
    expect(screen.getByText('42%')).toBeTruthy()

    fireEvent.change(slider, { target: { value: '73' } })
    fireEvent.click(screen.getByRole('button', { name: 'Diminuir volume' }))
    fireEvent.click(screen.getByRole('button', { name: 'Aumentar volume' }))
    fireEvent.click(screen.getByRole('button', { name: 'Ativar mudo' }))

    expect(onSetLevel).toHaveBeenCalledWith(73)
    expect(onDelta).toHaveBeenNthCalledWith(1, -5)
    expect(onDelta).toHaveBeenNthCalledWith(2, 5)
    expect(onToggleMute).toHaveBeenCalledTimes(1)
  })

  it('shows loading and disables input while a request is active', () => {
    render(
      <VolumeScreen
        disabled={false}
        loading
        level={null}
        muted={false}
        statusMessage="Carregando volume..."
        statusError={false}
        onSetLevel={vi.fn()}
        onDelta={vi.fn()}
        onToggleMute={vi.fn()}
        onBack={vi.fn()}
      />,
    )

    expect(screen.getByText('Carregando volume...')).toBeTruthy()
    expect((screen.getByRole('slider', { name: 'Volume do computador' }) as HTMLInputElement).disabled).toBe(true)
  })
})

describe('VolumeScreen scope feedback', () => {
  function renderScope(scope: 'LOCAL' | 'GLOBAL', target: string | null) {
    render(
      <VolumeScreen
        disabled={false}
        loading={false}
        level={40}
        muted={false}
        scope={scope}
        target={target}
        statusMessage=""
        statusError={false}
        onDelta={vi.fn()}
        onSetLevel={vi.fn()}
        onToggleMute={vi.fn()}
        onBack={vi.fn()}
      />,
    )
  }

  it('names the application when only it was changed', () => {
    renderScope('LOCAL', 'Spotify')

    expect(screen.getByText('Spotify')).toBeTruthy()
    expect(screen.getByText(/Só o áudio do Spotify muda/)).toBeTruthy()
  })

  it('never hides the fallback to the whole system', () => {
    renderScope('GLOBAL', null)

    expect(screen.getByText('Sistema Windows')).toBeTruthy()
    expect(screen.getByText(/vale para o computador inteiro/)).toBeTruthy()
  })
})

describe('VolumeScreen slider otimista', () => {
  function renderVolume(level: number | null, onSetLevel = vi.fn()) {
    const utils = render(
      <VolumeScreen
        disabled={false}
        loading={false}
        level={level}
        muted={false}
        statusMessage=""
        statusError={false}
        onSetLevel={onSetLevel}
        onDelta={vi.fn()}
        onToggleMute={vi.fn()}
        onBack={vi.fn()}
      />,
    )
    return { ...utils, onSetLevel }
  }

  it('mostra o valor do dedo enquanto o servidor não confirma', () => {
    // Sem isto o slider voltava ao valor antigo a cada movimento e o arrasto
    // parecia emperrado.
    const { onSetLevel } = renderVolume(40)
    const slider = screen.getByRole('slider', { name: 'Volume do computador' })

    fireEvent.change(slider, { target: { value: '75' } })

    expect(onSetLevel).toHaveBeenCalledWith(75)
    expect((slider as HTMLInputElement).value).toBe('75')
    expect(screen.getByText('75%')).toBeTruthy()
  })

  it('volta a seguir o servidor quando ele alcança o arrasto', () => {
    const { rerender } = renderVolume(40)
    const slider = screen.getByRole('slider', { name: 'Volume do computador' })

    fireEvent.change(slider, { target: { value: '75' } })
    rerender(
      <VolumeScreen
        disabled={false}
        loading={false}
        level={75}
        muted={false}
        statusMessage=""
        statusError={false}
        onSetLevel={vi.fn()}
        onDelta={vi.fn()}
        onToggleMute={vi.fn()}
        onBack={vi.fn()}
      />,
    )

    expect((slider as HTMLInputElement).value).toBe('75')
  })

  it('continua utilizável com um comando em voo', () => {
    // O ciclo "executando por 2s" travava o controle a cada ajuste.
    renderVolume(40)

    expect(
      (screen.getByRole('slider', { name: 'Volume do computador' }) as HTMLInputElement).disabled,
    ).toBe(false)
  })
})
