import {
  ArrowLeft,
  FastForward,
  Gauge,
  Keyboard,
  Maximize2,
  Minimize2,
  MousePointer2,
  Play,
  Rewind,
  SkipBack,
  SkipForward,
} from 'lucide-react'

import { NoMediaCard } from '../../components/fawkes-remote/NoMediaCard'
import { NowPlayingCard } from '../../components/fawkes-remote/NowPlayingCard'
import { RemoteStatusText } from '../../components/fawkes-remote/RemoteStatusText'
import { ControlDeck } from '../../components/remote-control/ControlDeck'
import { InlineKeyboard } from '../../components/remote-control/InlineKeyboard'
import { VolumeBar } from '../../components/remote-control/VolumeBar'
import type {
  MediaAction,
  NavigationAction,
  NowPlayingSession,
  PointerAction,
  PointerPayload,
  SafeKey,
} from '../../features/fawkes-remote/types'
import type { GestureLimits } from '../../features/fawkes-remote/touchpadGesture'
import type { NavigableScreen } from '../../state/currentScreen'


interface RemoteControlScreenProps {
  disabled: boolean
  connected: boolean
  navigationDisabled: boolean
  currentAction: MediaAction | null
  currentNavigationAction: NavigationAction | null
  muted: boolean
  volumeLevel: number | null
  statusMessage: string
  statusError: boolean
  nowPlaying?: NowPlayingSession | null
  apiBaseUrl?: string
  credentials?: { deviceId: string; token: string } | null
  gestureLimits?: GestureLimits
  onAction: (action: MediaAction) => void
  onNavigationAction: (action: NavigationAction) => void
  onPointerAction: (action: PointerAction, payload?: PointerPayload) => void
  onKey: (key: SafeKey) => void
  /** De quem é o volume mostrado: o aplicativo, ou o Windows inteiro. */
  volumeTarget?: string | null
  /** Consulta que ficou pendente na busca e segue para o campo daqui. */
  pendingSearchText?: string | null
  onText?: (text: string) => boolean
  onSetVolume: (level: number) => void
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

const TOOLS = [
  { screen: 'TOUCHPAD', label: 'Abrir touchpad', short: 'Touchpad', icon: MousePointer2 },
  { screen: 'KEYBOARD', label: 'Abrir teclado', short: 'Teclado', icon: Keyboard },
  { screen: 'VOLUME', label: 'Abrir volume detalhado', short: 'Volume', icon: Gauge },
] as const

export function RemoteControlScreen({
  disabled,
  connected,
  navigationDisabled,
  currentAction,
  currentNavigationAction,
  muted,
  volumeLevel,
  statusMessage,
  statusError,
  nowPlaying = null,
  apiBaseUrl = '',
  credentials = null,
  gestureLimits,
  onAction,
  onNavigationAction,
  onPointerAction,
  onKey,
  volumeTarget = null,
  pendingSearchText = null,
  onText,
  onSetVolume,
  onVolumeDelta,
  onToggleMute,
  onNavigate,
  onBack,
}: RemoteControlScreenProps) {
  // Sem sessão de mídia, os controles de reprodução não têm o que controlar.
  // Deixá-los ativos convidava o usuário a tocar e receber erro; desligados,
  // eles dizem a verdade antes do toque. O resto da tela segue vivo, porque
  // direcional, cursor, volume e teclado não dependem de mídia.
  const mediaDisabled = disabled || nowPlaying === null

  return (
    <main className="remote-screen control-screen" aria-labelledby="control-screen-title">
      <header className="control-screen__header">
        <button type="button" className="remote-screen__back" aria-label="Voltar" onClick={onBack}>
          <ArrowLeft size={18} aria-hidden="true" />
          Voltar
        </button>
        <h2 id="control-screen-title">Controle</h2>
        <span className="control-screen__connection" data-live={connected}>
          {connected ? 'AO VIVO' : 'OFFLINE'}
        </span>
      </header>

      {/* Atalhos no topo: são modos, não ações. Estavam no fim de um scroll
          longo, onde ninguém encontrava sem procurar. */}
      <nav className="control-tools" aria-label="Ferramentas do controle">
        {TOOLS.map(({ screen, label, short, icon: Icon }) => (
          <button key={screen} type="button" aria-label={label} onClick={() => onNavigate(screen)}>
            <Icon size={16} aria-hidden="true" />
            {short}
          </button>
        ))}
      </nav>

      {/* O que está tocando vem antes dos controles: é o contexto que dá
          sentido a eles, e é a primeira coisa que se quer saber ao pegar o
          celular. */}
      {nowPlaying !== null ? (
        <NowPlayingCard
          session={nowPlaying}
          apiBaseUrl={apiBaseUrl}
          credentials={credentials}
          onTogglePlay={() => onAction('MEDIA_PLAY_PAUSE')}
        />
      ) : (
        <NoMediaCard
          loading={!connected}
          onOpenPlatforms={() => onNavigate('PLATFORMS')}
        />
      )}

      <RemoteStatusText message={statusMessage} error={statusError} />

      {/* Navegar e apontar na mesma superfície: era trocar de tela a cada
          passo, e é isso que a superfície unificada resolve. */}
      <ControlDeck
        disabled={disabled}
        navigationDisabled={navigationDisabled}
        currentNavigationAction={currentNavigationAction}
        onNavigationAction={onNavigationAction}
        onPointerAction={onPointerAction}
        onKey={onKey}
        gestureLimits={gestureLimits}
      />

      {/* Logo abaixo da superfície que clica e manda Tab: com o texto aqui,
          um login inteiro cabe nesta tela. */}
      {onText ? (
        <InlineKeyboard
          disabled={disabled}
          initialText={pendingSearchText}
          onText={onText}
          onKey={onKey}
        />
      ) : null}

      <div className="media-controls__transport" role="group" aria-label="Controles de reprodução">
        {TRANSPORT_ACTIONS.map(({ action, label, icon: Icon, primary }) => (
          <button
            key={action}
            type="button"
            className={`media-control${primary ? ' media-control--primary' : ''}`}
            aria-label={label}
            disabled={mediaDisabled}
            data-active={currentAction === action}
            onClick={() => onAction(action)}
          >
            <Icon size={primary ? 28 : 21} aria-hidden="true" />
          </button>
        ))}
      </div>

      <VolumeBar
        level={volumeLevel}
        muted={muted}
        disabled={disabled}
        target={volumeTarget}
        onSetLevel={onSetVolume}
        onDelta={onVolumeDelta}
        onToggleMute={onToggleMute}
      />

      <div className="secondary-controls" role="group" aria-label="Ações secundárias">
        {SECONDARY_ACTIONS.map(({ action, label, shortLabel, icon: Icon }) => (
          <button
            key={action}
            type="button"
            aria-label={label}
            disabled={mediaDisabled}
            data-active={currentAction === action}
            onClick={() => onAction(action)}
          >
            <Icon size={16} aria-hidden="true" />
            <span>{shortLabel}</span>
          </button>
        ))}
      </div>
    </main>
  )
}
