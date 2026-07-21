import React from 'react';
import type { Platform } from '../../features/fawkes-remote/types';

export type PlatformActionState = 'idle' | 'executing' | 'success' | 'error';
type PlatformCardState = PlatformActionState | 'selected' | 'disabled';

interface PlatformGridProps {
  selectedPlatform: Platform | null;
  activeState: PlatformActionState;
  disabled: boolean;
  onSelect: (platform: Platform, rect: DOMRect) => void;
}

const PLATFORMS: Array<{ id: Platform; name: string; logo: string; color: string; rgb: string }> = [
  { id: 'NETFLIX', name: 'Netflix', logo: '/platforms/netflix.svg', color: '#e50914', rgb: '229, 9, 20' },
  { id: 'MAX', name: 'HBO Max', logo: '/platforms/max.svg', color: '#8b5cf6', rgb: '139, 92, 246' },
  { id: 'PRIME_VIDEO', name: 'Prime Video', logo: '/platforms/prime-video.svg', color: '#00a8e1', rgb: '0, 168, 225' },
  { id: 'DISNEY_PLUS', name: 'Disney+', logo: '/platforms/disney-plus.svg', color: '#7c8cff', rgb: '124, 140, 255' },
  { id: 'YOUTUBE', name: 'YouTube', logo: '/platforms/youtube.svg', color: '#ff2d2d', rgb: '255, 45, 45' },
  { id: 'SPOTIFY', name: 'Spotify', logo: '/platforms/spotify.svg', color: '#1ed760', rgb: '30, 215, 96' },
];

function getCardState(
  platform: Platform,
  selectedPlatform: Platform | null,
  activeState: PlatformActionState,
  disabled: boolean,
): PlatformCardState {
  if (disabled) return 'disabled';
  if (platform !== selectedPlatform) return 'idle';
  return activeState === 'idle' ? 'selected' : activeState;
}

export const PlatformGrid: React.FC<PlatformGridProps> = ({ selectedPlatform, activeState, disabled, onSelect }) => (
  <section className="platform-section" aria-labelledby="platform-section-title">
    <div className="section-heading">
      <span className="control-eyebrow">Streaming</span>
      <h2 id="platform-section-title">Escolha uma plataforma</h2>
    </div>
    <div className="platform-grid">
      {PLATFORMS.map(({ id, name, logo, color, rgb }) => {
        const cardState = getCardState(id, selectedPlatform, activeState, disabled);
        return (
          <button
            key={id}
            type="button"
            className="platform-card"
            data-state={cardState}
            aria-label={name}
            aria-pressed={selectedPlatform === id}
            disabled={disabled || activeState === 'executing'}
            onClick={(event) => onSelect(id, event.currentTarget.getBoundingClientRect())}
            style={{ '--brand-color': color, '--brand-rgb': rgb } as React.CSSProperties}
          >
            <span className="platform-card__halo" aria-hidden="true" />
            <img src={logo} alt={name} className="platform-card__logo" draggable={false} />
          </button>
        );
      })}
    </div>
  </section>
);
