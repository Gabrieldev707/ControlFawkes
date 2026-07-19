import React from 'react';

const PLATFORMS = [
  { id: 'netflix', name: 'Netflix', logo: '/platforms/netflix.svg' },
  { id: 'max', name: 'Max', logo: '/platforms/max.svg' },
  { id: 'prime', name: 'Prime Video', logo: '/platforms/prime-video.svg' },
  { id: 'disney', name: 'Disney+', logo: '/platforms/disney-plus.svg' },
  { id: 'youtube', name: 'YouTube', logo: '/platforms/youtube.svg' },
  { id: 'spotify', name: 'Spotify', logo: '/platforms/spotify.svg' },
];

export const PlatformGrid: React.FC = () => {
  return (
    <div className="platform-grid">
      {PLATFORMS.map(({ id, name, logo }) => (
        <button key={id} className="platform-btn" aria-label={name}>
          <img src={logo} alt={name} className="platform-logo" />
        </button>
      ))}
    </div>
  );
};
