import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { DPadControl } from './DPadControl'


function renderDPad(overrides: Partial<Parameters<typeof DPadControl>[0]> = {}) {
  const onAction = vi.fn()
  const view = render(
    <DPadControl
      disabled={false}
      currentAction={null}
      onAction={onAction}
      {...overrides}
    />,
  )
  return { onAction, ...view }
}

describe('DPadControl', () => {
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
    ['OK', 'NAVIGATE_CONFIRM'],
    ['Voltar na TV', 'NAVIGATE_BACK'],
  ])('sends the closed %s action on touch', (label, action) => {
    const { onAction } = renderDPad()

    fireEvent.pointerDown(screen.getByRole('button', { name: label }))

    expect(onAction).toHaveBeenCalledOnce()
    expect(onAction).toHaveBeenCalledWith(action)
  })

  it('supports the native keyboard/assistive click without double-sending pointer input', () => {
    const { onAction } = renderDPad()
    const ok = screen.getByRole('button', { name: 'OK' })

    fireEvent.click(ok, { detail: 0 })
    expect(onAction).toHaveBeenCalledOnce()
    fireEvent.pointerDown(ok)
    fireEvent.click(ok, { detail: 1 })
    expect(onAction).toHaveBeenCalledTimes(2)
  })

  it('repeats an arrow only after the hold delay and stops on release', () => {
    const { onAction } = renderDPad()
    const up = screen.getByRole('button', { name: 'Cima' })

    fireEvent.pointerDown(up)
    act(() => void vi.advanceTimersByTime(399))
    expect(onAction).toHaveBeenCalledOnce()

    act(() => void vi.advanceTimersByTime(1 + 120 * 3))
    expect(onAction).toHaveBeenCalledTimes(4)

    fireEvent.pointerUp(up)
    act(() => void vi.advanceTimersByTime(1000))
    expect(onAction).toHaveBeenCalledTimes(4)
  })

  it.each(['OK', 'Voltar na TV'])('never repeats %s', (label) => {
    const { onAction } = renderDPad()

    fireEvent.pointerDown(screen.getByRole('button', { name: label }))
    act(() => void vi.advanceTimersByTime(5000))

    expect(onAction).toHaveBeenCalledOnce()
  })

  it('stops an active repeat when the control unmounts', () => {
    const { onAction, unmount } = renderDPad()

    fireEvent.pointerDown(screen.getByRole('button', { name: 'Direita' }))
    unmount()
    act(() => void vi.advanceTimersByTime(5000))

    expect(onAction).toHaveBeenCalledOnce()
  })

  it('sends nothing and exposes disabled buttons while unavailable', () => {
    const { onAction } = renderDPad({ disabled: true })

    const up = screen.getByRole('button', { name: 'Cima' }) as HTMLButtonElement
    const ok = screen.getByRole('button', { name: 'OK' }) as HTMLButtonElement
    expect(up.disabled).toBe(true)
    expect(ok.disabled).toBe(true)

    fireEvent.pointerDown(up)
    fireEvent.pointerDown(ok)
    expect(onAction).not.toHaveBeenCalled()
  })

  it('marks only the server-correlated current action as active', () => {
    renderDPad({ currentAction: 'NAVIGATE_LEFT' })

    expect(screen.getByRole('button', { name: 'Esquerda' }).getAttribute('data-active')).toBe('true')
    expect(screen.getByRole('button', { name: 'Direita' }).getAttribute('data-active')).toBe('false')
  })

  it('does not expose an undefined home action', () => {
    renderDPad()

    expect(screen.queryByRole('button', { name: /home/i })).toBeNull()
  })
})
