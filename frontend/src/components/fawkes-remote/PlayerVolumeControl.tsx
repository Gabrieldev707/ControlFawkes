import React from 'react';
import { VerticalVolumeRail } from './VerticalVolumeRail';

export const PlayerVolumeControl: React.FC = () => (
  <VerticalVolumeRail
    id="player-volume"
    label="PLAYER"
    accent="champagne"
    disabled
  />
);
