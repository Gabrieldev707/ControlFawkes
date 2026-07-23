import { beforeEach, describe, expect, it } from 'vitest'

import { loadOrbQuality, saveOrbQuality } from './orbPreferences'


describe('orb preferences', () => {
  beforeEach(() => localStorage.clear())

  it('falls back to the default when nothing was saved', () => {
    expect(loadOrbQuality('device-1')).toBe('BALANCED')
  })

  it('keeps the choice per device', () => {
    saveOrbQuality('device-1', 'HIGH')

    expect(loadOrbQuality('device-1')).toBe('HIGH')
    // Outro dispositivo no mesmo navegador não herda a escolha.
    expect(loadOrbQuality('device-2')).toBe('BALANCED')
  })

  it('ignores a corrupted value instead of breaking the screen', () => {
    localStorage.setItem('controlfawkes.orbQuality.device-1', 'ULTRA')

    expect(loadOrbQuality('device-1')).toBe('BALANCED')
  })
})
