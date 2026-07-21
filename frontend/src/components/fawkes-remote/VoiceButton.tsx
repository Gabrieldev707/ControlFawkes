import React from 'react'
import { Mic } from 'lucide-react'


export const VoiceButton: React.FC = () => (
  <button
    type="button"
    className="voice-btn"
    aria-label="Entrada por voz — em breve"
    disabled
  >
    <Mic size={22} aria-hidden="true" />
    <span className="voice-soon">Em breve</span>
  </button>
)
