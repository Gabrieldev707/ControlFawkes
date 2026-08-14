import React from 'react'
import { Loader2, Mic, MicOff, Square } from 'lucide-react'

import type { VoiceState } from '../../hooks/useVoiceCapture'


interface VoiceButtonProps {
  state: VoiceState
  disabled?: boolean
  onToggle: () => void
}

const LABELS: Record<VoiceState, string> = {
  idle: 'Falar um comando',
  unsupported: 'Microfone indisponível',
  requesting: 'Liberando o microfone',
  recording: 'Parar de gravar',
  transcribing: 'Transcrevendo o áudio',
  error: 'Tentar falar de novo',
}

export const VoiceButton: React.FC<VoiceButtonProps> = ({
  state,
  disabled = false,
  onToggle,
}) => {
  const busy = state === 'requesting' || state === 'transcribing'
  const icon = state === 'recording'
    ? <Square size={18} aria-hidden="true" fill="currentColor" />
    : state === 'unsupported'
      ? <MicOff size={22} aria-hidden="true" />
      : busy
        ? <Loader2 size={20} aria-hidden="true" className="voice-btn__spinner" />
        : <Mic size={22} aria-hidden="true" />

  return (
    <button
      type="button"
      className="voice-btn"
      data-state={state}
      aria-label={LABELS[state]}
      aria-pressed={state === 'recording'}
      // `unsupported` continua clicável de propósito: o toque é o que revela a
      // mensagem explicando por que a voz não está disponível.
      disabled={disabled || busy}
      onClick={onToggle}
    >
      {icon}
    </button>
  )
}
