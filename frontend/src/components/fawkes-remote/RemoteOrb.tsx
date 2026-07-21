import React, { useRef, useEffect } from 'react';
import { FawkesOrb } from './FawkesOrb';
import type { AttractorTarget } from './FawkesOrb';
import type { OrbState } from '../../features/fawkes-remote/types';
import type * as THREE from 'three';
import { toCanvasAttractor } from './orbAttractor';

export interface OrbAttractorRequest {
  rect: DOMRect;
  intensity: number;
  color: THREE.Color;
}

interface RemoteOrbProps {
  state: OrbState;
  attractorTarget?: OrbAttractorRequest | null;
}



export const RemoteOrb: React.FC<RemoteOrbProps> = ({ state, attractorTarget }) => {
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
      orbRef.current.state = state; // We no longer use mapState since they are strictly equal
    }
  }, [state]);

  // Sync attractor changes
  useEffect(() => {
    const orb = orbRef.current;
    const mountNode = mountRef.current;
    if (!orb || !mountNode || !attractorTarget) {
      orb?.setAttractorTarget(null);
      return;
    }

    const normalized = toCanvasAttractor(attractorTarget.rect, mountNode.getBoundingClientRect());
    const target: AttractorTarget = { ...normalized, intensity: attractorTarget.intensity, color: attractorTarget.color };
    orb.setAttractorTarget(target);
  }, [attractorTarget]);

  // Give the container relative size without inline limits
  return <div ref={mountRef} className="remote-orb-container" />;
};
