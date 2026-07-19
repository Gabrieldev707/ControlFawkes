import React from 'react';
import type { RemoteState } from '../../features/fawkes-remote/types';
import { Wifi, WifiOff, Loader2 } from 'lucide-react';

export const ConnectionStatus: React.FC<{ state: RemoteState }> = ({ state }) => {
  let icon = <Wifi size={14} />;
  let text = 'Conectado';
  let dotClass = 'connected';

  if (state === 'DISCONNECTED') {
    icon = <WifiOff size={14} />;
    text = 'Desconectado';
    dotClass = 'disconnected';
  } else if (state === 'CONNECTING') {
    icon = <Loader2 size={14} className="animate-spin" />;
    text = 'Conectando...';
    dotClass = 'connecting';
  }

  return (
    <div className="status-badge">
      <div className={`status-dot ${dotClass}`} />
      {icon}
      <span>{text}</span>
    </div>
  );
};
