import { useCallback, useEffect, useRef, useState } from 'react'

import type {
  KeyboardAction,
  MediaAction,
  NavigationAction,
  PointerAction,
  VolumeAction,
} from '../features/fawkes-remote/types'
import { generateRequestId } from '../utils/uuid'


type ActiveCommand =
  | { kind: 'media'; action: MediaAction }
  | { kind: 'volume'; action: VolumeAction }
  | { kind: 'pointer'; action: PointerAction }
  | { kind: 'keyboard'; action: KeyboardAction }
  | { kind: 'navigation'; action: NavigationAction }

export function useCommandFeedback() {
  const requestIdRef = useRef<string | null>(null)
  const resetTimerRef = useRef<number | null>(null)
  const [activeCommand, setActiveCommand] = useState<ActiveCommand | null>(null)

  const cancelTimer = useCallback(() => {
    if (resetTimerRef.current !== null) {
      window.clearTimeout(resetTimerRef.current)
      resetTimerRef.current = null
    }
  }, [])

  useEffect(() => cancelTimer, [cancelTimer])

  const begin = useCallback((command: ActiveCommand | null = null): string => {
    cancelTimer()
    const requestId = generateRequestId()
    requestIdRef.current = requestId
    setActiveCommand(command)
    return requestId
  }, [cancelTimer])

  const cancel = useCallback(() => {
    cancelTimer()
    requestIdRef.current = null
    setActiveCommand(null)
  }, [cancelTimer])

  const scheduleReset = useCallback((delayMs: number, afterReset: () => void) => {
    cancelTimer()
    resetTimerRef.current = window.setTimeout(() => {
      resetTimerRef.current = null
      requestIdRef.current = null
      setActiveCommand(null)
      afterReset()
    }, delayMs)
  }, [cancelTimer])

  const isCurrent = useCallback((requestId: string): boolean => (
    requestIdRef.current === requestId
  ), [])

  const hasPending = useCallback((): boolean => requestIdRef.current !== null, [])

  return {
    begin,
    cancel,
    scheduleReset,
    isCurrent,
    hasPending,
    currentMediaAction: activeCommand?.kind === 'media' ? activeCommand.action : null,
    currentVolumeAction: activeCommand?.kind === 'volume' ? activeCommand.action : null,
    currentPointerAction: activeCommand?.kind === 'pointer' ? activeCommand.action : null,
    currentKeyboardAction: activeCommand?.kind === 'keyboard' ? activeCommand.action : null,
    currentNavigationAction: activeCommand?.kind === 'navigation' ? activeCommand.action : null,
  }
}
