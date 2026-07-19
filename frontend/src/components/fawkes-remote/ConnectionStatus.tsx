import React from 'react';
import type { ConnectionState } from '../../features/fawkes-remote/types';
import { Wifi, WifiOff, Loader2 } from 'lucide-react';

export const ConnectionStatus: React.FC<{ state: ConnectionState }> = ({ state }) => {
  let icon = <Wifi size={14} />;
  let text = 'Conectado';
  let dotClass = 'connected';

  if (state === 'disconnected') {
    icon = <WifiOff size={14} />;
    text = 'Desconectado';
    dotClass = 'disconnected';
  } else if (state === 'connecting') {
    icon = <Loader2 size={14} className="animate-spin" />;
    text = 'Conectando...';
    dotClass = 'connecting';
  } else if (state === 'error') {
    icon = <WifiOff size={14} />;
    text = 'Erro de Conexão';
    dotClass = 'disconnected';
  }

  return (
    <div className="status-badge">
      <div className={`status-dot ${dotClass}`} />
      {icon}
      <span>{text}</span>
    </div>
  );
};
