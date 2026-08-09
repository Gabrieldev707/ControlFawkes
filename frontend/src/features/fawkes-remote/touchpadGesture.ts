/**
 * Máquina de estados do touchpad: separa toque, movimento e arraste.
 *
 * O bug que motivou esta extração: o arraste era promovido depois de 350 ms
 * *e* de já ter havido movimento. Como o cursor já tinha andado antes do
 * POINTER_DOWN, o botão descia e subia praticamente no mesmo ponto, e o
 * Windows registrava isso como um clique acidental no meio do arraste.
 *
 * Agora o arraste é armado por pressão parada (long press sem mover), do mesmo
 * jeito que "pegar" um item num celular. Quando o POINTER_DOWN é enviado, o
 * cursor ainda não se moveu, então todo o movimento seguinte arrasta de fato.
 */

export type GesturePhase =
  | 'IDLE'
  | 'POSSIBLE_TAP'
  | 'MOVING'
  | 'DRAGGING'
  | 'CANCELLED'
  | 'COMPLETED'

export interface GestureLimits {
  /** Deslocamento máximo, em px, para um toque ainda contar como toque. */
  tapDistancePx: number
  /** Duração máxima, em ms, de um toque. */
  tapDurationMs: number
  /** Tempo parado, em ms, que arma o arraste. */
  dragHoldMs: number
}

export const DEFAULT_GESTURE_LIMITS: GestureLimits = {
  tapDistancePx: 10,
  tapDurationMs: 250,
  dragHoldMs: 350,
}

/** Efeitos que a tela deve executar. A máquina em si não toca em nada. */
export type GestureEffect =
  | { type: 'MOVE'; dx: number; dy: number }
  | { type: 'PRESS' }
  | { type: 'RELEASE' }
  | { type: 'CLICK' }

interface Pointer {
  id: number
  startX: number
  startY: number
  lastX: number
  lastY: number
  startedAt: number
}

export class TouchpadGesture {
  phase: GesturePhase = 'IDLE'

  private pointer: Pointer | null = null
  private extraPointers = 0
  private readonly limits: GestureLimits

  constructor(limits: GestureLimits = DEFAULT_GESTURE_LIMITS) {
    this.limits = limits
  }

  private distanceFromStart(x: number, y: number): number {
    if (!this.pointer) return 0
    return Math.hypot(x - this.pointer.startX, y - this.pointer.startY)
  }

  down(id: number, x: number, y: number, now: number): GestureEffect[] {
    if (this.pointer !== null) {
      // Segundo dedo: é pinça ou rolagem, nunca toque nem arraste.
      this.extraPointers += 1
      return this.cancel()
    }
    this.pointer = { id, startX: x, startY: y, lastX: x, lastY: y, startedAt: now }
    this.phase = 'POSSIBLE_TAP'
    return []
  }

  move(id: number, x: number, y: number): GestureEffect[] {
    if (!this.pointer || this.pointer.id !== id) return []
    if (this.phase === 'CANCELLED') return []

    const dx = x - this.pointer.lastX
    const dy = y - this.pointer.lastY
    this.pointer.lastX = x
    this.pointer.lastY = y

    if (this.phase === 'POSSIBLE_TAP' && this.distanceFromStart(x, y) > this.limits.tapDistancePx) {
      // Moveu antes de armar o arraste: daqui para frente é só mover o cursor,
      // sem apertar botão. É isso que impede o clique acidental.
      this.phase = 'MOVING'
    }

    if (dx === 0 && dy === 0) return []
    // O cursor acompanha o dedo desde o primeiro pixel, inclusive enquanto o
    // gesto ainda pode virar um toque: criar zona morta deixaria o movimento
    // com atraso perceptível. Quem decide se houve toque é o deslocamento
    // total no `up`, não o fato de termos emitido movimento.
    return [{ type: 'MOVE', dx, dy }]
  }

  /**
   * Chamado por um temporizador: o dedo ficou parado tempo suficiente para
   * armar o arraste. Só vale se ainda não houve movimento.
   */
  holdElapsed(): GestureEffect[] {
    if (this.phase !== 'POSSIBLE_TAP' || !this.pointer) return []
    this.phase = 'DRAGGING'
    // O botão desce antes de qualquer movimento: daqui para frente tudo
    // arrasta de verdade.
    return [{ type: 'PRESS' }]
  }

  up(id: number, x: number, y: number, now: number): GestureEffect[] {
    if (!this.pointer || this.pointer.id !== id) return []

    const moved = this.distanceFromStart(x, y)
    const held = now - this.pointer.startedAt
    const phase = this.phase
    this.pointer = null
    this.extraPointers = 0

    if (phase === 'DRAGGING') {
      this.phase = 'COMPLETED'
      return [{ type: 'RELEASE' }]
    }

    if (
      phase === 'POSSIBLE_TAP'
      && moved <= this.limits.tapDistancePx
      && held <= this.limits.tapDurationMs
    ) {
      this.phase = 'COMPLETED'
      return [{ type: 'CLICK' }]
    }

    this.phase = phase === 'CANCELLED' ? 'CANCELLED' : 'COMPLETED'
    return []
  }

  /** Multitoque, pointercancel, perda de captura, troca de tela. */
  cancel(): GestureEffect[] {
    const wasDragging = this.phase === 'DRAGGING'
    this.pointer = null
    this.phase = 'CANCELLED'
    // Soltar o botão é obrigatório: sem isso ele fica pressionado no Windows.
    return wasDragging ? [{ type: 'RELEASE' }] : []
  }

  reset(): void {
    this.pointer = null
    this.extraPointers = 0
    this.phase = 'IDLE'
  }
}
