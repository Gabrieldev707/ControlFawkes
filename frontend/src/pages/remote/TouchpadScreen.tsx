import { ArrowLeft, MousePointer2, OctagonAlert, Power, RotateCcw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'

import { RemoteStatusText } from '../../components/fawkes-remote/RemoteStatusText'
import type { PointerAction, PointerPayload } from '../../features/fawkes-remote/types'


interface TouchpadScreenProps {
  disabled: boolean
  currentAction?: PointerAction | null
  statusMessage: string
  statusError: boolean
  onAction: (action: PointerAction, payload?: PointerPayload) => void
  onBack: () => void
}

interface PointerGesture {
  id: number
  startedAt: number
  startX: number
  startY: number
  lastX: number
  lastY: number
  clickCancelled: boolean
  dragging: boolean
}

const CLICK_DISTANCE_PX = 6
const TAP_MAX_DURATION_MS = 250
const DRAG_HOLD_DURATION_MS = 350
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
  const gestureRef = useRef<PointerGesture | null>(null)
  const activePointersRef = useRef(new Set<number>())
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

  const resetGesture = (release: boolean, flushPending = true) => {
    if (frameRef.current !== null) {
      cancelAnimationFrame(frameRef.current)
      if (flushPending) {
        flushMovement()
      } else {
        frameRef.current = null
      }
    }
    if (release && gestureRef.current?.dragging) {
      actionRef.current('POINTER_UP')
    }
    gestureRef.current = null
    accumulatedRef.current = { dx: 0, dy: 0 }
  }

  const deactivate = () => {
    resetGesture(true, false)
    activePointersRef.current.clear()
    setActive(false)
  }

  useEffect(() => {
    if (disabled && active) deactivate()
  }, [disabled, active])

  useEffect(() => () => resetGesture(true, false), [])

  const handlePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault()
    if (!active || disabled) return
    activePointersRef.current.add(event.pointerId)
    if (gestureRef.current) {
      gestureRef.current.clickCancelled = true
      return
    }
    event.currentTarget.setPointerCapture?.(event.pointerId)
    gestureRef.current = {
      id: event.pointerId,
      startedAt: Date.now(),
      startX: event.clientX,
      startY: event.clientY,
      lastX: event.clientX,
      lastY: event.clientY,
      clickCancelled: false,
      dragging: false,
    }
  }

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault()
    const gesture = gestureRef.current
    if (!gesture || gesture.id !== event.pointerId || disabled) return
    const dx = event.clientX - gesture.lastX
    const dy = event.clientY - gesture.lastY
    gesture.lastX = event.clientX
    gesture.lastY = event.clientY
    if (dx === 0 && dy === 0) return

    const displacement = Math.hypot(
      event.clientX - gesture.startX,
      event.clientY - gesture.startY,
    )
    if (displacement > CLICK_DISTANCE_PX || activePointersRef.current.size > 1) {
      gesture.clickCancelled = true
    }
    if (
      !gesture.dragging
      && displacement > CLICK_DISTANCE_PX
      && Date.now() - gesture.startedAt >= DRAG_HOLD_DURATION_MS
    ) {
      gesture.dragging = true
      actionRef.current('POINTER_DOWN')
    }
    accumulatedRef.current.dx += dx
    accumulatedRef.current.dy += dy
    if (frameRef.current === null) {
      frameRef.current = requestAnimationFrame(flushMovement)
    }
  }

  const handlePointerUp = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault()
    activePointersRef.current.delete(event.pointerId)
    const gesture = gestureRef.current
    if (!gesture || gesture.id !== event.pointerId) return
    const displacement = Math.hypot(
      event.clientX - gesture.startX,
      event.clientY - gesture.startY,
    )
    if (displacement > CLICK_DISTANCE_PX) {
      gesture.clickCancelled = true
    }
    const shouldClick = !gesture.clickCancelled
      && !gesture.dragging
      && Date.now() - gesture.startedAt <= TAP_MAX_DURATION_MS
    if (gesture.dragging) {
      resetGesture(true)
    } else {
      resetGesture(false)
    }
    if (shouldClick) {
      actionRef.current('POINTER_CLICK')
    }
  }

  const handlePointerCancel = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault()
    activePointersRef.current.delete(event.pointerId)
    if (gestureRef.current?.id === event.pointerId) {
      gestureRef.current.clickCancelled = true
      resetGesture(true, false)
    }
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
            onClick={(event) => {
              event.preventDefault()
              event.stopPropagation()
            }}
            onWheel={(event) => {
              event.preventDefault()
              if (gestureRef.current) {
                gestureRef.current.clickCancelled = true
              }
              if (event.deltaY !== 0) {
                onAction('POINTER_SCROLL', { delta: event.deltaY > 0 ? -120 : 120 })
              }
            }}
          >
            <MousePointer2 size={30} aria-hidden="true" />
            <strong>Mova para controlar</strong>
            <span>Toque para clicar · segure e arraste para mover</span>
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
