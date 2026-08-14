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
      idle: 1.08,
      listening: 1.1,
      transcribing: 1.08,
      needs_selection: 1.06,
      executing: 1.1,
      success: 1.1,
      error: 1.02,
    })

    for (const theme of Object.values(ORB_THEMES)) {
      expect(theme.brightness).toBeGreaterThanOrEqual(1.02)
      expect(theme.brightness).toBeLessThanOrEqual(1.1)
    }
  })

  it('gives every state its own orbit and energy wave', () => {
    for (const [state, theme] of Object.entries(ORB_THEMES)) {
      expect(theme.swirl, state).toBeGreaterThan(0)
      expect(theme.waveStrength, state).toBeGreaterThan(0)
      // Período curto demais transforma a onda em tremor; longo demais some.
      expect(theme.wavePeriod, state).toBeGreaterThanOrEqual(1)
      expect(theme.wavePeriod, state).toBeLessThanOrEqual(8)
    }
  })

  it('keeps the resting state present instead of nearly invisible', () => {
    // Repouso é a primeira tela: se sumir aqui, o produto parece desligado.
    expect(ORB_THEMES.idle.electronRate).toBeGreaterThan(0.02)
    expect(ORB_THEMES.idle.lineAmount).toBeGreaterThanOrEqual(0.15)
    expect(ORB_THEMES.idle.size).toBeGreaterThanOrEqual(0.5)
  })

  it('keeps mobile material tuning visible without exceeding valid opacity', () => {
    expect(ORB_VISUAL_TUNING).toEqual({
      spriteMidHaloOpacity: 0.55,
      lineOpacityMultiplier: 0.3,
      electronOpacity: 1,
      initialPointOpacity: 1,
    })

    // O produto do multiplicador pelo lineAmount de repouso é a opacidade real
    // das ligações. Abaixo de ~0,05 elas somem na tela, que era o caso.
    expect(
      ORB_VISUAL_TUNING.lineOpacityMultiplier * ORB_THEMES.idle.lineAmount,
    ).toBeGreaterThan(0.05)

    expect(ORB_VISUAL_TUNING.electronOpacity).toBeLessThanOrEqual(1)
    expect(ORB_VISUAL_TUNING.initialPointOpacity).toBeLessThanOrEqual(1)
  })
})

describe('as animações precisam ser perceptíveis, não só existir', () => {
  // A primeira versão tinha órbita e onda no cálculo, mas em escala tão baixa
  // que nenhuma das duas aparecia: uma volta levava mais de cinco minutos e o
  // brilho da crista somava 0,12 numa cor já clara.
  const FATOR_ORBITAL = 0.008
  const AMORTECIMENTO = 0.992
  const QUADROS_POR_SEGUNDO = 60

  function segundosPorVolta(swirl: number, raio = 25): number {
    // Velocidade terminal: o incremento por quadro dividido pela perda.
    const porQuadro = (swirl * FATOR_ORBITAL) / (1 - AMORTECIMENTO)
    const porSegundo = porQuadro * QUADROS_POR_SEGUNDO
    return (2 * Math.PI * raio) / porSegundo
  }

  it('em repouso a nuvem dá uma volta em menos de um minuto e meio', () => {
    expect(segundosPorVolta(ORB_THEMES.idle.swirl)).toBeLessThan(90)
  })

  it('em repouso ela não gira rápido a ponto de distrair', () => {
    expect(segundosPorVolta(ORB_THEMES.idle.swirl)).toBeGreaterThan(20)
  })

  it('os estados agitados giram visivelmente mais que o repouso', () => {
    expect(ORB_THEMES.executing.swirl).toBeGreaterThan(ORB_THEMES.idle.swirl * 2)
    expect(ORB_THEMES.transcribing.swirl).toBeGreaterThan(ORB_THEMES.idle.swirl * 2)
  })
})
