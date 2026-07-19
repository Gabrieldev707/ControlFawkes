import React, { useRef, useEffect } from 'react';
import { FawkesOrb, type OrbState } from './FawkesOrb';
import type { RemoteState } from '../../features/fawkes-remote/types';

interface RemoteOrbProps {
  state: RemoteState;
}

// Map RemoteState to OrbState
function mapState(s: RemoteState): OrbState {
  switch(s) {
    case 'LISTENING': return 'listening';
    case 'TRANSCRIBING': return 'transcribing';
    case 'NEEDS_SELECTION': return 'needs_selection';
    case 'THINKING': return 'thinking';
    case 'EXECUTING': return 'executing';
    case 'ERROR': return 'error';
    case 'SUCCESS': return 'success';
    default: return 'idle';
  }
}

export const RemoteOrb: React.FC<RemoteOrbProps> = ({ state }) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const orbRef = useRef<FawkesOrb | null>(null);

  useEffect(() => {
    const mountNode = mountRef.current;
    if (!mountNode) return;

    // We create a canvas element to inject into the div
    const canvas = document.createElement('canvas');
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    canvas.style.display = 'block';
    mountNode.appendChild(canvas);

    // Initialize the real Fawkes Orb
    const orb = new FawkesOrb(canvas);
    orbRef.current = orb;

    return () => {
      orb.destroy();
      if (mountNode && canvas.parentNode === mountNode) {
        mountNode.removeChild(canvas);
      }
      orbRef.current = null;
    };
  }, []);

  // Sync state changes
  useEffect(() => {
    if (orbRef.current) {
      orbRef.current.state = mapState(state);
    }
  }, [state]);

  // Give the container some relative size/boundaries, similar to what we had
  return <div ref={mountRef} className="remote-orb" style={{ width: '100%', height: '100%', maxWidth: 300, maxHeight: 300 }} />;
};
