import React, { useCallback, useEffect, useRef } from 'react'
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  CornerDownLeft,
  Undo2,
} from 'lucide-react'

import { RemoteStatusText } from '../../components/fawkes-remote/RemoteStatusText'
import {
  REPEATABLE_NAVIGATION_ACTIONS,
  type NavigationAction,
} from '../../features/fawkes-remote/types'


// Log só em desenvolvimento, para diagnosticar o direcional no aparelho sem
// deixar rastro em produção.
function debugNavigation(action: NavigationAction, phase: string): void {
  if (import.meta.env.DEV) {
    console.info(`[nav] ${action} ${phase}`)
  }
}


interface NavigationScreenProps {
  disabled: boolean
  currentAction: NavigationAction | null
  statusMessage: string
  statusError: boolean
  onAction: (action: NavigationAction) => void
  onBack: () => void
}

// Espera antes de começar a repetir, e intervalo entre repetições. Os mesmos
// valores de um controle de TV: não dispara no toque curto.
const REPEAT_DELAY_MS = 400
const REPEAT_INTERVAL_MS = 120

const DIRECTIONS = {
  NAVIGATE_UP: { label: 'Cima', icon: ArrowUp },
  NAVIGATE_LEFT: { label: 'Esquerda', icon: ArrowLeft },
  NAVIGATE_RIGHT: { label: 'Direita', icon: ArrowRight },
  NAVIGATE_DOWN: { label: 'Baixo', icon: ArrowDown },
} as const

export function NavigationScreen({
  disabled,
  currentAction,
  statusMessage,
  statusError,
  onAction,
  onBack,
}: NavigationScreenProps) {
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

  // Soltar o dedo fora do botão, trocar de tela ou receber uma ligação não
  // podem deixar a seta repetindo sozinha.
  useEffect(() => stopRepeating, [stopRepeating])

  const startRepeating = useCallback((action: NavigationAction) => {
    if (!REPEATABLE_NAVIGATION_ACTIONS.includes(action)) return
    stopRepeating()
    delayRef.current = window.setTimeout(() => {
      intervalRef.current = window.setInterval(() => onAction(action), REPEAT_INTERVAL_MS)
    }, REPEAT_DELAY_MS)
  }, [onAction, stopRepeating])

  const handlePress = useCallback((action: NavigationAction) => {
    if (disabled) {
      debugNavigation(action, 'ignorado (controles desabilitados)')
      return
    }
    debugNavigation(action, 'enviado')
    onAction(action)
    startRepeating(action)
  }, [disabled, onAction, startRepeating])

  // Todos os botões respondem a pointerdown, inclusive OK e voltar.
  //
  // Antes o OK usava onClick e não funcionava no iPhone: o Safari cancela o
  // click quando o dedo se move alguns pixels entre o toque e o soltar, o que
  // acontece o tempo todo com o aparelho na mão. As setas já usavam
  // pointerdown e por isso funcionavam — era essa a diferença.
  //
  // Verificado que o caminho do backend estava correto antes de mexer aqui:
  // uma janela de teste no Windows recebeu KEYDOWN/KEYUP de Return sem
  // modificadores.
  function pressHandlers(action: NavigationAction) {
    return {
      onPointerDown: (event: React.PointerEvent) => {
        // Evita que o toque vire também um clique sintético e envie duas vezes.
        event.preventDefault()
        handlePress(action)
      },
      onPointerUp: stopRepeating,
      onPointerLeave: stopRepeating,
      onPointerCancel: stopRepeating,
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
    <main className="remote-screen navigation-screen" aria-labelledby="navigation-screen-title">
      <button
        type="button"
        className="remote-screen__back"
        aria-label="Voltar"
        onClick={onBack}
      >
        <ArrowLeft size={18} aria-hidden="true" />
        Voltar
      </button>

      <header className="remote-screen__header">
        <p className="remote-screen__eyebrow">ControlFawkes</p>
        <h2 id="navigation-screen-title">Navegação</h2>
      </header>

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

      <div className="navigation-screen__actions">
        <button
          type="button"
          className="navigation-action"
          disabled={disabled}
          data-active={currentAction === 'NAVIGATE_BACK'}
          {...pressHandlers('NAVIGATE_BACK')}
        >
          <Undo2 size={20} aria-hidden="true" />
          Voltar na TV
        </button>
        <p className="navigation-screen__hint">
          <CornerDownLeft size={14} aria-hidden="true" />
          Segure uma seta para repetir
        </p>
      </div>

      <RemoteStatusText message={statusMessage} error={statusError} />
    </main>
  )
}
