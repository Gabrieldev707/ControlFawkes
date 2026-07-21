import React, { useEffect, useRef, useState } from 'react';
import { VerticalVolumeRail } from './VerticalVolumeRail';

interface WindowsVolumeControlProps {
  volume: number;
  isMuted: boolean;
  onSetVolume: (level: number) => void;
  onStep: (delta: -5 | 5) => void;
  onToggleMute: () => void;
  disabled?: boolean;
  onInteraction?: () => void;
}

export const WindowsVolumeControl: React.FC<WindowsVolumeControlProps> = ({
  volume,
  isMuted,
  onSetVolume,
  onStep,
  onToggleMute,
  disabled = false,
  onInteraction,
}) => {
  const [localVolume, setLocalVolume] = useState(volume);
  const isDraggingRef = useRef(false);
  const localVolumeRef = useRef(volume);
  const confirmedVolumeRef = useRef(volume);

  useEffect(() => {
    confirmedVolumeRef.current = volume;
    if (!isDraggingRef.current) {
      setLocalVolume(volume);
      localVolumeRef.current = volume;
    }
  }, [volume]);

  const handleChange = (newVolume: number) => {
    if (disabled) return;
    setLocalVolume(newVolume);
    localVolumeRef.current = newVolume;
    onSetVolume(newVolume);
  };

  const startDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    const target = event.target as HTMLInputElement;
    if (disabled || target.type !== 'range') return;
    isDraggingRef.current = true;
  };

  const finishDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    const target = event.target as HTMLInputElement;
    if (target.type !== 'range' || !isDraggingRef.current) return;
    isDraggingRef.current = false;
    if (!disabled) onSetVolume(localVolumeRef.current);
    setLocalVolume(confirmedVolumeRef.current);
    localVolumeRef.current = confirmedVolumeRef.current;
  };

  const handleStep = (delta: -5 | 5) => {
    navigator.vibrate?.(8);
    onStep(delta);
  };

  return (
    <div
      className="windows-volume-control"
      onPointerDownCapture={startDrag}
      onPointerUpCapture={finishDrag}
      onPointerCancelCapture={finishDrag}
    >
      <VerticalVolumeRail
        id="pc-volume"
        label="PC"
        value={localVolume}
        muted={isMuted}
        disabled={disabled}
        accent="violet"
        onChange={handleChange}
        onStep={handleStep}
        onToggleMute={onToggleMute}
        onInteraction={onInteraction}
      />
    </div>
  );
};
