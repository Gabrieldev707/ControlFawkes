import {
  ArrowLeft,
  FastForward,
  Keyboard,
  Maximize2,
  Minimize2,
  MousePointer2,
  Play,
  Rewind,
  SkipBack,
  SkipForward,
  Volume2,
} from 'lucide-react'

import { RemoteStatusText } from '../../components/fawkes-remote/RemoteStatusText'
import type { MediaAction } from '../../features/fawkes-remote/types'
import type { NavigableScreen } from '../../state/currentScreen'


interface RemoteControlScreenProps {
  disabled: boolean
  currentAction: MediaAction | null
  statusMessage: string
  statusError: boolean
  onAction: (action: MediaAction) => void
  onNavigate: (screen: NavigableScreen) => void
  onBack: () => void
}

const TRANSPORT_ACTIONS = [
  { action: 'MEDIA_PREVIOUS', label: 'Faixa anterior', icon: SkipBack, primary: false },
  { action: 'MEDIA_PLAY_PAUSE', label: 'Play/Pause', icon: Play, primary: true },
  { action: 'MEDIA_NEXT', label: 'Próxima faixa', icon: SkipForward, primary: false },
] as const

const TIMELINE_ACTIONS = [
  { action: 'MEDIA_SEEK_BACK', label: 'Voltar 10 segundos', shortLabel: '−10s', icon: Rewind },
  { action: 'MEDIA_SEEK_FORWARD', label: 'Avançar 10 segundos', shortLabel: '+10s', icon: FastForward },
] as const

const VIEW_ACTIONS = [
  { action: 'MEDIA_FULLSCREEN', label: 'Fullscreen', icon: Maximize2 },
  { action: 'MEDIA_EXIT_FULLSCREEN', label: 'Sair do fullscreen', icon: Minimize2 },
] as const

export function RemoteControlScreen({
  disabled,
  currentAction,
  statusMessage,
  statusError,
  onAction,
  onNavigate,
  onBack,
}: RemoteControlScreenProps) {
  return (
    <main className="remote-screen media-screen" aria-labelledby="media-screen-title">
      <button type="button" className="remote-screen__back" aria-label="Voltar" onClick={onBack}>
        <ArrowLeft size={18} aria-hidden="true" />
        Voltar
      </button>

      <div className="media-screen__heading">
        <p className="remote-screen__eyebrow">Controle remoto</p>
        <h2 id="media-screen-title">Mídia</h2>
        <p>Comandos fixos para a janela ativa do computador.</p>
      </div>

      <RemoteStatusText message={statusMessage} error={statusError} />

      <section className="media-controls" aria-label="Controles de reprodução">
        <div className="media-controls__transport">
          {TRANSPORT_ACTIONS.map(({ action, label, icon: Icon, primary }) => (
            <button
              key={action}
              type="button"
              className={`media-control${primary ? ' media-control--primary' : ''}${currentAction === action ? ' media-control--active' : ''}`}
              aria-label={label}
              disabled={disabled}
              onClick={() => onAction(action)}
            >
              <Icon size={primary ? 30 : 22} aria-hidden="true" />
              <span>{label}</span>
            </button>
          ))}
        </div>

        <div className="media-controls__row">
          {TIMELINE_ACTIONS.map(({ action, label, shortLabel, icon: Icon }) => (
            <button
              key={action}
              type="button"
              className={`media-control media-control--wide${currentAction === action ? ' media-control--active' : ''}`}
              aria-label={label}
              disabled={disabled}
              onClick={() => onAction(action)}
            >
              <Icon size={19} aria-hidden="true" />
              <span>{shortLabel}</span>
            </button>
          ))}
        </div>

        <div className="media-controls__row">
          {VIEW_ACTIONS.map(({ action, label, icon: Icon }) => (
            <button
              key={action}
              type="button"
              className={`media-control media-control--wide${currentAction === action ? ' media-control--active' : ''}`}
              aria-label={label}
              disabled={disabled}
              onClick={() => onAction(action)}
            >
              <Icon size={19} aria-hidden="true" />
              <span>{label}</span>
            </button>
          ))}
        </div>
      </section>

      <nav className="media-shortcuts" aria-label="Outros controles">
        <button type="button" onClick={() => onNavigate('VOLUME')}>
          <Volume2 size={18} aria-hidden="true" />
          Volume e mudo
        </button>
        <button type="button" onClick={() => onNavigate('TOUCHPAD')}>
          <MousePointer2 size={18} aria-hidden="true" />
          Touchpad
        </button>
        <button type="button" onClick={() => onNavigate('KEYBOARD')}>
          <Keyboard size={18} aria-hidden="true" />
          Teclado
        </button>
      </nav>
    </main>
  )
}
