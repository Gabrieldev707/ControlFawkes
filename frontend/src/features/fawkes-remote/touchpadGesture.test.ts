import { describe, expect, it } from 'vitest'

import {
  DEFAULT_GESTURE_LIMITS,
  GESTURE_SENSITIVITIES,
  TouchpadGesture,
  gestureLimitsFor,
  type GestureLimits,
} from './touchpadGesture'


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
    // O que importa é o efeito: dois dedos nunca podem virar um clique.
    const g = gesture()
    g.down(1, 100, 100, 0)
    g.down(2, 150, 150, 10)

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

describe('TouchpadGesture flick', () => {
  const rapido = 120

  function deslizar(g: TouchpadGesture, dx: number, dy: number, ms = rapido) {
    g.down(1, 200, 200, 0)
    g.move(1, 200 + dx / 2, 200 + dy / 2)
    g.move(1, 200 + dx, 200 + dy)
    return g.up(1, 200 + dx, 200 + dy, ms)
  }

  it.each([
    ['RIGHT', 90, 0],
    ['LEFT', -90, 0],
    ['DOWN', 0, 90],
    ['UP', 0, -90],
  ])('reconhece o flick para %s', (direcao, dx, dy) => {
    expect(deslizar(new TouchpadGesture(), dx, dy)).toEqual([
      { type: 'FLICK', direction: direcao },
    ])
  })

  it('não vira seta quando o dedo foi devagar', () => {
    // Movimento lento é mira de cursor. Transformá-lo em seta tiraria a
    // possibilidade de apontar com precisão.
    expect(deslizar(new TouchpadGesture(), 90, 0, 900)).toEqual([])
  })

  it('não vira seta quando o deslocamento foi curto', () => {
    expect(deslizar(new TouchpadGesture(), 30, 0)).toEqual([])
  })

  it('não chuta direção num gesto diagonal', () => {
    // Sem eixo dominante, qualquer seta seria adivinhação.
    expect(deslizar(new TouchpadGesture(), 80, 75)).toEqual([])
  })

  it('o cursor acompanha o dedo mesmo no gesto que vira flick', () => {
    // O cursor andar junto é o preço de decidir no fim do gesto — e é
    // inofensivo, porque mover o cursor num menu não aciona nada.
    const g = new TouchpadGesture()
    g.down(1, 200, 200, 0)
    const efeitos = g.move(1, 260, 200)

    expect(efeitos).toEqual([{ type: 'MOVE', dx: 60, dy: 0 }])
  })

  it('um toque continuado ainda arrasta, sem virar flick', () => {
    const g = new TouchpadGesture()
    g.down(1, 200, 200, 0)
    expect(g.holdElapsed()).toEqual([{ type: 'PRESS' }])
    g.move(1, 300, 200)

    expect(g.up(1, 300, 200, 100)).toEqual([{ type: 'RELEASE' }])
  })
})

describe('TouchpadGesture voltar com dois dedos', () => {
  it('dois dedos que encostam e saem rápido viram voltar', () => {
    const g = new TouchpadGesture()
    g.down(1, 100, 100, 0)
    g.down(2, 150, 150, 20)
    g.up(1, 100, 100, 120)

    expect(g.twoFingerTap(130)).toEqual([{ type: 'TWO_FINGER_TAP' }])
  })

  it('dois dedos parados na tela não viram voltar', () => {
    // Pinça e rolagem começam assim; disparar voltar sairia da tela do usuário.
    const g = new TouchpadGesture()
    g.down(1, 100, 100, 0)
    g.down(2, 150, 150, 20)

    expect(g.twoFingerTap(3000)).toEqual([])
  })

  it('um dedo só nunca dispara voltar', () => {
    const g = new TouchpadGesture()
    g.down(1, 100, 100, 0)
    g.up(1, 100, 100, 50)

    expect(g.twoFingerTap(60)).toEqual([])
  })
})

describe('sensibilidade do gesto', () => {
  it('alta exige menos deslize e aceita gesto mais lento', () => {
    const alta = gestureLimitsFor('ALTA')
    const padrao = gestureLimitsFor('PADRAO')

    expect(alta.flickDistancePx).toBeLessThan(padrao.flickDistancePx)
    expect(alta.flickDurationMs).toBeGreaterThan(padrao.flickDurationMs)
  })

  it('baixa exige mais deslize e mais pressa, liberando o cursor', () => {
    const baixa = gestureLimitsFor('BAIXA')
    const padrao = gestureLimitsFor('PADRAO')

    expect(baixa.flickDistancePx).toBeGreaterThan(padrao.flickDistancePx)
    expect(baixa.flickDurationMs).toBeLessThan(padrao.flickDurationMs)
  })

  it('só mexe no flick: toque e arraste continuam iguais em todos os níveis', () => {
    // Mudar o toque junto faria o ajuste de navegação alterar o clique, que é
    // outra coisa e não foi o que a pessoa pediu.
    for (const nivel of GESTURE_SENSITIVITIES) {
      const limites = gestureLimitsFor(nivel)
      expect(limites.tapDistancePx).toBe(DEFAULT_GESTURE_LIMITS.tapDistancePx)
      expect(limites.tapDurationMs).toBe(DEFAULT_GESTURE_LIMITS.tapDurationMs)
      expect(limites.dragHoldMs).toBe(DEFAULT_GESTURE_LIMITS.dragHoldMs)
    }
  })

  it('um deslize de 45px vira seta na alta e não na baixa', () => {
    function deslizar(limites: GestureLimits) {
      const g = new TouchpadGesture(limites)
      g.down(1, 200, 200, 0)
      g.move(1, 225, 200)
      g.move(1, 245, 200)
      return g.up(1, 245, 200, 150)
    }

    expect(deslizar(gestureLimitsFor('ALTA'))).toEqual([{ type: 'FLICK', direction: 'RIGHT' }])
    expect(deslizar(gestureLimitsFor('BAIXA'))).toEqual([])
  })
})
