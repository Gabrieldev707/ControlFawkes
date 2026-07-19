import React from 'react';
import type { Platform } from '../../features/fawkes-remote/types';

interface PlatformGridProps {
  selectedPlatform: Platform | null;
  disabled: boolean;
  onSelect: (platform: Platform) => void;
}

const PLATFORMS: Array<{ id: Platform; name: string; logo: string }> = [
  { id: 'NETFLIX', name: 'Netflix', logo: '/platforms/netflix.svg' },
  { id: 'MAX', name: 'Max', logo: '/platforms/max.svg' },
  { id: 'PRIME_VIDEO', name: 'Prime Video', logo: '/platforms/prime-video.svg' },
  { id: 'DISNEY_PLUS', name: 'Disney+', logo: '/platforms/disney-plus.svg' },
  { id: 'YOUTUBE', name: 'YouTube', logo: '/platforms/youtube.svg' },
  { id: 'SPOTIFY', name: 'Spotify', logo: '/platforms/spotify.svg' },
];

export const PlatformGrid: React.FC<PlatformGridProps> = ({ selectedPlatform, disabled, onSelect }) => {
  return (
    <div className={`platform-grid ${disabled ? 'disabled' : ''}`}>
      {PLATFORMS.map(({ id, name, logo }) => (
        <button 
          key={id} 
          className={`platform-btn ${selectedPlatform === id ? 'active' : ''}`} 
          aria-label={name}
          disabled={disabled}
          onClick={() => onSelect(id)}
        >
          <img src={logo} alt={name} className="platform-logo" />
        </button>
      ))}
    </div>
  );
};
