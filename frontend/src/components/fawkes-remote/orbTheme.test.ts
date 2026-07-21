import { describe, expect, it } from 'vitest'

import { ORB_THEMES, ORB_VISUAL_TUNING } from './orbTheme'


describe('Fawkes orb themes', () => {
  it('defines a visible, bounded brightness for every visual state', () => {
    expect(Object.keys(ORB_THEMES)).toEqual([
      'idle',
      'listening',
      'transcribing',
      'needs_selection',
      'executing',
      'success',
      'error',
    ])

    expect(Object.fromEntries(
      Object.entries(ORB_THEMES).map(([state, theme]) => [state, theme.brightness]),
    )).toEqual({
      idle: 1,
      listening: 1,
      transcribing: 1,
      needs_selection: 1,
      executing: 1,
      success: 1,
      error: 0.94,
    })

    for (const theme of Object.values(ORB_THEMES)) {
      expect(theme.brightness).toBeGreaterThanOrEqual(0.94)
      expect(theme.brightness).toBeLessThanOrEqual(1)
    }
  })

  it('keeps mobile material tuning visible without exceeding valid opacity', () => {
    expect(ORB_VISUAL_TUNING).toEqual({
      spriteMidHaloOpacity: 0.42,
      lineOpacityMultiplier: 0.085,
      electronOpacity: 1,
      initialPointOpacity: 1,
    })

    expect(ORB_VISUAL_TUNING.electronOpacity).toBeLessThanOrEqual(1)
    expect(ORB_VISUAL_TUNING.initialPointOpacity).toBeLessThanOrEqual(1)
  })
})
