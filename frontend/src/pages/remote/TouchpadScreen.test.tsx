import { fireEvent, render, screen } from '@testing-library/react'
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

afterEach(() => vi.unstubAllGlobals())

describe('TouchpadScreen', () => {
  it('groups relative movement into one update per animation frame', () => {
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

    expect(onAction).toHaveBeenNthCalledWith(1, 'POINTER_DOWN')
    expect(onAction).toHaveBeenNthCalledWith(2, 'POINTER_MOVE', { dx: 10, dy: 8 })
    expect(onAction).toHaveBeenNthCalledWith(3, 'POINTER_UP')
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

  it('releases a drag and disables immediately on emergency stop', () => {
    vi.stubGlobal('requestAnimationFrame', vi.fn(() => 1))
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    const onAction = renderTouchpad()
    const surface = screen.getByLabelText('Área do touchpad')

    fireEvent.pointerDown(surface, { pointerId: 1, clientX: 10, clientY: 10 })
    fireEvent.pointerMove(surface, { pointerId: 1, clientX: 20, clientY: 20 })
    fireEvent.click(screen.getByRole('button', { name: 'Parada de emergência' }))

    expect(onAction).toHaveBeenCalledWith('POINTER_UP')
    expect(onAction).not.toHaveBeenCalledWith(
      'POINTER_MOVE',
      expect.anything(),
    )
    expect(screen.getByRole('button', { name: 'Ativar touchpad' })).toBeTruthy()
    expect(screen.queryByLabelText('Área do touchpad')).toBeNull()
  })
})
