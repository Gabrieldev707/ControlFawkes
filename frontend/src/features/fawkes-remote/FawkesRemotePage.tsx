import React, { useState, useCallback, useRef } from 'react';
import type { OrbState, Platform, ServerMessage } from './types';
import { useWebSocket } from '../../hooks/useWebSocket';
import { 
  RemoteOrb, 
  ConnectionStatus, 
  PlatformGrid, 
  VoiceButton, 
  TextInput 
} from '../../components/fawkes-remote';
import '../../styles/fawkes-remote.css';

export const FawkesRemotePage: React.FC = () => {
  const [orbState, setOrbState] = useState<OrbState>('idle');
  const [selectedPlatform, setSelectedPlatform] = useState<Platform | null>(null);
  
  const currentRequestId = useRef<string | null>(null);
  const successTimeoutRef = useRef<number | null>(null);

  const handleMessage = useCallback((msg: ServerMessage) => {
    if (msg.type === 'STATE_UPDATE') {
      // Backend sent state update, not strictly mapped to visual orb state in Phase 1.5
      return;
    }

    // Only process responses for our current request
    if ('requestId' in msg && msg.requestId !== currentRequestId.current) {
      return;
    }

    if (msg.type === 'COMMAND_RESULT') {
      setOrbState('success');
      
      // Clear selection after a delay and return to idle
      if (successTimeoutRef.current) clearTimeout(successTimeoutRef.current);
      successTimeoutRef.current = window.setTimeout(() => {
        setOrbState('idle');
        setSelectedPlatform(null);
        currentRequestId.current = null;
      }, 2000);
      
    } else if (msg.type === 'ERROR') {
      setOrbState('error');
      
      if (successTimeoutRef.current) clearTimeout(successTimeoutRef.current);
      successTimeoutRef.current = window.setTimeout(() => {
        setOrbState('idle');
        setSelectedPlatform(null);
        currentRequestId.current = null;
      }, 3000);
    }
  }, []);

  const { connectionState, sendMessage } = useWebSocket({
    onMessage: handleMessage
  });

  const handlePlatformSelect = (platform: Platform) => {
    if (connectionState !== 'connected') return;
    if (orbState === 'executing') return;
    
    // Clear previous timeouts
    if (successTimeoutRef.current) clearTimeout(successTimeoutRef.current);
    
    const reqId = crypto.randomUUID();
    currentRequestId.current = reqId;
    
    setSelectedPlatform(platform);
    setOrbState('executing');
    
    sendMessage({
      type: 'PLATFORM_SELECTED',
      requestId: reqId,
      payload: { platform }
    });
  };

  return (
    <div className="remote-container">
      <div className="remote-header">
        <h1 className="remote-title">FAWKES</h1>
        <ConnectionStatus state={connectionState} />
      </div>

      <div className="orb-container">
        <RemoteOrb state={orbState} />
      </div>

      <div className="input-area">
        <PlatformGrid 
          selectedPlatform={selectedPlatform}
          disabled={connectionState !== 'connected'}
          onSelect={handlePlatformSelect}
        />
        
        <div className="main-controls">
          <TextInput />
          <VoiceButton />
        </div>
      </div>
    </div>
  );
};
