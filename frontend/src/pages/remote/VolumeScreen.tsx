import { ArrowLeft, Minus, Plus, Volume2, VolumeX } from 'lucide-react'
import type { CSSProperties } from 'react'

import { RemoteStatusText } from '../../components/fawkes-remote/RemoteStatusText'
import type { VolumeScope } from '../../features/fawkes-remote/types'


interface VolumeScreenProps {
  disabled: boolean
  loading: boolean
  level: number | null
  muted: boolean
  /** Onde a mudança aconteceu de fato. O fallback nunca é escondido. */
  scope?: VolumeScope
  target?: string | null
  statusMessage: string
  statusError: boolean
  onSetLevel: (level: number) => void
  onDelta: (delta: -5 | 5) => void
  onToggleMute: () => void
  onBack: () => void
}

export function VolumeScreen({
  disabled,
  loading,
  level,
  muted,
  scope = 'GLOBAL',
  target = null,
  statusMessage,
  statusError,
  onSetLevel,
  onDelta,
  onToggleMute,
  onBack,
}: VolumeScreenProps) {
  const effectiveLevel = level ?? 0
  const controlsDisabled = disabled || loading || level === null

  return (
    <main className="remote-screen volume-screen" aria-labelledby="volume-screen-title">
      <button type="button" className="remote-screen__back" aria-label="Voltar" onClick={onBack}>
        <ArrowLeft size={18} aria-hidden="true" />
        Voltar
      </button>

      <div className="volume-screen__heading">
        <p className="remote-screen__eyebrow">Sistema Windows</p>
        <h2 id="volume-screen-title">Volume</h2>
        <p>Controle o áudio principal do computador.</p>
      </div>

      <p className="volume-screen__scope">
        {scope === 'LOCAL' && target !== null
          ? `Controlando o volume do ${target}`
          : 'Controlando o volume do Windows (fallback)'}
      </p>

      <RemoteStatusText message={statusMessage} error={statusError} />

      <section className="volume-panel" aria-label="Volume do Windows" aria-busy={loading}>
        <div className={`volume-panel__icon${muted ? ' volume-panel__icon--muted' : ''}`}>
          {muted ? <VolumeX size={28} aria-hidden="true" /> : <Volume2 size={28} aria-hidden="true" />}
        </div>
        <output className="volume-panel__value" aria-live="polite">
          {level === null ? '—' : `${level}%`}
        </output>
        <span className="volume-panel__state">{muted ? 'Mudo ativado' : 'Som ativo'}</span>

        <div className="volume-panel__slider-row">
          <button
            type="button"
            aria-label="Diminuir volume"
            disabled={controlsDisabled || effectiveLevel === 0}
            onClick={() => onDelta(-5)}
          >
            <Minus size={20} aria-hidden="true" />
          </button>
          <input
            type="range"
            min="0"
            max="100"
            step="1"
            value={effectiveLevel}
            aria-label="Volume do computador"
            disabled={controlsDisabled}
            style={{ '--volume-progress': `${effectiveLevel}%` } as CSSProperties}
            onChange={(event) => onSetLevel(Number(event.target.value))}
          />
          <button
            type="button"
            aria-label="Aumentar volume"
            disabled={controlsDisabled || effectiveLevel === 100}
            onClick={() => onDelta(5)}
          >
            <Plus size={20} aria-hidden="true" />
          </button>
        </div>

        <button
          type="button"
          className={`volume-panel__mute${muted ? ' volume-panel__mute--active' : ''}`}
          aria-label={muted ? 'Desativar mudo' : 'Ativar mudo'}
          disabled={controlsDisabled}
          onClick={onToggleMute}
        >
          {muted ? <Volume2 size={19} aria-hidden="true" /> : <VolumeX size={19} aria-hidden="true" />}
          {muted ? 'Ativar som' : 'Silenciar'}
        </button>
      </section>
    </main>
  )
}
