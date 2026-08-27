import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  CornerDownRight,
  Undo2,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'

import type {
  NavigationAction,
  PointerAction,
  PointerPayload,
  SafeKey,
} from '../../features/fawkes-remote/types'
import {
  DEFAULT_GESTURE_LIMITS,
  TouchpadGesture,
  type GestureLimits,
  type FlickDirection,
  type GestureEffect,
} from '../../features/fawkes-remote/touchpadGesture'


interface ControlDeckProps {
  disabled: boolean
  navigationDisabled: boolean
  currentNavigationAction: NavigationAction | null
  onNavigationAction: (action: NavigationAction) => void
  onPointerAction: (action: PointerAction, payload?: PointerPayload) => void
  onKey: (key: SafeKey) => void
  /** Ajustável em Ajustes: o polegar de cada um é diferente. */
  gestureLimits?: GestureLimits
  /**
   * O deslize rápido pode virar seta AGORA?
   *
   * Falso enquanto algo está tocando, e o motivo é medido. A seta vira
   * `ARROW_RIGHT`, e seta num player de vídeo não navega: ela PULA 5 ou 10
   * segundos. Relatado em 26/08/2026: "quando mexo o mouse no controle ele
   * sempre adianta tempo no que estou assistindo".
   *
   * O comentário do detector de flick dizia que o cursor andar junto era
   * "inofensivo, porque mover o cursor num menu não aciona nada". Vale num
   * menu; durante a reprodução, cada movimento rápido do dedo virava um salto
   * no filme.
   *
   * As setas dos cantos continuam, e é por isso que dá para desligar o gesto
   * sem perder a navegação: quem quer navegar durante a reprodução toca nelas.
   */
  flickHabilitado?: boolean
}

const FLICK_TO_NAVIGATION: Record<FlickDirection, NavigationAction> = {
  UP: 'NAVIGATE_UP',
  DOWN: 'NAVIGATE_DOWN',
  LEFT: 'NAVIGATE_LEFT',
  RIGHT: 'NAVIGATE_RIGHT',
}

const EDGE_ARROWS = [
  { action: 'NAVIGATE_UP', label: 'Cima', icon: ChevronUp },
  { action: 'NAVIGATE_LEFT', label: 'Esquerda', icon: ChevronLeft },
  { action: 'NAVIGATE_RIGHT', label: 'Direita', icon: ChevronRight },
  { action: 'NAVIGATE_DOWN', label: 'Baixo', icon: ChevronDown },
] as const

const REPEAT_DELAY_MS = 400
const REPEAT_INTERVAL_MS = 120
const clampDelta = (value: number) => Math.max(-160, Math.min(160, value))

/**
 * Uma superfície só, para navegar e apontar.
 *
 * Antes eram duas telas: o direcional no Controle e o cursor no Touchpad. Numa
 * interface de streaming as duas coisas se alternam o tempo todo — a seta anda
 * pelo menu, e aí aparece algo que só o ponteiro alcança —, então trocar de
 * tela a cada passo era o atrito principal do produto.
 *
 * Aqui os dois convivem sem modo:
 *   arrastar devagar → move o cursor
 *   flick rápido     → seta do direcional
 *   tocar            → clique
 *   dois dedos       → voltar
 *   segurar parado   → arrasta segurando o botão
 *
 * As setas das bordas continuam sendo botões de verdade. Gesto sozinho seria
 * inacessível para quem usa leitor de tela ou tem limitação motora, e também
 * é o que ensina o gesto a quem está chegando agora.
 */
