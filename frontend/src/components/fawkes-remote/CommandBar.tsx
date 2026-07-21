import React from 'react';
import { Mic, Search } from 'lucide-react';

interface CommandBarProps {
  disabled?: boolean;
}

export const CommandBar: React.FC<CommandBarProps> = ({ disabled }) => {
  return (
    <div className="command-bar">
      <div className="command-bar-icon">
        <Search size={20} />
      </div>
      <input 
        type="text" 
        className="command-bar-input" 
        placeholder="O que vamos assistir?" 
        disabled={disabled}
      />
      <button className="command-bar-voice" disabled={disabled} aria-label="Comando de voz">
        <Mic size={22} />
      </button>
    </div>
  );
};
