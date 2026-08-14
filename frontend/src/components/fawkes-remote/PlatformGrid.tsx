import React from 'react';
import { PLATFORM_BRANDS, type PlatformBrand } from '../../features/fawkes-remote/platformBrand';
import type { Platform } from '../../features/fawkes-remote/types';

interface PlatformGridProps {
  selectedPlatform: Platform | null;
  disabled: boolean;
  onSelect: (platform: Platform) => void;
}

// A ordem é da tela, não do mapa: as duas primeiras são as mais usadas aqui.
const PLATFORMS: Array<{ id: Platform } & PlatformBrand> = (
  ['NETFLIX', 'MAX', 'PRIME_VIDEO', 'DISNEY_PLUS', 'YOUTUBE', 'SPOTIFY'] as Platform[]
).map((id) => ({ id, ...PLATFORM_BRANDS[id] }));

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
