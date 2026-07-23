import { ArrowLeft, MousePointer2, OctagonAlert, Power, RotateCcw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'

import { RemoteStatusText } from '../../components/fawkes-remote/RemoteStatusText'
import type { PointerAction, PointerPayload } from '../../features/fawkes-remote/types'
import {
  DEFAULT_GESTURE_LIMITS,
  TouchpadGesture,
  type GestureEffect,
} from '../../features/fawkes-remote/touchpadGesture'


interface TouchpadScreenProps {
  disabled: boolean
  currentAction?: PointerAction | null
  statusMessage: string
  statusError: boolean
  onAction: (action: PointerAction, payload?: PointerPayload) => void
  onBack: () => void
}

const clampDelta = (value: number) => Math.max(-160, Math.min(160, value))

export function TouchpadScreen({
  disabled,
  currentAction = null,
  statusMessage,
  statusError,
  onAction,
  onBack,
}: TouchpadScreenProps) {
  const [active, setActive] = useState(false)
  // A separação entre toque, movimento e arraste vive numa máquina de estados
  // própria e testada; aqui só traduzimos eventos e executamos os efeitos.
  const gestureRef = useRef(new TouchpadGesture())
  const holdTimerRef = useRef<number | null>(null)
  const accumulatedRef = useRef({ dx: 0, dy: 0 })
  const frameRef = useRef<number | null>(null)
  const actionRef = useRef(onAction)
  actionRef.current = onAction

  const flushMovement = () => {
    frameRef.current = null
    const { dx, dy } = accumulatedRef.current
    accumulatedRef.current = { dx: 0, dy: 0 }
    const boundedDx = clampDelta(dx)
    const boundedDy = clampDelta(dy)
    if (boundedDx !== 0 || boundedDy !== 0) {
      actionRef.current('POINTER_MOVE', { dx: boundedDx, dy: boundedDy })
    }
  }

  const clearHoldTimer = () => {
    if (holdTimerRef.current !== null) {
      window.clearTimeout(holdTimerRef.current)
      holdTimerRef.current = null
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
        actionRef.current('POINTER_DOWN')
      } else if (effect.type === 'RELEASE') {
        actionRef.current('POINTER_UP')
      } else if (effect.type === 'CLICK') {
        actionRef.current('POINTER_CLICK')
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

  const deactivate = () => {
    abortGesture()
    setActive(false)
  }

  useEffect(() => {
    if (disabled && active) deactivate()
  }, [disabled, active])

  // Sair da tela no meio de um arraste não pode deixar o botão pressionado.
  useEffect(() => () => abortGesture(), [])

  const handlePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault()
    if (!active || disabled) return
    event.currentTarget.setPointerCapture?.(event.pointerId)
    runEffects(gestureRef.current.down(
      event.pointerId,
      event.clientX,
      event.clientY,
      Date.now(),
    ))
    clearHoldTimer()
    // O arraste é armado por pressão parada. Enviar o POINTER_DOWN antes de
    // qualquer movimento é o que evita o clique acidental.
    holdTimerRef.current = window.setTimeout(() => {
      holdTimerRef.current = null
      runEffects(gestureRef.current.holdElapsed())
    }, DEFAULT_GESTURE_LIMITS.dragHoldMs)
  }

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault()
    if (disabled) return
    const before = gestureRef.current.phase
    runEffects(gestureRef.current.move(
      event.pointerId,
      event.clientX,
      event.clientY,
    ))
    // Assim que vira movimento, o arraste não pode mais ser armado.
    if (before === 'POSSIBLE_TAP' && gestureRef.current.phase !== 'POSSIBLE_TAP') {
      clearHoldTimer()
    }
  }

  const handlePointerUp = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault()
    clearHoldTimer()
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
    gestureRef.current.reset()
  }

  const handlePointerCancel = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault()
    abortGesture()
  }

  return (
    <main
      className="remote-screen touchpad-screen"
      aria-labelledby="touchpad-screen-title"
      data-active-action={currentAction ?? undefined}
    >
      <button type="button" className="remote-screen__back" aria-label="Voltar" onClick={onBack}>
        <ArrowLeft size={18} aria-hidden="true" />
        Voltar
      </button>

      <div className="touchpad-screen__heading">
        <p className="remote-screen__eyebrow">Entrada remota</p>
        <h2 id="touchpad-screen-title">Touchpad</h2>
        <p>Movimento relativo com limite de envio e parada segura.</p>
      </div>

      <RemoteStatusText message={statusMessage} error={statusError} />

      {!active ? (
        <section className="touchpad-activation">
          <MousePointer2 size={34} aria-hidden="true" />
          <p>O ponteiro só responde depois da ativação explícita.</p>
          <button type="button" disabled={disabled} onClick={() => setActive(true)}>
            <Power size={18} aria-hidden="true" />
            Ativar touchpad
          </button>
        </section>
      ) : (
        <section className="touchpad-controls">
          <div
            className="touchpad-surface"
            role="application"
            aria-label="Área do touchpad"
            tabIndex={0}
            onContextMenu={(event) => event.preventDefault()}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            onPointerCancel={handlePointerCancel}
            onLostPointerCapture={handlePointerCancel}
            onClick={(event) => {
              event.preventDefault()
              event.stopPropagation()
            }}
            onWheel={(event) => {
              event.preventDefault()
              // Rolagem cancela o toque em andamento: não é clique.
              abortGesture()
              if (event.deltaY !== 0) {
                onAction('POINTER_SCROLL', { delta: event.deltaY > 0 ? -120 : 120 })
              }
            }}
          >
            <MousePointer2 size={30} aria-hidden="true" />
            <strong>Mova para controlar</strong>
            <span>Toque para clicar · segure parado e arraste para mover</span>
          </div>

          <div className="touchpad-clicks" aria-label="Cliques do touchpad">
            <button type="button" disabled={disabled} onClick={() => onAction('POINTER_CLICK')}>
              Clique
            </button>
            <button type="button" disabled={disabled} onClick={() => onAction('POINTER_DOUBLE_CLICK')}>
              Clique duplo
            </button>
            <button type="button" disabled={disabled} onClick={() => onAction('POINTER_RIGHT_CLICK')}>
              Clique direito
            </button>
          </div>

          <div className="touchpad-safety">
            <button type="button" className="touchpad-safety__disable" onClick={deactivate}>
              <RotateCcw size={17} aria-hidden="true" />
              Desativar touchpad
            </button>
            <button type="button" className="touchpad-safety__emergency" onClick={deactivate}>
              <OctagonAlert size={17} aria-hidden="true" />
              Parada de emergência
            </button>
          </div>
        </section>
      )}
    </main>
  )
}
