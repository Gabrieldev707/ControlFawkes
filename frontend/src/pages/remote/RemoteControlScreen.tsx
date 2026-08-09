import {
  ArrowLeft,
  FastForward,
  Gauge,
  Keyboard,
  Maximize2,
  Minimize2,
  Minus,
  MousePointer2,
  Play,
  Plus,
  Rewind,
  SkipBack,
  SkipForward,
  Volume2,
  VolumeX,
} from 'lucide-react'

import { RemoteStatusText } from '../../components/fawkes-remote/RemoteStatusText'
import { DPadControl } from '../../components/remote-control/DPadControl'
import type {
  MediaAction,
  NavigationAction,
  VolumeAction,
} from '../../features/fawkes-remote/types'
import type { NavigableScreen } from '../../state/currentScreen'


interface RemoteControlScreenProps {
  disabled: boolean
  connected: boolean
  navigationDisabled: boolean
  currentAction: MediaAction | null
  currentNavigationAction: NavigationAction | null
  currentVolumeAction: VolumeAction | null
  muted: boolean
  volumeLevel: number | null
  statusMessage: string
  statusError: boolean
  onAction: (action: MediaAction) => void
  onNavigationAction: (action: NavigationAction) => void
  onVolumeDelta: (delta: -5 | 5) => void
  onToggleMute: () => void
  onNavigate: (screen: NavigableScreen) => void
  onBack: () => void
}

const TRANSPORT_ACTIONS = [
  { action: 'MEDIA_PREVIOUS', label: 'Faixa anterior', icon: SkipBack, primary: false },
  { action: 'MEDIA_PLAY_PAUSE', label: 'Play/Pause', icon: Play, primary: true },
  { action: 'MEDIA_NEXT', label: 'Próxima faixa', icon: SkipForward, primary: false },
] as const

const SECONDARY_ACTIONS = [
  { action: 'MEDIA_SEEK_BACK', label: 'Voltar 10 segundos', shortLabel: '−10s', icon: Rewind },
  { action: 'MEDIA_SEEK_FORWARD', label: 'Avançar 10 segundos', shortLabel: '+10s', icon: FastForward },
  { action: 'MEDIA_FULLSCREEN', label: 'Fullscreen', shortLabel: 'Tela cheia', icon: Maximize2 },
  { action: 'MEDIA_EXIT_FULLSCREEN', label: 'Sair do fullscreen', shortLabel: 'Sair', icon: Minimize2 },
] as const

export function RemoteControlScreen({
  disabled,
  connected,
  navigationDisabled,
  currentAction,
  currentNavigationAction,
  currentVolumeAction,
  muted,
  volumeLevel,
  statusMessage,
  statusError,
  onAction,
  onNavigationAction,
  onVolumeDelta,
  onToggleMute,
  onNavigate,
  onBack,
}: RemoteControlScreenProps) {
  const formattedVolume = volumeLevel === null ? '—' : `${volumeLevel}%`

  return (
    <main className="remote-screen control-screen" aria-labelledby="control-screen-title">
      <header className="control-screen__header">
        <button type="button" className="remote-screen__back" aria-label="Voltar" onClick={onBack}>
          <ArrowLeft size={18} aria-hidden="true" />
          Voltar
        </button>
        <div>
          <p className="remote-screen__eyebrow">Fawkes Command Deck</p>
          <h2 id="control-screen-title">Controle</h2>
        </div>
        <span className="control-screen__connection" data-live={connected} aria-hidden="true">
          {connected ? 'AO VIVO' : 'OFFLINE'}
        </span>
      </header>

      <RemoteStatusText message={statusMessage} error={statusError} />

      <section className="control-module control-module--directional" aria-labelledby="directional-title">
        <div className="control-module__heading">
          <p>01 · Navegação</p>
          <h3 id="directional-title">Controle direcional</h3>
        </div>
        <DPadControl
          disabled={disabled || navigationDisabled}
          currentAction={currentNavigationAction}
          onAction={onNavigationAction}
        />
      </section>

      <section className="control-module" aria-labelledby="playback-title">
        <div className="control-module__heading">
          <p>02 · Player ativo</p>
          <h3 id="playback-title">Controles de reprodução</h3>
        </div>
        <div className="media-controls__transport" role="group" aria-label="Controles de reprodução">
          {TRANSPORT_ACTIONS.map(({ action, label, icon: Icon, primary }) => (
            <button
              key={action}
              type="button"
              className={`media-control${primary ? ' media-control--primary' : ''}`}
              aria-label={label}
              disabled={disabled}
              data-active={currentAction === action}
              onClick={() => onAction(action)}
            >
              <Icon size={primary ? 30 : 22} aria-hidden="true" />
              <span>{label}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="control-module" aria-labelledby="quick-volume-title">
        <div className="control-module__heading control-module__heading--inline">
          <div>
            <p>03 · Sistema</p>
            <h3 id="quick-volume-title">Volume rápido</h3>
          </div>
        </div>
        <div className="quick-volume" role="group" aria-label="Volume rápido">
          <button type="button" aria-label="Diminuir volume" disabled={disabled} onClick={() => onVolumeDelta(-5)}>
            <Minus size={24} aria-hidden="true" />
          </button>
          <button
            type="button"
            aria-label={muted ? 'Desativar mudo' : 'Ativar mudo'}
            disabled={disabled}
            data-active={currentVolumeAction === 'SYSTEM_MUTE_TOGGLE' || muted}
            onClick={onToggleMute}
          >
            {muted ? <VolumeX size={25} aria-hidden="true" /> : <Volume2 size={25} aria-hidden="true" />}
            <span>{muted ? 'Mudo ativo' : 'Mudo'}</span>
          </button>
          <output aria-label="Volume atual">{formattedVolume}</output>
          <button type="button" aria-label="Aumentar volume" disabled={disabled} onClick={() => onVolumeDelta(5)}>
            <Plus size={24} aria-hidden="true" />
          </button>
        </div>
      </section>

      <section className="control-module control-module--secondary" aria-labelledby="secondary-title">
        <div className="control-module__heading">
          <p>04 · Precisão</p>
          <h3 id="secondary-title">Ações secundárias</h3>
        </div>
        <div className="secondary-controls" role="group" aria-label="Ações secundárias">
          {SECONDARY_ACTIONS.map(({ action, label, shortLabel, icon: Icon }) => (
            <button
              key={action}
              type="button"
              aria-label={label}
              disabled={disabled}
              data-active={currentAction === action}
              onClick={() => onAction(action)}
            >
              <Icon size={18} aria-hidden="true" />
              <span>{shortLabel}</span>
            </button>
          ))}
        </div>
      </section>

      <nav className="control-tools" aria-label="Ferramentas do controle">
        <button type="button" aria-label="Abrir touchpad" onClick={() => onNavigate('TOUCHPAD')}>
          <MousePointer2 size={18} aria-hidden="true" />
          Touchpad
        </button>
        <button type="button" aria-label="Abrir teclado" onClick={() => onNavigate('KEYBOARD')}>
          <Keyboard size={18} aria-hidden="true" />
          Teclado
        </button>
        <button type="button" aria-label="Abrir volume detalhado" onClick={() => onNavigate('VOLUME')}>
          <Gauge size={18} aria-hidden="true" />
          Volume detalhado
        </button>
      </nav>
    </main>
  )
}
