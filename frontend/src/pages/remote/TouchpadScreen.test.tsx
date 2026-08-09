import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { TouchpadScreen } from './TouchpadScreen'


function renderTouchpad() {
  const onAction = vi.fn()
  render(
    <TouchpadScreen
      disabled={false}
      statusMessage="Computador pronto."
      statusError={false}
      onAction={onAction}
      onBack={vi.fn()}
    />,
  )
  fireEvent.click(screen.getByRole('button', { name: 'Ativar touchpad' }))
  return onAction
}

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('TouchpadScreen', () => {
  it('groups relative movement into one update per animation frame without holding the mouse button', () => {
    const scheduled: FrameRequestCallback[] = []
    vi.stubGlobal('requestAnimationFrame', vi.fn((callback: FrameRequestCallback) => {
      scheduled.push(callback)
      return 1
    }))
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    const onAction = renderTouchpad()
    const surface = screen.getByLabelText('Área do touchpad')

    fireEvent.pointerDown(surface, { pointerId: 1, clientX: 10, clientY: 10 })
    fireEvent.pointerMove(surface, { pointerId: 1, clientX: 16, clientY: 13 })
    fireEvent.pointerMove(surface, { pointerId: 1, clientX: 20, clientY: 18 })
    scheduled[0]!(16)
    fireEvent.pointerUp(surface, { pointerId: 1, clientX: 20, clientY: 18 })

    expect(onAction).toHaveBeenCalledTimes(1)
    expect(onAction).toHaveBeenCalledWith('POINTER_MOVE', { dx: 10, dy: 8 })
    expect(onAction).not.toHaveBeenCalledWith('POINTER_CLICK')
  })

  it('maps taps, double click, right click and bounded scrolling', () => {
    const onAction = renderTouchpad()
    const surface = screen.getByLabelText('Área do touchpad')

    fireEvent.pointerDown(surface, { pointerId: 1, clientX: 10, clientY: 10 })
    fireEvent.pointerUp(surface, { pointerId: 1, clientX: 10, clientY: 10 })
    fireEvent.click(screen.getByRole('button', { name: 'Clique duplo' }))
    fireEvent.click(screen.getByRole('button', { name: 'Clique direito' }))
    fireEvent.wheel(surface, { deltaY: 40 })

    expect(onAction).toHaveBeenNthCalledWith(1, 'POINTER_CLICK')
    expect(onAction).toHaveBeenNthCalledWith(2, 'POINTER_DOUBLE_CLICK')
    expect(onAction).toHaveBeenNthCalledWith(3, 'POINTER_RIGHT_CLICK')
    expect(onAction).toHaveBeenNthCalledWith(4, 'POINTER_SCROLL', { delta: -120 })
  })

  it('accepts only a short tap within the six-pixel tolerance as a click', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-07-21T12:00:00Z'))
    const onAction = renderTouchpad()
    const surface = screen.getByLabelText('Área do touchpad')

    fireEvent.pointerDown(surface, { pointerId: 1, clientX: 10, clientY: 10 })
    vi.advanceTimersByTime(180)
    fireEvent.pointerUp(surface, { pointerId: 1, clientX: 14, clientY: 13 })

    expect(onAction).toHaveBeenCalledOnce()
    expect(onAction).toHaveBeenCalledWith('POINTER_CLICK')
  })

  it('cancels click after movement beyond the tolerance or a long press', () => {
    vi.useFakeTimers()
    const scheduled: FrameRequestCallback[] = []
    vi.stubGlobal('requestAnimationFrame', vi.fn((callback: FrameRequestCallback) => {
      scheduled.push(callback)
      return 1
    }))
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    vi.setSystemTime(new Date('2026-07-21T12:00:00Z'))
    const onAction = renderTouchpad()
    const surface = screen.getByLabelText('Área do touchpad')

    // 15px: além da tolerância de toque, que é 10px.
    fireEvent.pointerDown(surface, { pointerId: 1, clientX: 10, clientY: 10 })
    fireEvent.pointerMove(surface, { pointerId: 1, clientX: 25, clientY: 10 })
    scheduled.shift()!(16)
    fireEvent.pointerUp(surface, { pointerId: 1, clientX: 25, clientY: 10 })

    fireEvent.pointerDown(surface, { pointerId: 2, clientX: 20, clientY: 20 })
    vi.advanceTimersByTime(300)
    fireEvent.pointerUp(surface, { pointerId: 2, clientX: 20, clientY: 20 })

    expect(onAction).toHaveBeenCalledTimes(1)
    expect(onAction).toHaveBeenCalledWith('POINTER_MOVE', { dx: 15, dy: 0 })
    expect(onAction).not.toHaveBeenCalledWith('POINTER_CLICK')
  })

  it('uses hold-and-drag explicitly and releases it on pointer up', () => {
    vi.useFakeTimers()
    const scheduled: FrameRequestCallback[] = []
    vi.stubGlobal('requestAnimationFrame', vi.fn((callback: FrameRequestCallback) => {
      scheduled.push(callback)
      return 1
    }))
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    vi.setSystemTime(new Date('2026-07-21T12:00:00Z'))
    const onAction = renderTouchpad()
    const surface = screen.getByLabelText('Área do touchpad')

    fireEvent.pointerDown(surface, { pointerId: 1, clientX: 10, clientY: 10 })
    vi.advanceTimersByTime(360)
    fireEvent.pointerMove(surface, { pointerId: 1, clientX: 20, clientY: 18 })
    scheduled[0]!(16)
    fireEvent.pointerUp(surface, { pointerId: 1, clientX: 20, clientY: 18 })

    expect(onAction).toHaveBeenNthCalledWith(1, 'POINTER_DOWN')
    expect(onAction).toHaveBeenNthCalledWith(2, 'POINTER_MOVE', { dx: 10, dy: 8 })
    expect(onAction).toHaveBeenNthCalledWith(3, 'POINTER_UP')
    expect(onAction).not.toHaveBeenCalledWith('POINTER_CLICK')
  })

  it('cancels clicks for pointer cancellation, multitouch and scrolling', () => {
    const onAction = renderTouchpad()
    const surface = screen.getByLabelText('Área do touchpad')

    fireEvent.pointerDown(surface, { pointerId: 1, clientX: 10, clientY: 10 })
    fireEvent.pointerCancel(surface, { pointerId: 1 })

    fireEvent.pointerDown(surface, { pointerId: 2, clientX: 10, clientY: 10 })
    fireEvent.pointerDown(surface, { pointerId: 3, clientX: 12, clientY: 12 })
    fireEvent.pointerUp(surface, { pointerId: 3, clientX: 12, clientY: 12 })
    fireEvent.pointerUp(surface, { pointerId: 2, clientX: 10, clientY: 10 })

    fireEvent.pointerDown(surface, { pointerId: 4, clientX: 10, clientY: 10 })
    fireEvent.wheel(surface, { deltaY: 40 })
    fireEvent.pointerUp(surface, { pointerId: 4, clientX: 10, clientY: 10 })

    expect(onAction).toHaveBeenCalledOnce()
    expect(onAction).toHaveBeenCalledWith('POINTER_SCROLL', { delta: -120 })
    expect(onAction).not.toHaveBeenCalledWith('POINTER_CLICK')
  })

  it('blocks the native click event on the touch surface to prevent ghost clicks', () => {
    const onAction = renderTouchpad()
    const surface = screen.getByLabelText('Área do touchpad')

    const dispatched = fireEvent.click(surface)

    expect(dispatched).toBe(false)
    expect(onAction).not.toHaveBeenCalled()
  })

  it('releases a drag and disables immediately on emergency stop', () => {
    vi.stubGlobal('requestAnimationFrame', vi.fn(() => 1))
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-07-21T12:00:00Z'))
    const onAction = renderTouchpad()
    const surface = screen.getByLabelText('Área do touchpad')

    fireEvent.pointerDown(surface, { pointerId: 1, clientX: 10, clientY: 10 })
    vi.advanceTimersByTime(360)
    fireEvent.pointerMove(surface, { pointerId: 1, clientX: 20, clientY: 20 })
    fireEvent.click(screen.getByRole('button', { name: 'Parada de emergência' }))

    expect(onAction).toHaveBeenCalledWith('POINTER_UP')
    expect(onAction).not.toHaveBeenCalledWith('POINTER_MOVE', expect.anything())
    expect(screen.getByRole('button', { name: 'Ativar touchpad' })).toBeTruthy()
    expect(screen.queryByLabelText('Área do touchpad')).toBeNull()
  })
})

