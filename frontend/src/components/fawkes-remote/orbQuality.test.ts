import { describe, expect, it } from 'vitest'

import {
  DEFAULT_ORB_QUALITY,
  ORB_QUALITY_LEVELS,
  isOrbQuality,
  orbQualityProfile,
} from './orbQuality'
import { ORB_THEMES } from './orbTheme'


describe('orb quality', () => {
  it('defaults to BALANCED', () => {
    expect(DEFAULT_ORB_QUALITY).toBe('BALANCED')
  })

  it('renders sharp on retina by default', () => {
    // O teto era 1.5 e o iPhone tem DPR 3: o canvas saía a meia resolução e
    // era ampliado, o que apagava pontos de 1px.
    expect(orbQualityProfile('BALANCED').pixelRatioCap).toBeGreaterThanOrEqual(2)
  })

  it('grows monotonically from LOW to HIGH', () => {
    const [low, balanced, high] = ORB_QUALITY_LEVELS.map(orbQualityProfile)

    expect(low.pixelRatioCap).toBeLessThanOrEqual(balanced.pixelRatioCap)
    expect(balanced.pixelRatioCap).toBeLessThanOrEqual(high.pixelRatioCap)
    expect(low.particleScale).toBeLessThan(high.particleScale)
    expect(low.electronScale).toBeLessThan(high.electronScale)
  })

  it('enlarges the points on every level', () => {
    // Nenhum nível pode deixar o ponto menor do que era.
    for (const level of ORB_QUALITY_LEVELS) {
      expect(orbQualityProfile(level).sizeScale).toBeGreaterThan(1)
    }
  })

  it('validates the level coming from settings', () => {
    expect(isOrbQuality('HIGH')).toBe(true)
    expect(isOrbQuality('ULTRA')).toBe(false)
    expect(isOrbQuality(null)).toBe(false)
  })
})

describe('orb theme visibility', () => {
  const BACKGROUND = 0.0016 // luminância de #050508

  function contrast(hex: number): number {
    const toLinear = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)
    const r = ((hex >> 16) & 255) / 255
    const g = ((hex >> 8) & 255) / 255
    const b = (hex & 255) / 255
    const luminance = 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b)
    return (luminance + 0.05) / (BACKGROUND + 0.05)
  }

  it('keeps every idle colour above the threshold where it vanishes on OLED', () => {
    // A paleta anterior tinha cinco cores abaixo de 2,2:1 e o orb sumia no
    // iPhone com brilho normal.
    for (const colour of ORB_THEMES.idle.colors) {
      expect(contrast(colour.getHex())).toBeGreaterThan(2.5)
    }
  })

  it('emits particles in every state', () => {
    // idle, listening, needs_selection e error estavam com taxa zero: o estado
    // padrão não mostrava partícula nenhuma.
    for (const [state, theme] of Object.entries(ORB_THEMES)) {
      expect(theme.electronRate, `estado ${state}`).toBeGreaterThan(0)
    }
  })
})
