import React from 'react';
import type { OrbState } from '../../features/fawkes-remote/types';

interface RemoteStatusTextProps {
  text: string;
  state: OrbState;
}

export const RemoteStatusText: React.FC<RemoteStatusTextProps> = ({ text, state }) => (
  <p className="remote-status-text" role="status" aria-live="polite" data-state={state}>{text}</p>
);
