import {
  Gamepad2,
  House,
  LayoutGrid,
  MousePointer2,
  Navigation,
  Settings,
} from 'lucide-react'

import type { NavigableScreen } from '../../state/currentScreen'


interface RemoteNavigationProps {
  currentScreen: NavigableScreen
  onNavigate: (screen: NavigableScreen) => void
}

const NAV_ITEMS = [
  { screen: 'HOME', label: 'Início', icon: House },
  { screen: 'REMOTE_CONTROL', label: 'Controle', icon: Gamepad2 },
  { screen: 'NAVIGATION', label: 'Navegar', icon: Navigation },
  { screen: 'TOUCHPAD', label: 'Touchpad', icon: MousePointer2 },
  { screen: 'PLATFORMS', label: 'Plataformas', icon: LayoutGrid },
  { screen: 'SETTINGS', label: 'Ajustes', icon: Settings },
] as const satisfies ReadonlyArray<{
  screen: NavigableScreen
  label: string
  icon: typeof House
}>

export function RemoteNavigation({ currentScreen, onNavigate }: RemoteNavigationProps) {
  return (
    <nav className="remote-navigation" aria-label="Navegação principal">
      {NAV_ITEMS.map(({ screen, label, icon: Icon }) => {
        const active = currentScreen === screen
        return (
          <button
            key={screen}
            type="button"
            className={`remote-navigation__item${active ? ' remote-navigation__item--active' : ''}`}
            aria-label={`Abrir ${label}`}
            aria-current={active ? 'page' : undefined}
            onClick={() => onNavigate(screen)}
          >
            <Icon size={19} strokeWidth={active ? 2.2 : 1.7} aria-hidden="true" />
            <span>{label}</span>
          </button>
        )
      })}
    </nav>
  )
}