describe('TouchpadScreen tap and drag separation', () => {
  it('does not click when a drag starts', () => {
    // O bug: o arraste era promovido depois de o cursor já ter andado, então o
    // botão descia e subia quase no mesmo ponto e virava clique.
    vi.useFakeTimers()
    vi.stubGlobal('requestAnimationFrame', vi.fn(() => 1))
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    const onAction = renderTouchpad()
    const surface = screen.getByLabelText('Área do touchpad')

    fireEvent.pointerDown(surface, { pointerId: 1, clientX: 50, clientY: 50 })
    act(() => void vi.advanceTimersByTime(400))
    fireEvent.pointerMove(surface, { pointerId: 1, clientX: 150, clientY: 150 })
    fireEvent.pointerUp(surface, { pointerId: 1, clientX: 150, clientY: 150 })

    const actions = onAction.mock.calls.map(([action]) => action)
    expect(actions).toContain('POINTER_DOWN')
    expect(actions).toContain('POINTER_UP')
    expect(actions).not.toContain('POINTER_CLICK')
    // O botão desce antes de qualquer movimento.
    expect(actions.indexOf('POINTER_DOWN')).toBeLessThan(actions.indexOf('POINTER_UP'))
  })

  it('releases the button when the gesture is cancelled mid-drag', () => {
    vi.useFakeTimers()
    vi.stubGlobal('requestAnimationFrame', vi.fn(() => 1))
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    const onAction = renderTouchpad()
    const surface = screen.getByLabelText('Área do touchpad')

    fireEvent.pointerDown(surface, { pointerId: 1, clientX: 50, clientY: 50 })
    act(() => void vi.advanceTimersByTime(400))
    fireEvent.pointerCancel(surface, { pointerId: 1 })

    expect(onAction.mock.calls.map(([action]) => action)).toContain('POINTER_UP')
  })

  it('does not arm a drag once the finger has moved', () => {
    vi.useFakeTimers()
    vi.stubGlobal('requestAnimationFrame', vi.fn(() => 1))
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    const onAction = renderTouchpad()
    const surface = screen.getByLabelText('Área do touchpad')

    fireEvent.pointerDown(surface, { pointerId: 1, clientX: 50, clientY: 50 })
    fireEvent.pointerMove(surface, { pointerId: 1, clientX: 120, clientY: 50 })
    act(() => void vi.advanceTimersByTime(1000))
    fireEvent.pointerUp(surface, { pointerId: 1, clientX: 120, clientY: 50 })

    const actions = onAction.mock.calls.map(([action]) => action)
    expect(actions).not.toContain('POINTER_DOWN')
    expect(actions).not.toContain('POINTER_CLICK')
  })
})
