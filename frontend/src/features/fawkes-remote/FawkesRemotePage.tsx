import React, { useState, useEffect } from 'react';
import type { RemoteState } from './types';
import { 
  RemoteOrb, 
  ConnectionStatus, 
  PlatformGrid, 
  VoiceButton, 
  TextInput 
} from '../../components/fawkes-remote';
import '../../styles/fawkes-remote.css';

export const FawkesRemotePage: React.FC = () => {
  const [state, setState] = useState<RemoteState>('CONNECTING');

  useEffect(() => {
    // Esqueleto de WebSocket
    const ws = new WebSocket(import.meta.env.VITE_WS_URL || 'ws://localhost:8100/ws');
    
    ws.onopen = () => {
      console.log('WS Connected');
      // O backend vai mandar um STATE_UPDATE logo em seguida
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'STATE_UPDATE') {
          setState(data.state as RemoteState);
        }
      } catch (err) {
        console.error('Error parsing WS message', err);
      }
    };

    ws.onerror = () => setState('ERROR');
    ws.onclose = () => setState('DISCONNECTED');

    return () => {
      ws.close();
    };
  }, []);

  return (
    <div className="remote-container">
      <div className="remote-header">
        <h1 className="remote-title">FAWKES</h1>
        <ConnectionStatus state={state} />
      </div>

      <div className="orb-container">
        <RemoteOrb state={state} />
      </div>

      <div className="input-area">
        <PlatformGrid />
        
        <div className="main-controls">
          <TextInput />
          <VoiceButton />
        </div>
      </div>
    </div>
  );
};