export function ControlDeck({
  disabled,
  navigationDisabled,
  currentNavigationAction,
  onNavigationAction,
  onPointerAction,
  onKey,
  gestureLimits = DEFAULT_GESTURE_LIMITS,
  flickHabilitado = true,
}: ControlDeckProps) {
  const [hint, setHint] = useState<string | null>(null)
  const gestureRef = useRef(new TouchpadGesture(gestureLimits))
  // Numa `ref` porque `runEffects` é chamado de dentro de manipuladores de
  // ponteiro que não são recriados a cada render: lido direto, o valor ficaria
  // congelado no que era quando o manipulador nasceu.
  const flickHabilitadoRef = useRef(flickHabilitado)
  flickHabilitadoRef.current = flickHabilitado
  const holdTimerRef = useRef<number | null>(null)
  const accumulatedRef = useRef({ dx: 0, dy: 0 })
  const frameRef = useRef<number | null>(null)
  const hintTimerRef = useRef<number | null>(null)
  const activePointers = useRef(new Set<number>())
  const repeatDelayRef = useRef<number | null>(null)
  const repeatIntervalRef = useRef<number | null>(null)

  const navigationRef = useRef(onNavigationAction)
  navigationRef.current = onNavigationAction
  const pointerRef = useRef(onPointerAction)
  pointerRef.current = onPointerAction

  const showHint = (text: string) => {
    setHint(text)
    if (hintTimerRef.current !== null) window.clearTimeout(hintTimerRef.current)
    hintTimerRef.current = window.setTimeout(() => setHint(null), 900)
  }

  const flushMovement = () => {
    frameRef.current = null
    const { dx, dy } = accumulatedRef.current
    accumulatedRef.current = { dx: 0, dy: 0 }
    const boundedDx = clampDelta(dx)
    const boundedDy = clampDelta(dy)
    if (boundedDx !== 0 || boundedDy !== 0) {
      pointerRef.current('POINTER_MOVE', { dx: boundedDx, dy: boundedDy })
    }
  }

  const clearHoldTimer = () => {
    if (holdTimerRef.current !== null) {
      window.clearTimeout(holdTimerRef.current)
      holdTimerRef.current = null
    }
  }

  const stopRepeating = () => {
    if (repeatDelayRef.current !== null) {
      window.clearTimeout(repeatDelayRef.current)
      repeatDelayRef.current = null
    }
    if (repeatIntervalRef.current !== null) {
      window.clearInterval(repeatIntervalRef.current)
      repeatIntervalRef.current = null
    }
  }

  const runEffects = (effects: GestureEffect[]) => {
    for (const effect of effects) {
      if (effect.type === 'MOVE') {
        accumulatedRef.current.dx += effect.dx
        accumulatedRef.current.dy += effect.dy
        if (frameRef.current === null) {
          frameRef.current = requestAnimationFrame(flushMovement)
        }
      } else if (effect.type === 'PRESS') {
        pointerRef.current('POINTER_DOWN')
        showHint('arrastando')
      } else if (effect.type === 'RELEASE') {
        pointerRef.current('POINTER_UP')
      } else if (effect.type === 'CLICK') {
        pointerRef.current('POINTER_CLICK')
        showHint('clique')
      } else if (effect.type === 'FLICK') {
        if (!flickHabilitadoRef.current) {
          // Tocando: a seta pularia o filme em vez de navegar. O cursor já se
          // moveu junto com o gesto, que é o que a pessoa queria.
          showHint('use as setas')
          continue
        }
        navigationRef.current(FLICK_TO_NAVIGATION[effect.direction])
        showHint(effect.direction)
      } else if (effect.type === 'TWO_FINGER_TAP') {
        navigationRef.current('NAVIGATE_BACK')
        showHint('voltar')
      }
    }
  }

  const abortGesture = () => {
    clearHoldTimer()
    if (frameRef.current !== null) {
      cancelAnimationFrame(frameRef.current)
      frameRef.current = null
    }
    accumulatedRef.current = { dx: 0, dy: 0 }
    runEffects(gestureRef.current.cancel())
    gestureRef.current.reset()
  }

  // Sair da tela no meio de um arraste não pode deixar o botão pressionado.
  useEffect(() => () => {
    abortGesture()
    stopRepeating()
    if (hintTimerRef.current !== null) window.clearTimeout(hintTimerRef.current)
  }, [])

  useEffect(() => {
    if (disabled) abortGesture()
  }, [disabled])

  // Os limites são lidos no início de cada gesto, nunca no meio.
  //
  // A versão anterior trocava a máquina de estados num `useEffect` que
  // dependia do objeto de limites. Como quem chama monta esse objeto a cada
  // render, o efeito rodava em todo render da página — e a página re-renderiza
  // o tempo todo (status, tocando agora, contagem de reconexão). Resultado: no
  // meio de um arrasto a máquina era substituída por uma zerada, e o cursor
  // simplesmente parava de responder.
  const limitesRef = useRef(gestureLimits)
  limitesRef.current = gestureLimits

  const handlePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault()
    if (disabled) return
    activePointers.current.add(event.pointerId)
    event.currentTarget.setPointerCapture?.(event.pointerId)
    // Fronteira segura para adotar a sensibilidade nova: entre gestos, nunca
    // dentro de um. O toque seguinte já usa o que foi escolhido em Ajustes.
    if (activePointers.current.size === 1 && gestureRef.current.limits !== limitesRef.current) {
      gestureRef.current = new TouchpadGesture(limitesRef.current)
    }
    runEffects(gestureRef.current.down(
      event.pointerId,
      event.clientX,
      event.clientY,
      Date.now(),
    ))
    clearHoldTimer()
    holdTimerRef.current = window.setTimeout(() => {
      holdTimerRef.current = null
      runEffects(gestureRef.current.holdElapsed())
    }, limitesRef.current.dragHoldMs)
  }

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault()
    if (disabled) return
    const before = gestureRef.current.phase
    runEffects(gestureRef.current.move(event.pointerId, event.clientX, event.clientY))
    if (before === 'POSSIBLE_TAP' && gestureRef.current.phase !== 'POSSIBLE_TAP') {
      clearHoldTimer()
    }
  }

  const handlePointerUp = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault()
    clearHoldTimer()
    activePointers.current.delete(event.pointerId)
    if (frameRef.current !== null) {
      cancelAnimationFrame(frameRef.current)
      flushMovement()
    }
    runEffects(gestureRef.current.up(
      event.pointerId,
      event.clientX,
      event.clientY,
      Date.now(),
    ))
    // O voltar de dois dedos só é resolvido quando o último dedo sai: antes
    // disso não dá para saber se foi toque, pinça ou rolagem.
    if (activePointers.current.size === 0) {
      runEffects(gestureRef.current.twoFingerTap(Date.now()))
      gestureRef.current.reset()
    }
  }

  const handlePointerCancel = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault()
    activePointers.current.delete(event.pointerId)
    abortGesture()
  }

  function arrowHandlers(action: NavigationAction) {
    const press = () => {
      if (disabled || navigationDisabled) return
      onNavigationAction(action)
      stopRepeating()
      // Segurar a seta repete, como num controle de verdade.
      repeatDelayRef.current = window.setTimeout(() => {
        repeatIntervalRef.current = window.setInterval(
          () => onNavigationAction(action),
          REPEAT_INTERVAL_MS,
        )
      }, REPEAT_DELAY_MS)
    }
    return {
      onPointerDown: (event: ReactPointerEvent) => {
        // Impede que o toque na seta escorra para a superfície e vire clique.
        event.stopPropagation()
        event.preventDefault()
        press()
      },
      onPointerUp: (event: ReactPointerEvent) => {
        event.stopPropagation()
        stopRepeating()
      },
      onPointerLeave: stopRepeating,
      onPointerCancel: stopRepeating,
      onBlur: stopRepeating,
      onClick: (event: React.MouseEvent) => {
        event.stopPropagation()
        // Só teclado: o toque já foi tratado no pointerdown.
        if (event.detail === 0) press()
      },
    }
  }

  return (
    <section className="control-deck" aria-label="Superfície de controle">
      <div
        className="control-deck__surface"
        role="application"
        aria-label="Controle direcional"
        aria-describedby="control-deck-help"
        onContextMenu={(event) => event.preventDefault()}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerCancel}
        onLostPointerCapture={handlePointerCancel}
        onWheel={(event) => {
          event.preventDefault()
          abortGesture()
          if (event.deltaY !== 0) {
            onPointerAction('POINTER_SCROLL', { delta: event.deltaY > 0 ? -120 : 120 })
          }
        }}
      >
        {EDGE_ARROWS.map(({ action, label, icon: Icon }) => (
          <button
            key={action}
            type="button"
            className="control-deck__arrow"
            data-direction={action}
            aria-label={label}
            disabled={disabled || navigationDisabled}
            data-active={currentNavigationAction === action}
            {...arrowHandlers(action)}
          >
            <Icon size={20} aria-hidden="true" />
          </button>
        ))}

        <div className="control-deck__center" aria-hidden="true">
          {hint !== null ? (
            <span className="control-deck__hint">{hint}</span>
          ) : (
            <>
              <span className="control-deck__ok">OK</span>
              <span className="control-deck__legend">toque</span>
            </>
          )}
        </div>
      </div>

      <div className="control-deck__actions">
        <button
          type="button"
          className="control-deck__confirm"
          aria-label="OK"
          disabled={disabled || navigationDisabled}
          data-active={currentNavigationAction === 'NAVIGATE_CONFIRM'}
          onClick={() => onNavigationAction('NAVIGATE_CONFIRM')}
        >
          OK
        </button>
        {/* Tela de login e seleção de perfil não andam com seta: elas andam
            com Tab. Sem isto, entrar numa conta exigia sair para a tela de
            teclado ou mirar cada campo com o cursor. */}
        <button
          type="button"
          className="control-deck__next"
          aria-label="Próximo campo"
          disabled={disabled}
          onClick={() => onKey('TAB')}
        >
          <CornerDownRight size={15} aria-hidden="true" />
          Campo
        </button>
        <button
          type="button"
          className="control-deck__back"
          aria-label="Voltar na TV"
          disabled={disabled || navigationDisabled}
          data-active={currentNavigationAction === 'NAVIGATE_BACK'}
          onClick={() => onNavigationAction('NAVIGATE_BACK')}
        >
          <Undo2 size={16} aria-hidden="true" />
          Voltar
        </button>
      </div>

      <p className="control-deck__help" id="control-deck-help">
        {flickHabilitado
          ? 'Deslize rápido para navegar · arraste devagar para o cursor · toque para clicar'
          : 'Tocando: use as setas para navegar · arraste para o cursor · toque para clicar'}
      </p>
    </section>
  )
}
