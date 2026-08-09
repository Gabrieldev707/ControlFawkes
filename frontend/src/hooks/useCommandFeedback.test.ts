import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useCommandFeedback } from './useCommandFeedback'


describe('useCommandFeedback', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  it('correlates one request and exposes its typed active action', () => {
    const { result } = renderHook(() => useCommandFeedback())
    let requestId = ''
    act(() => {
      requestId = result.current.begin({ kind: 'media', action: 'MEDIA_PLAY_PAUSE' })
    })

    expect(result.current.isCurrent(requestId)).toBe(true)
    expect(result.current.isCurrent('stale')).toBe(false)
    expect(result.current.currentMediaAction).toBe('MEDIA_PLAY_PAUSE')
    expect(result.current.currentVolumeAction).toBeNull()
  })

  it('clears current correlation after the honest feedback window', () => {
    const afterReset = vi.fn()
    const { result } = renderHook(() => useCommandFeedback())
    let requestId = ''
    act(() => {
      requestId = result.current.begin({ kind: 'volume', action: 'SYSTEM_MUTE_TOGGLE' })
      result.current.scheduleReset(2000, afterReset)
    })

    act(() => void vi.advanceTimersByTime(1999))
    expect(result.current.isCurrent(requestId)).toBe(true)
    act(() => void vi.advanceTimersByTime(1))
    expect(result.current.isCurrent(requestId)).toBe(false)
    expect(result.current.currentVolumeAction).toBeNull()
    expect(afterReset).toHaveBeenCalledOnce()
  })

  it('cancels pending timers and active input on unmount', () => {
    const afterReset = vi.fn()
    const { result, unmount } = renderHook(() => useCommandFeedback())
    act(() => {
      result.current.begin({ kind: 'navigation', action: 'NAVIGATE_DOWN' })
      result.current.scheduleReset(1000, afterReset)
    })
    unmount()
    act(() => void vi.advanceTimersByTime(1000))
    expect(afterReset).not.toHaveBeenCalled()
  })
})
