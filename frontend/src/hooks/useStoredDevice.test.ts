import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import { useStoredDevice } from './useStoredDevice'


describe('useStoredDevice', () => {
  beforeEach(() => localStorage.clear())

  it('loads only a complete credential pair', () => {
    localStorage.setItem('controlfawkes.deviceId', 'device-1')
    const { result } = renderHook(() => useStoredDevice())
    expect(result.current.load()).toBeNull()

    localStorage.setItem('controlfawkes.token', 'secure-token')
    expect(result.current.load()).toEqual({ deviceId: 'device-1', token: 'secure-token' })
  })

  it('saves and clears the credential pair as one lifecycle', () => {
    const { result } = renderHook(() => useStoredDevice())
    act(() => result.current.save('device-1', 'secure-token'))
    expect(result.current.load()).toEqual({ deviceId: 'device-1', token: 'secure-token' })

    act(() => result.current.clear())
    expect(result.current.load()).toBeNull()
    expect(localStorage.getItem('controlfawkes.deviceId')).toBeNull()
    expect(localStorage.getItem('controlfawkes.token')).toBeNull()
  })
})
