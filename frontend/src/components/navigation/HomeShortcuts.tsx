import {
  ChevronRight,
  Gamepad2,
  Keyboard,
  LayoutGrid,
  MousePointer2,
  Settings,
  Volume2,
} from 'lucide-react'

import type { NavigableScreen } from '../../state/currentScreen'


interface HomeShortcutsProps {
  onNavigate: (screen: NavigableScreen) => void
}

const SHORTCUTS = [
  { screen: 'REMOTE_CONTROL', label: 'Controle', icon: Gamepad2 },
  { screen: 'TOUCHPAD', label: 'Touchpad', icon: MousePointer2 },
  { screen: 'KEYBOARD', label: 'Teclado', icon: Keyboard },
  { screen: 'VOLUME', label: 'Volume', icon: Volume2 },
  { screen: 'PLATFORMS', label: 'Plataformas', icon: LayoutGrid },
  { screen: 'SETTINGS', label: 'Configurações', icon: Settings },
] as const satisfies ReadonlyArray<{
  screen: NavigableScreen
  label: string
  icon: typeof Gamepad2
}>

export function HomeShortcuts({ onNavigate }: HomeShortcutsProps) {
  return (
    <section className="home-shortcuts" aria-labelledby="home-shortcuts-title">
      <div className="home-shortcuts__heading">
        <p className="home-shortcuts__eyebrow">Controle rápido</p>
        <h2 id="home-shortcuts-title">Para onde vamos?</h2>
      </div>

      <div className="home-shortcuts__grid">
        {SHORTCUTS.map(({ screen, label, icon: Icon }) => (
          <button
            key={screen}
            type="button"
            className="home-shortcut"
            aria-label={label}
            onClick={() => onNavigate(screen)}
          >
            <span className="home-shortcut__icon" aria-hidden="true">
              <Icon size={21} strokeWidth={1.8} />
            </span>
            <span>{label}</span>
            <ChevronRight className="home-shortcut__chevron" size={16} aria-hidden="true" />
          </button>
        ))}
      </div>
    </section>
  )
}
