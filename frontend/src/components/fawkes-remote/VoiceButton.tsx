import React from 'react';
import { Mic } from 'lucide-react';

export const VoiceButton: React.FC = () => {
  return (
    <button className="voice-btn">
      <Mic size={24} />
    </button>
  );
};
