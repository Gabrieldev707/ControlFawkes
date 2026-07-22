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
  VolumeX,
} from 'lucide-react'

import { RemoteStatusText } from '../../components/fawkes-remote/RemoteStatusText'
import type { MediaAction, VolumeAction } from '../../features/fawkes-remote/types'
import type { NavigableScreen } from '../../state/currentScreen'


interface RemoteControlScreenProps {
  disabled: boolean
  currentAction: MediaAction | null
  currentVolumeAction: VolumeAction | null
  muted: boolean
  statusMessage: string
  statusError: boolean
  onAction: (action: MediaAction) => void
  onToggleMute: () => void
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
  currentVolumeAction,
  muted,
  statusMessage,
  statusError,
  onAction,
  onToggleMute,
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
        <h2 id="media-screen-title">Controles</h2>
        <p>Volume do Windows e comandos da plataforma de mídia ativa.</p>
      </div>

      <RemoteStatusText message={statusMessage} error={statusError} />

      <section className="control-section control-section--system" aria-labelledby="system-controls-title">
        <div className="control-section__heading">
          <div>
            <p className="control-section__eyebrow">Windows</p>
            <h3 id="system-controls-title">Sistema</h3>
          </div>
          <p>Volume principal</p>
        </div>

        <div className="system-controls">
          <button
            type="button"
            className="system-control"
            aria-label="Abrir controles de volume"
            onClick={() => onNavigate('VOLUME')}
          >
            <Volume2 size={20} aria-hidden="true" />
            <span>Volume</span>
          </button>
          <button
            type="button"
            className={`system-control${currentVolumeAction === 'SYSTEM_MUTE_TOGGLE' ? ' system-control--active' : ''}`}
            aria-label={muted ? 'Desativar mudo' : 'Ativar mudo'}
            disabled={disabled}
            onClick={onToggleMute}
          >
            {muted ? <VolumeX size={20} aria-hidden="true" /> : <Volume2 size={20} aria-hidden="true" />}
            <span>{muted ? 'Mudo ativo' : 'Mudo'}</span>
          </button>
        </div>
      </section>

      <section className="control-section control-section--media" aria-labelledby="player-controls-title">
        <div className="control-section__heading">
          <div>
            <p className="control-section__eyebrow">Player ativo</p>
            <h3 id="player-controls-title">Mídia</h3>
          </div>
          <p>Plataforma identificada</p>
        </div>

        <div className="media-controls" aria-label="Controles de reprodução">
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
        </div>
      </section>

      <nav className="media-shortcuts" aria-label="Outras entradas">
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
