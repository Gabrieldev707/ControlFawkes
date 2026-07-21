import React from 'react';
import { Mic } from 'lucide-react';

export const HoldToTalkButton: React.FC = () => (
  <div className="voice-preview">
    <button
      type="button"
      className="hold-to-talk-button hold-to-talk-button--circular"
      aria-label="Segure para falar"
      aria-disabled="true"
      disabled
    >
      <Mic aria-hidden="true" />
    </button>
    <span className="hold-to-talk-button__label">Segure para falar</span>
  </div>
);
