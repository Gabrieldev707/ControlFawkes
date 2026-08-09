import React, { useCallback, useEffect, useRef } from 'react'
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Undo2 } from 'lucide-react'

import {
  REPEATABLE_NAVIGATION_ACTIONS,
  type NavigationAction,
} from '../../features/fawkes-remote/types'


interface DPadControlProps {
  disabled: boolean
  currentAction: NavigationAction | null
  onAction: (action: NavigationAction) => void
}

const REPEAT_DELAY_MS = 400
const REPEAT_INTERVAL_MS = 120

const DIRECTIONS = {
  NAVIGATE_UP: { label: 'Cima', icon: ArrowUp },
  NAVIGATE_LEFT: { label: 'Esquerda', icon: ArrowLeft },
  NAVIGATE_RIGHT: { label: 'Direita', icon: ArrowRight },
  NAVIGATE_DOWN: { label: 'Baixo', icon: ArrowDown },
} as const

export function DPadControl({ disabled, currentAction, onAction }: DPadControlProps) {
  const delayRef = useRef<number | null>(null)
  const intervalRef = useRef<number | null>(null)

  const stopRepeating = useCallback(() => {
    if (delayRef.current !== null) {
      window.clearTimeout(delayRef.current)
      delayRef.current = null
    }
    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [])

  useEffect(() => stopRepeating, [stopRepeating])

  const startRepeating = useCallback((action: NavigationAction) => {
    if (!REPEATABLE_NAVIGATION_ACTIONS.includes(action)) return
    stopRepeating()
    delayRef.current = window.setTimeout(() => {
      intervalRef.current = window.setInterval(() => onAction(action), REPEAT_INTERVAL_MS)
    }, REPEAT_DELAY_MS)
  }, [onAction, stopRepeating])

  const handlePress = useCallback((action: NavigationAction) => {
    if (disabled) return
    onAction(action)
    startRepeating(action)
  }, [disabled, onAction, startRepeating])

  function pressHandlers(action: NavigationAction) {
    return {
      onPointerDown: (event: React.PointerEvent) => {
        event.preventDefault()
        handlePress(action)
      },
      onPointerUp: stopRepeating,
      onPointerLeave: stopRepeating,
      onPointerCancel: stopRepeating,
      onBlur: stopRepeating,
      onClick: (event: React.MouseEvent) => {
        if (event.detail === 0) handlePress(action)
      },
    }
  }

  function directionButton(action: keyof typeof DIRECTIONS) {
    const { label, icon: Icon } = DIRECTIONS[action]
    return (
      <button
        type="button"
        className="dpad__button"
        style={{ gridArea: action }}
        aria-label={label}
        disabled={disabled}
        data-active={currentAction === action}
        {...pressHandlers(action)}
      >
        <Icon size={26} aria-hidden="true" />
      </button>
    )
  }

  return (
    <div className="control-dpad" aria-label="Navegação do controle">
      <div className="dpad" role="group" aria-label="Controle direcional">
        {directionButton('NAVIGATE_UP')}
        {directionButton('NAVIGATE_LEFT')}
        <button
          type="button"
          className="dpad__button dpad__button--confirm"
          style={{ gridArea: 'NAVIGATE_CONFIRM' }}
          aria-label="OK"
          disabled={disabled}
          data-active={currentAction === 'NAVIGATE_CONFIRM'}
          {...pressHandlers('NAVIGATE_CONFIRM')}
        >
          OK
        </button>
        {directionButton('NAVIGATE_RIGHT')}
        {directionButton('NAVIGATE_DOWN')}
      </div>

      <button
        type="button"
        className="control-dpad__back"
        aria-label="Voltar na TV"
        disabled={disabled}
        data-active={currentAction === 'NAVIGATE_BACK'}
        {...pressHandlers('NAVIGATE_BACK')}
      >
        <Undo2 size={18} aria-hidden="true" />
        Voltar
      </button>
    </div>
  )
}
