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
  | 'TWO_FINGER'
  | 'CANCELLED'
  | 'COMPLETED'

export interface GestureLimits {
  /** Deslocamento máximo, em px, para um toque ainda contar como toque. */
  tapDistancePx: number
  /** Duração máxima, em ms, de um toque. */
  tapDurationMs: number
  /** Tempo parado, em ms, que arma o arraste. */
  dragHoldMs: number
  /** Deslocamento mínimo, em px, para um movimento virar flick. */
  flickDistancePx: number
  /** Duração máxima, em ms, de um flick. Acima disso é arraste de cursor. */
  flickDurationMs: number
  /**
   * Quanto o eixo dominante precisa superar o outro para a direção ser clara.
   * Um gesto diagonal não vira seta: mandaria a seleção para um lugar que a
   * pessoa não pediu.
   */
  flickAxisRatio: number
}

export const DEFAULT_GESTURE_LIMITS: GestureLimits = {
  tapDistancePx: 10,
  tapDurationMs: 250,
  dragHoldMs: 350,
  flickDistancePx: 55,
  flickDurationMs: 260,
  flickAxisRatio: 1.6,
}

export const GESTURE_SENSITIVITIES = ['ALTA', 'PADRAO', 'BAIXA'] as const

export type GestureSensitivity = (typeof GESTURE_SENSITIVITIES)[number]

export const DEFAULT_GESTURE_SENSITIVITY: GestureSensitivity = 'PADRAO'

export function isGestureSensitivity(value: unknown): value is GestureSensitivity {
  return typeof value === 'string'
    && GESTURE_SENSITIVITIES.includes(value as GestureSensitivity)
}

/**
 * Quanto de gesto é preciso para virar seta, em três níveis.
 *
 * Os números do padrão saíram de raciocínio, não de polegar: foram escolhidos
 * antes de qualquer uso num celular de verdade. Em vez de fingir que estão
 * certos, ficam ajustáveis — a sessão real vira configuração em vez de
 * mudança de código.
 *
 * O eixo é um só, porque só existem dois jeitos de errar: a seta dispara
 * quando a pessoa queria mirar o cursor (exigir mais gesto), ou não dispara
 * quando ela queria navegar (exigir menos).
 */
export function gestureLimitsFor(sensitivity: GestureSensitivity): GestureLimits {
  if (sensitivity === 'ALTA') {
    // Pega gestos curtos e sem pressa. Bom para quem quase só navega.
    return { ...DEFAULT_GESTURE_LIMITS, flickDistancePx: 38, flickDurationMs: 340 }
  }
  if (sensitivity === 'BAIXA') {
    // Exige um gesto claramente rápido e longo, para o cursor ficar livre.
    return { ...DEFAULT_GESTURE_LIMITS, flickDistancePx: 78, flickDurationMs: 200 }
  }
  return DEFAULT_GESTURE_LIMITS
}

export type FlickDirection = 'UP' | 'DOWN' | 'LEFT' | 'RIGHT'

/** Efeitos que a tela deve executar. A máquina em si não toca em nada. */
export type GestureEffect =
  | { type: 'MOVE'; dx: number; dy: number }
  | { type: 'PRESS' }
  | { type: 'RELEASE' }
  | { type: 'CLICK' }
  | { type: 'FLICK'; direction: FlickDirection }
  | { type: 'TWO_FINGER_TAP' }

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
  private twoFingerAt: number | null = null
  /** Público para quem usa poder trocar de perfil entre um gesto e outro. */
  readonly limits: GestureLimits

  constructor(limits: GestureLimits = DEFAULT_GESTURE_LIMITS) {
    this.limits = limits
  }

  private distanceFromStart(x: number, y: number): number {
    if (!this.pointer) return 0
    return Math.hypot(x - this.pointer.startX, y - this.pointer.startY)
  }

  down(id: number, x: number, y: number, now: number): GestureEffect[] {
    if (this.pointer !== null) {
      // Segundo dedo: é pinça, rolagem ou o gesto de voltar. Nunca toque nem
      // arraste — mas o encostar de dois dedos precisa ser lembrado até o fim
      // do gesto, senão o `up` não teria como distingui-lo de um cancelamento.
      this.extraPointers += 1
      this.twoFingerAt = now
      const effects = this.cancel()
      this.phase = 'TWO_FINGER'
      return effects
    }
    this.pointer = { id, startX: x, startY: y, lastX: x, lastY: y, startedAt: now }
    this.phase = 'POSSIBLE_TAP'
    return []
  }

  /**
   * Toque com dois dedos: o "voltar" do gesto.
   *
   * Chamado quando o último dedo sai. Só conta se os dois encostaram e saíram
   * rápido — dois dedos parados na tela costumam ser pinça ou rolagem.
   */
  twoFingerTap(now: number): GestureEffect[] {
    if (this.phase !== 'TWO_FINGER' || this.twoFingerAt === null) return []
    const held = now - this.twoFingerAt
    this.twoFingerAt = null
    this.phase = 'COMPLETED'
    return held <= this.limits.tapDurationMs * 2 ? [{ type: 'TWO_FINGER_TAP' }] : []
  }

  private flickFrom(
    dx: number,
    dy: number,
    held: number,
  ): FlickDirection | null {
    if (held > this.limits.flickDurationMs) return null

    const horizontal = Math.abs(dx)
    const vertical = Math.abs(dy)
    const dominant = Math.max(horizontal, vertical)
    if (dominant < this.limits.flickDistancePx) return null
    // Diagonal não vira seta: sem eixo claro, qualquer escolha seria chute.
    if (dominant < Math.min(horizontal, vertical) * this.limits.flickAxisRatio) return null

    if (horizontal >= vertical) return dx > 0 ? 'RIGHT' : 'LEFT'
    return dy > 0 ? 'DOWN' : 'UP'
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
    const dx = x - this.pointer.startX
    const dy = y - this.pointer.startY
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

    // Movimento rápido e curto num eixo só: era um flick, não uma mira.
    //
    // A decisão fica para o fim do gesto de propósito. Decidir no começo
    // exigiria segurar o cursor por alguns quadros esperando para saber o que
    // o dedo ia fazer, e esse atraso no início de todo arraste é justamente o
    // que torna um touchpad ruim de usar. O preço é o cursor ter andado junto
    // com o flick — inofensivo, porque mover o cursor num menu não aciona nada.
    if (phase === 'MOVING') {
      const direction = this.flickFrom(dx, dy, held)
      if (direction !== null) {
        this.phase = 'COMPLETED'
        return [{ type: 'FLICK', direction }]
      }
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
    this.twoFingerAt = null
    this.phase = 'IDLE'
  }
}
