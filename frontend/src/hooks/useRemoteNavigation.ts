import { useCallback, useReducer } from 'react'

import type { NavigableScreen } from '../state/currentScreen'


interface NavigationState {
  currentScreen: NavigableScreen
  previousScreen: NavigableScreen | null
}

type NavigationAction =
  | { type: 'NAVIGATE'; screen: NavigableScreen }
  | { type: 'BACK' }

function navigationReducer(
  state: NavigationState,
  action: NavigationAction,
): NavigationState {
  if (action.type === 'BACK') {
    return {
      currentScreen: state.previousScreen ?? 'HOME',
      previousScreen: null,
    }
  }

  if (action.screen === state.currentScreen) return state
  return {
    currentScreen: action.screen,
    previousScreen: action.screen === 'HOME' ? null : state.currentScreen,
  }
}

export function useRemoteNavigation() {
  const [state, dispatch] = useReducer(navigationReducer, {
    currentScreen: 'HOME',
    previousScreen: null,
  })

  const navigate = useCallback((screen: NavigableScreen) => {
    dispatch({ type: 'NAVIGATE', screen })
  }, [])

  const goBack = useCallback(() => {
    dispatch({ type: 'BACK' })
  }, [])

  return {
    currentScreen: state.currentScreen,
    navigate,
    goBack,
  }
}
