import React, { useState, useCallback, useRef, useEffect } from 'react';
import type { OrbState, Platform, ServerMessage, AuthState } from './types';
import { useWebSocket } from '../../hooks/useWebSocket';
import {
  RemoteOrb,
  ConnectionStatus,
  PlatformGrid,
  HoldToTalkButton,
  SearchSheet,
  RemoteNavigation,
  RemoteStatusText,
  MediaControlPanel,
  TouchpadPreview,
} from '../../components/fawkes-remote';
import type { OrbAttractorRequest, PlatformActionState, RemoteView } from '../../components/fawkes-remote';
import { PairingScreen } from '../../components/fawkes-remote/PairingScreen';
import { generateId } from '../../utils/uuid';
import * as THREE from 'three';
import { Search } from 'lucide-react';
import { getRemoteStatusCopy } from './statusCopy';
import '../../styles/fawkes-remote.css';

export const FawkesRemotePage: React.FC = () => {
  const [orbState, setOrbState] = useState<OrbState>('idle');
  const [selectedPlatform, setSelectedPlatform] = useState<Platform | null>(null);
  const [attractorTarget, setAttractorTarget] = useState<OrbAttractorRequest | null>(null);
  const [currentView, setCurrentView] = useState<RemoteView>('home');
  const [searchOpen, setSearchOpen] = useState(false);

  const [authState, setAuthState] = useState<AuthState>('checking');
  const [errorMsg, setErrorMsg] = useState<string>('');
  const [volumeLevel, setVolumeLevel] = useState<number>(0);
  const [isMuted, setIsMuted] = useState<boolean>(false);

  // Rate limiting variables for volume
  const lastSendTime = useRef<number>(Number.NEGATIVE_INFINITY);
  const lastSentVolumeRef = useRef<number | null>(null);
  const pendingVolumeRef = useRef<number | null>(null);
  const rateLimitTimeoutRef = useRef<number | null>(null);

  const currentRequestId = useRef<string | null>(null);
  const successTimeoutRef = useRef<number | null>(null);

  const sendMessageRef = useRef<any>(null);
  const hasSentAuthThisConnection = useRef<boolean>(false);

  const handleMessage = useCallback((msg: ServerMessage) => {

    if (msg.type === 'AUTH_REQUIRED') {
      setAuthState('pairing_required');
      return;
    }

    if (msg.type === 'AUTH_RESULT') {
      if (msg.success) {
        setAuthState('authenticated');
        sendMessageRef.current?.({ type: 'VOLUME_GET', requestId: generateId(), payload: {} });
      } else {
        localStorage.removeItem('fawkes_token');
        localStorage.removeItem('fawkes_deviceId');
        setAuthState('pairing_required');
        setErrorMsg(msg.message);
      }
      return;
    }

    if (msg.type === 'PAIR_RESULT') {
      if (msg.success && msg.token && msg.deviceId) {
        localStorage.setItem('fawkes_token', msg.token);
        localStorage.setItem('fawkes_deviceId', msg.deviceId);
        setAuthState('authenticated');
        setErrorMsg('');
        sendMessageRef.current?.({ type: 'VOLUME_GET', requestId: generateId(), payload: {} });
      } else {
        setAuthState('rejected');
        setErrorMsg(msg.message);
      }
      return;
    }

    if (msg.type === 'VOLUME_STATE') {
      setVolumeLevel(msg.level);
      setIsMuted(msg.muted);
      return;
    }

    // Only process responses for our current request for generic commands
    if ('requestId' in msg && msg.requestId !== currentRequestId.current) {
      // Volume commands might have different requestIds and are fire-and-forget for UI state here
      // But for commands like PLATFORM_SELECTED or TEXT_COMMAND, we track them.
      if (msg.type === 'ERROR' && msg.code === 'RATE_LIMITED') {
        // If we get rate limited, schedule sending the pending volume again
        if (pendingVolumeRef.current !== null && !rateLimitTimeoutRef.current) {
          rateLimitTimeoutRef.current = window.setTimeout(() => {
             const vol = pendingVolumeRef.current;
             pendingVolumeRef.current = null;
             rateLimitTimeoutRef.current = null;
              if (vol !== null && vol !== lastSentVolumeRef.current) {
                lastSentVolumeRef.current = vol;
                sendMessageRef.current?.({
                  type: 'VOLUME_SET',
                  requestId: generateId(),
                  payload: { level: vol }
               });
             }
          }, 50); // wait 50ms (window size)
        }
      }
      return;
    }

    if (msg.type === 'COMMAND_RESULT') {
      if (msg.success) setOrbState('success');
      else setOrbState('error');

      if (successTimeoutRef.current) clearTimeout(successTimeoutRef.current);
      successTimeoutRef.current = window.setTimeout(() => {
        setOrbState('idle');
        setSelectedPlatform(null);
        setAttractorTarget(null);
        currentRequestId.current = null;
      }, msg.success ? 2000 : 3000);

    } else if (msg.type === 'ERROR') {
      if (msg.code === 'AUTH_REQUIRED') {
        setAuthState('pairing_required');
      } else {
        setOrbState('error');
        if (successTimeoutRef.current) clearTimeout(successTimeoutRef.current);
        successTimeoutRef.current = window.setTimeout(() => {
          setOrbState('idle');
          setSelectedPlatform(null);
          setAttractorTarget(null);
          currentRequestId.current = null;
        }, 3000);
      }
    }
  }, []);

  const { connectionState, sendMessage } = useWebSocket({
    onMessage: handleMessage
  });

  sendMessageRef.current = sendMessage;

  useEffect(() => {
    if (connectionState === 'connected') {
      if (!hasSentAuthThisConnection.current) {
        hasSentAuthThisConnection.current = true;
        const token = localStorage.getItem('fawkes_token');
        const deviceId = localStorage.getItem('fawkes_deviceId');
        if (token && deviceId) {
          setAuthState('checking');
          sendMessageRef.current?.({
            type: 'AUTH',
            requestId: generateId(),
            payload: { deviceId, token }
          });
        } else {
          setAuthState('pairing_required');
        }
      }
    } else {
      hasSentAuthThisConnection.current = false;
      if (connectionState === 'disconnected' || connectionState === 'error') {
        if (authState === 'checking') {
          // Keep it checking until we reconnect
        }
      }
    }
  }, [connectionState, authState]);

  useEffect(() => {
    return () => {
      if (successTimeoutRef.current) clearTimeout(successTimeoutRef.current);
      if (rateLimitTimeoutRef.current) clearTimeout(rateLimitTimeoutRef.current);
    };
  }, []);

  const controlsDisabled = connectionState !== 'connected' || authState !== 'authenticated';

  const handlePlatformSelect = (platform: Platform, rect?: DOMRect) => {
    if (controlsDisabled) return;
    if (orbState === 'executing') return;

    if (successTimeoutRef.current) clearTimeout(successTimeoutRef.current);

    const reqId = generateId();
    currentRequestId.current = reqId;

    setSelectedPlatform(platform);

    // Set attractor to the center of the clicked button
    if (rect) {
      // Choose an accent color based on platform
      let colorHex = 0xffffff;
      if (platform === 'NETFLIX') colorHex = 0xe50914;
      if (platform === 'MAX') colorHex = 0x6b21a8;
      if (platform === 'PRIME_VIDEO') colorHex = 0x00a8e1;
      if (platform === 'DISNEY_PLUS') colorHex = 0x113ccf;
      if (platform === 'SPOTIFY') colorHex = 0x1db954;
      if (platform === 'YOUTUBE') colorHex = 0xff0000;

      setAttractorTarget({
        rect,
        intensity: 1.0,
        color: new THREE.Color(colorHex)
      });
    }

    setOrbState('executing');

    const sent = sendMessage({
      type: 'PLATFORM_SELECTED',
      requestId: reqId,
      payload: { platform }
    });

    if (!sent) {
      setOrbState('error');
      currentRequestId.current = null;
      setSelectedPlatform(null);
      setAttractorTarget(null);

      successTimeoutRef.current = window.setTimeout(() => {
        setOrbState('idle');
      }, 3000);
    }
  };


  const attemptPairing = (pin: string, deviceName: string) => {
    setErrorMsg('');
    setAuthState('pairing');
    sendMessage({
      type: 'PAIR_DEVICE',
      requestId: generateId(),
      payload: { pin, deviceName }
    });
  };

  const handleSetVolume = (level: number) => {
    if (controlsDisabled) return;

    // Check local window limits to not span the server if we can avoid it.
    const now = performance.now();
    const elapsed = now - lastSendTime.current;
    if (elapsed >= 50) {
      if (rateLimitTimeoutRef.current !== null) {
        clearTimeout(rateLimitTimeoutRef.current);
        rateLimitTimeoutRef.current = null;
      }
      lastSendTime.current = now;
      lastSentVolumeRef.current = level;
      sendMessage({
        type: 'VOLUME_SET',
        requestId: generateId(),
        payload: { level }
      });
      // Clear pending
      pendingVolumeRef.current = null;
    } else {
      if (level === lastSentVolumeRef.current) {
        pendingVolumeRef.current = null;
        if (rateLimitTimeoutRef.current !== null) {
          clearTimeout(rateLimitTimeoutRef.current);
          rateLimitTimeoutRef.current = null;
        }
        return;
      }

      // Store pending volume for trailing update
      pendingVolumeRef.current = level;
      if (rateLimitTimeoutRef.current === null) {
        rateLimitTimeoutRef.current = window.setTimeout(() => {
          const vol = pendingVolumeRef.current;
          pendingVolumeRef.current = null;
          rateLimitTimeoutRef.current = null;
          if (vol !== null && vol !== lastSentVolumeRef.current) {
            lastSendTime.current = performance.now();
            lastSentVolumeRef.current = vol;
            sendMessage({
              type: 'VOLUME_SET',
              requestId: generateId(),
              payload: { level: vol }
            });
          }
        }, Math.max(0, 50 - elapsed));
      }
    }
  };

  const handleToggleMute = () => {
    if (controlsDisabled) return;
    sendMessage({
      type: 'VOLUME_TOGGLE_MUTE',
      requestId: generateId(),
      payload: {}
    });
  };

  const handleVolumeStep = (delta: -5 | 5) => {
    if (controlsDisabled) return;
    sendMessage({
      type: 'VOLUME_STEP',
      requestId: generateId(),
      payload: { delta },
    });
  };

  const statusText = getRemoteStatusCopy({ connectionState, authState, orbState, selectedPlatform });
  const platformActionState: PlatformActionState =
    orbState === 'executing' || orbState === 'success' || orbState === 'error' ? orbState : 'idle';

  return (
    <div className="fawkes-remote-container">
      <header className="remote-header">
        <ConnectionStatus state={connectionState} />
        <span className="remote-title" aria-label="ControlFawkes">fawkes</span>
      </header>

      {(authState === 'pairing_required' || authState === 'pairing' || authState === 'rejected') && (
        <PairingScreen
          onPair={attemptPairing}
          errorMsg={connectionState !== 'connected' ? 'Computador desconectado' : errorMsg}
          isPairing={authState === 'pairing'}
        />
      )}

      <main className="remote-main">
        {currentView === 'home' && (
          <div className="home-view">
            <div className="orb-section">
              <RemoteOrb state={orbState} attractorTarget={attractorTarget} />
            </div>
            <RemoteStatusText text={statusText} state={orbState} />
            <PlatformGrid
              onSelect={handlePlatformSelect}
              selectedPlatform={selectedPlatform}
              activeState={platformActionState}
              disabled={controlsDisabled}
            />
            <HoldToTalkButton />
            <button
              type="button"
              className="search-access-button"
              onClick={() => setSearchOpen(true)}
            >
              <Search aria-hidden="true" />
              <span>Teclado/Pesquisa</span>
            </button>
          </div>
        )}

        {currentView === 'control' && (
          <MediaControlPanel
            volume={volumeLevel}
            isMuted={isMuted}
            onSetVolume={handleSetVolume}
            onStep={handleVolumeStep}
            onToggleMute={handleToggleMute}
            onOpenSearch={() => setSearchOpen(true)}
            disabled={controlsDisabled}
          />
        )}

        {currentView === 'touchpad' && <TouchpadPreview />}

        <RemoteNavigation currentView={currentView} onNavigate={setCurrentView} />
      </main>
      <SearchSheet open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  );
};
