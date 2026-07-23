import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { NavigationScreen } from './NavigationScreen'


function renderScreen(overrides: Partial<Parameters<typeof NavigationScreen>[0]> = {}) {
  const onAction = vi.fn()
  const onBack = vi.fn()
  render(
    <NavigationScreen
      disabled={false}
      currentAction={null}
      statusMessage="Computador pronto."
      statusError={false}
      onAction={onAction}
      onBack={onBack}
      {...overrides}
    />,
  )
  return { onAction, onBack }
}

describe('NavigationScreen', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  it.each([
    ['Cima', 'NAVIGATE_UP'],
    ['Baixo', 'NAVIGATE_DOWN'],
    ['Esquerda', 'NAVIGATE_LEFT'],
    ['Direita', 'NAVIGATE_RIGHT'],
  ])('sends %s once on a short press', (label, action) => {
    const { onAction } = renderScreen()

    fireEvent.pointerDown(screen.getByRole('button', { name: label }))
    fireEvent.pointerUp(screen.getByRole('button', { name: label }))

    expect(onAction).toHaveBeenCalledTimes(1)
    expect(onAction).toHaveBeenCalledWith(action)
  })

  it('repeats only while an arrow stays pressed', () => {
    const { onAction } = renderScreen()
    const up = screen.getByRole('button', { name: 'Cima' })

    fireEvent.pointerDown(up)
    expect(onAction).toHaveBeenCalledTimes(1)

    act(() => void vi.advanceTimersByTime(400 + 120 * 3))
    expect(onAction).toHaveBeenCalledTimes(4)

    fireEvent.pointerUp(up)
    act(() => void vi.advanceTimersByTime(1000))
    expect(onAction).toHaveBeenCalledTimes(4)
  })

  it('does not repeat before the hold delay', () => {
    const { onAction } = renderScreen()

    fireEvent.pointerDown(screen.getByRole('button', { name: 'Cima' }))
    act(() => void vi.advanceTimersByTime(399))

    expect(onAction).toHaveBeenCalledTimes(1)
  })

  it('stops repeating when the finger slides off the button', () => {
    const { onAction } = renderScreen()
    const up = screen.getByRole('button', { name: 'Cima' })

    fireEvent.pointerDown(up)
    act(() => void vi.advanceTimersByTime(400 + 120))
    const afterHold = onAction.mock.calls.length
    fireEvent.pointerLeave(up)
    act(() => void vi.advanceTimersByTime(1000))

    expect(onAction).toHaveBeenCalledTimes(afterHold)
  })

  it.each([
    ['OK', 'NAVIGATE_CONFIRM'],
    ['Voltar na TV', 'NAVIGATE_BACK'],
  ])('never repeats %s', (label, action) => {
    const { onAction } = renderScreen()

    fireEvent.pointerDown(screen.getByRole('button', { name: label }))
    act(() => void vi.advanceTimersByTime(5000))

    expect(onAction).toHaveBeenCalledTimes(1)
    expect(onAction).toHaveBeenCalledWith(action)
  })

  it.each([
    ['OK', 'NAVIGATE_CONFIRM'],
    ['Voltar na TV', 'NAVIGATE_BACK'],
    ['Cima', 'NAVIGATE_UP'],
  ])('%s responds to the touch itself, not to a click', (label, action) => {
    // O iOS cancela o click quando o dedo se move alguns pixels, o que fazia o
    // OK não funcionar no aparelho enquanto as setas funcionavam.
    const { onAction } = renderScreen()

    fireEvent.pointerDown(screen.getByRole('button', { name: label }))

    expect(onAction).toHaveBeenCalledWith(action)
  })

  it('does not send twice when the touch also produces a click', () => {
    const { onAction } = renderScreen()
    const ok = screen.getByRole('button', { name: 'OK' })

    fireEvent.pointerDown(ok)
    fireEvent.click(ok)

    expect(onAction).toHaveBeenCalledTimes(1)
  })

  it('stops repeating when the screen unmounts mid-hold', () => {
    const onAction = vi.fn()
    const { unmount } = render(
      <NavigationScreen
        disabled={false}
        currentAction={null}
        statusMessage=""
        statusError={false}
        onAction={onAction}
        onBack={vi.fn()}
      />,
    )

    fireEvent.pointerDown(screen.getByRole('button', { name: 'Cima' }))
    unmount()
    act(() => void vi.advanceTimersByTime(5000))

    expect(onAction).toHaveBeenCalledTimes(1)
  })

  it('sends nothing while disabled', () => {
    const { onAction } = renderScreen({ disabled: true })

    fireEvent.pointerDown(screen.getByRole('button', { name: 'Cima' }))
    fireEvent.pointerDown(screen.getByRole('button', { name: 'OK' }))
    act(() => void vi.advanceTimersByTime(5000))

    expect(onAction).not.toHaveBeenCalled()
  })

  it('exposes no HOME button while the behaviour is undefined', () => {
    renderScreen()

    expect(screen.queryByRole('button', { name: /home/i })).toBeNull()
  })
})
