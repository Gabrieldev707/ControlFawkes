import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Search } from 'lucide-react';
import {
  activateControlFeedback,
  clearControlFeedback,
  initialControlFeedback,
} from '../../features/fawkes-remote/controlFeedback';
import { ControlCircuitLayer } from './ControlCircuitLayer';
import { HoldToTalkButton } from './HoldToTalkButton';
import { PlayerVolumeControl } from './PlayerVolumeControl';
import { TransportCluster } from './TransportCluster';
import { WindowsVolumeControl } from './WindowsVolumeControl';

export interface MediaControlPanelProps {
  volume: number;
  isMuted: boolean;
  onSetVolume: (level: number) => void;
  onStep: (delta: -5 | 5) => void;
  onToggleMute: () => void;
  onOpenSearch: () => void;
  disabled?: boolean;
}

const FEEDBACK_DURATION_MS = 450;

export const MediaControlPanel: React.FC<MediaControlPanelProps> = ({
  volume,
  isMuted,
  onSetVolume,
  onStep,
  onToggleMute,
  onOpenSearch,
  disabled = false,
}) => {
  const [feedback, setFeedback] = useState(initialControlFeedback);
  const feedbackTimeoutRef = useRef<number | null>(null);

  const clearFeedbackTimer = useCallback(() => {
    if (feedbackTimeoutRef.current === null) return;
    window.clearTimeout(feedbackTimeoutRef.current);
    feedbackTimeoutRef.current = null;
  }, []);

  const handlePcInteraction = useCallback(() => {
    if (disabled) return;

    clearFeedbackTimer();
    setFeedback((previous) => activateControlFeedback(previous, 'pc-volume'));
    feedbackTimeoutRef.current = window.setTimeout(() => {
      feedbackTimeoutRef.current = null;
      setFeedback((previous) => clearControlFeedback(previous));
    }, FEEDBACK_DURATION_MS);
  }, [clearFeedbackTimer, disabled]);

  useEffect(() => () => clearFeedbackTimer(), [clearFeedbackTimer]);

  return (
    <div className="media-control-panel">
      <header className="view-heading">
        <span className="control-eyebrow">Controle remoto</span>
        <h1>Controle</h1>
      </header>

      <section
        className="cosmic-remote-shell"
        aria-label="Controle remoto Cosmic Core"
        data-active-zone={feedback.zone}
        data-pulse-id={feedback.pulseId}
      >
        <ControlCircuitLayer activeZone={feedback.zone} pulseId={feedback.pulseId} />

        <div className="cosmic-remote-shell__pc">
          <WindowsVolumeControl
            volume={volume}
            isMuted={isMuted}
            onSetVolume={onSetVolume}
            onStep={onStep}
            onToggleMute={onToggleMute}
            disabled={disabled}
            onInteraction={handlePcInteraction}
          />
        </div>

        <div className="cosmic-remote-shell__center">
          <TransportCluster />

          <div className="cosmic-remote-shell__footer">
            <HoldToTalkButton />
            <button
              type="button"
              className="search-access-button cosmic-remote-shell__search"
              onClick={onOpenSearch}
            >
              <Search aria-hidden="true" />
              <span>Teclado/Pesquisa</span>
            </button>
          </div>
        </div>

        <div className="cosmic-remote-shell__player">
          <PlayerVolumeControl />
        </div>

      </section>
    </div>
  );
};
