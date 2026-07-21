import { ArrowLeft, LayoutGrid } from 'lucide-react'

import { PlatformGrid } from '../../components/fawkes-remote/PlatformGrid'
import { RemoteStatusText } from '../../components/fawkes-remote/RemoteStatusText'
import type { Platform } from '../../features/fawkes-remote/types'


interface PlatformsScreenProps {
  selectedPlatform: Platform | null
  disabled: boolean
  statusMessage: string
  statusError: boolean
  onSelect: (platform: Platform) => void
  onBack: () => void
}

export function PlatformsScreen({
  selectedPlatform,
  disabled,
  statusMessage,
  statusError,
  onSelect,
  onBack,
}: PlatformsScreenProps) {
  return (
    <main className="remote-screen platforms-screen" aria-labelledby="platforms-screen-title">
      <button
        type="button"
        className="remote-screen__back"
        aria-label="Voltar"
        onClick={onBack}
      >
        <ArrowLeft size={18} aria-hidden="true" />
        Voltar
      </button>

      <div className="platforms-screen__heading">
        <span className="platforms-screen__icon" aria-hidden="true">
          <LayoutGrid size={24} strokeWidth={1.7} />
        </span>
        <div>
          <p className="remote-screen__eyebrow">Streaming</p>
          <h2 id="platforms-screen-title">Plataformas</h2>
        </div>
      </div>

      <p className="platforms-screen__intro">
        Escolha um destino. O computador abrirá somente a URL oficial cadastrada.
      </p>

      <RemoteStatusText message={statusMessage} error={statusError} />

      <div className="platforms-screen__grid">
        <PlatformGrid
          selectedPlatform={selectedPlatform}
          disabled={disabled}
          onSelect={onSelect}
        />
      </div>
    </main>
  )
}
