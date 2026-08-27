import { useCallback, useEffect, useReducer } from 'react'

import { CURRENT_SCREENS, type NavigableScreen } from '../state/currentScreen'


const CHAVE = 'controlfawkes.screen'

/**
 * A tela em que a pessoa estava, de volta depois de um recarregamento.
 *
 * No iPhone, sair do navegador e voltar costuma descartar a página: o Safari
 * libera a memória da aba em segundo plano e a recarrega ao voltar. Como a
 * navegação vivia só na memória do React, isso jogava de volta para a tela
 * inicial no meio do uso — sem aviso e sem motivo aparente.
 *
 * `sessionStorage` é o lugar certo: sobrevive ao recarregamento, morre junto
 * com a aba, e não deixa rastro para a próxima visita.
 */
function telaGuardada(): NavigableScreen {
  try {
    const guardada = sessionStorage.getItem(CHAVE)
    const conhecida = CURRENT_SCREENS.find((tela) => tela === guardada)
    // Pareamento não é destino de navegação: quem manda nele é o estado da
    // autenticação, não a última tela aberta.
    return conhecida !== undefined && conhecida !== 'PAIRING' ? conhecida : 'HOME'
  } catch {
    // Navegador com armazenamento bloqueado: volta ao começo, como antes.
    return 'HOME'
  }
}


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
  const [state, dispatch] = useReducer(navigationReducer, null, () => ({
    currentScreen: telaGuardada(),
    previousScreen: null,
  }))

  useEffect(() => {
    try {
      sessionStorage.setItem(CHAVE, state.currentScreen)
    } catch {
      // Sem armazenamento a navegação continua funcionando; só não sobrevive
      // ao recarregamento, que é o comportamento antigo.
    }
  }, [state.currentScreen])

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
