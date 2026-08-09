import { describe, expect, it } from 'vitest'

import { DEFAULT_GESTURE_LIMITS, TouchpadGesture } from './touchpadGesture'


const { tapDistancePx, tapDurationMs } = DEFAULT_GESTURE_LIMITS

function gesture() {
  return new TouchpadGesture()
}

describe('TouchpadGesture', () => {
  it('never clicks on the press itself', () => {
    const g = gesture()

    expect(g.down(1, 100, 100, 0)).toEqual([])
    expect(g.phase).toBe('POSSIBLE_TAP')
  })

  it('clicks only when the finger is released quickly and barely moved', () => {
    const g = gesture()
    g.down(1, 100, 100, 0)

    expect(g.up(1, 102, 101, 120)).toEqual([{ type: 'CLICK' }])
    expect(g.phase).toBe('COMPLETED')
  })

  it('does not click when the finger travelled too far', () => {
    const g = gesture()
    g.down(1, 100, 100, 0)
    g.move(1, 100 + tapDistancePx + 5, 100)

    expect(g.up(1, 100 + tapDistancePx + 5, 100, 100)).toEqual([])
  })

  it('does not click when the press lasted too long', () => {
    const g = gesture()
    g.down(1, 100, 100, 0)

    expect(g.up(1, 100, 100, tapDurationMs + 50)).toEqual([])
  })

  it('moves the cursor without pressing any button', () => {
    const g = gesture()
    g.down(1, 100, 100, 0)
    g.move(1, 130, 100)

    const effects = g.move(1, 150, 110)

    expect(effects).toEqual([{ type: 'MOVE', dx: 20, dy: 10 }])
    expect(g.phase).toBe('MOVING')
  })

  it('arms the drag on a still long press, before any movement', () => {
    // Era aqui que nascia o clique acidental: o botão descia depois de o
    // cursor já ter andado, então descia e subia quase no mesmo ponto.
    const g = gesture()
    g.down(1, 100, 100, 0)

    expect(g.holdElapsed()).toEqual([{ type: 'PRESS' }])
    expect(g.phase).toBe('DRAGGING')
    expect(g.move(1, 160, 140)).toEqual([
      { type: 'MOVE', dx: 60, dy: 40 },
    ])
  })

  it('does not arm the drag once the finger has already moved', () => {
    const g = gesture()
    g.down(1, 100, 100, 0)
    g.move(1, 100 + tapDistancePx + 5, 100)

    expect(g.holdElapsed()).toEqual([])
    expect(g.phase).toBe('MOVING')
  })

  it('releases the button when the drag ends, and never clicks', () => {
    const g = gesture()
    g.down(1, 100, 100, 0)
    g.holdElapsed()
    g.move(1, 200, 200)

    expect(g.up(1, 200, 200, 500)).toEqual([{ type: 'RELEASE' }])
  })

  it('releases the button when the drag is cancelled', () => {
    const g = gesture()
    g.down(1, 100, 100, 0)
    g.holdElapsed()

    expect(g.cancel()).toEqual([{ type: 'RELEASE' }])
    expect(g.phase).toBe('CANCELLED')
  })

  it('cancels the tap when a second finger touches', () => {
    const g = gesture()
    g.down(1, 100, 100, 0)
    g.down(2, 150, 150, 10)

    expect(g.phase).toBe('CANCELLED')
    expect(g.up(1, 100, 100, 50)).toEqual([])
  })

  it('releases the button when a second finger interrupts a drag', () => {
    const g = gesture()
    g.down(1, 100, 100, 0)
    g.holdElapsed()

    expect(g.down(2, 150, 150, 400)).toEqual([{ type: 'RELEASE' }])
  })

  it('ignores events from a pointer that is not the active one', () => {
    const g = gesture()
    g.down(1, 100, 100, 0)

    expect(g.move(9, 300, 300)).toEqual([])
    expect(g.up(9, 300, 300, 30)).toEqual([])
    expect(g.phase).toBe('POSSIBLE_TAP')
  })

  it('emits nothing for a movement of zero pixels', () => {
    const g = gesture()
    g.down(1, 100, 100, 0)
    g.holdElapsed()

    expect(g.move(1, 100, 100)).toEqual([])
  })

  it('goes back to idle on reset', () => {
    const g = gesture()
    g.down(1, 100, 100, 0)
    g.reset()

    expect(g.phase).toBe('IDLE')
  })
})
