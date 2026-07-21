import React, { useState, useEffect, useRef, useCallback } from 'react';
import './PairingScreen.css';
import { getDefaultDeviceName } from '../../features/fawkes-remote/deviceName';

interface PairingScreenProps {
  onPair: (pin: string, deviceName: string) => void;
  errorMsg?: string;
  isPairing?: boolean;
}

export const PairingScreen: React.FC<PairingScreenProps> = ({ onPair, errorMsg, isPairing }) => {
  const [pin, setPin] = useState('');
  const [shake, setShake] = useState(false);
  const submittedPinRef = useRef<string | null>(null);

  // If there's a new error from a submitted pin, trigger shake/clear
  useEffect(() => {
    if (errorMsg && errorMsg !== 'Computador desconectado' && submittedPinRef.current !== null) {
      // It's a PIN error (or pairing rejected error)
      setPin('');
      submittedPinRef.current = null;
      setShake(true);
      if (typeof navigator !== 'undefined' && navigator.vibrate) {
        navigator.vibrate(40);
      }
      const timer = setTimeout(() => setShake(false), 500);
      return () => clearTimeout(timer);
    }
  }, [errorMsg]);

  const handleKeyPress = useCallback((key: string) => {
    if (isPairing || errorMsg === 'Computador desconectado') return;
    
    setPin((prev) => {
      if (key === 'Backspace') {
        return prev.slice(0, -1);
      }
      if (prev.length < 6) {
        return prev + key;
      }
      return prev;
    });
  }, [isPairing, errorMsg]);

  useEffect(() => {
    if (pin.length === 6 && pin !== submittedPinRef.current) {
      submittedPinRef.current = pin;
      onPair(pin, getDefaultDeviceName());
    }
  }, [pin, onPair]);

  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if (isPairing || errorMsg === 'Computador desconectado') return;
      if (e.key >= '0' && e.key <= '9') {
        handleKeyPress(e.key);
      } else if (e.key === 'Backspace' || e.key === 'Delete') {
        handleKeyPress('Backspace');
      } else if (e.key === 'Escape') {
        setPin('');
      }
    };
    
    window.addEventListener('keydown', handleGlobalKeyDown);
    return () => window.removeEventListener('keydown', handleGlobalKeyDown);
  }, [handleKeyPress, isPairing, errorMsg]);

  return (
    <div className="pairing-screen">
      <div className="pairing-card">
        <h2>Parear dispositivo</h2>
        <p>Digite o PIN exibido no computador</p>
        
        {/* Assistive text for screen readers */}
        <div className="sr-only" aria-live="polite">
          {errorMsg ? (errorMsg === 'Computador desconectado' ? 'Computador desconectado' : 'PIN incorreto. Tente novamente.') : `${pin.length} de 6 dígitos informados`}
        </div>

        <div className={`pin-indicators ${shake ? 'shake' : ''}`}>
          {[...Array(6)].map((_, i) => (
            <div key={i} className={`indicator ${i < pin.length ? 'filled' : ''}`} />
          ))}
        </div>
        
        <div className="error-msg-container">
          {errorMsg && <span className="error-msg">{errorMsg}</span>}
        </div>

        <div className="keypad">
          {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((num) => (
            <button
              key={num}
              type="button"
              className="keypad-btn"
              onClick={() => handleKeyPress(num.toString())}
              disabled={isPairing || errorMsg === 'Computador desconectado'}
              aria-label={`Número ${num}`}
            >
              {num}
            </button>
          ))}
          <div className="keypad-spacer"></div>
          <button
            type="button"
            className="keypad-btn"
            onClick={() => handleKeyPress('0')}
            disabled={isPairing || errorMsg === 'Computador desconectado'}
            aria-label="Número 0"
          >
            0
          </button>
          <button
            type="button"
            className="keypad-btn backspace"
            onClick={() => handleKeyPress('Backspace')}
            disabled={isPairing || errorMsg === 'Computador desconectado' || pin.length === 0}
            aria-label="Apagar último número"
          >
            ⌫
          </button>
        </div>
      </div>
    </div>
  );
};
