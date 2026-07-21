import React from 'react';
import { Minus, Plus, Volume2, VolumeX } from 'lucide-react';
import './CosmicRemoteControl.css';

export interface VerticalVolumeRailProps {
  id: string;
  label: string;
  value?: number;
  muted?: boolean;
  disabled?: boolean;
  accent: 'violet' | 'champagne';
  onChange?: (value: number) => void;
  onStep?: (delta: -5 | 5) => void;
  onToggleMute?: () => void;
  onInteraction?: () => void;
  unavailableReason?: string;
}

function getControlSubject(label: string) {
  if (label.toUpperCase() === 'PC') return 'computador';
  if (label.toUpperCase() === 'PLAYER') return 'player';
  return label;
}

export const VerticalVolumeRail: React.FC<VerticalVolumeRailProps> = ({
  id,
  label,
  value,
  muted = false,
  disabled = false,
  accent,
  onChange,
  onStep,
  onToggleMute,
  onInteraction,
  unavailableReason,
}) => {
  const subject = getControlSubject(label);
  const volumeLabel = `Volume do ${subject}`;
  const reasonId = unavailableReason ? `${id}-reason` : undefined;
  const unavailable = disabled || value === undefined;
  const currentValue = value ?? 0;
  const canIncrease = !unavailable && currentValue + 5 <= 100;
  const canDecrease = !unavailable && currentValue - 5 >= 0;

  const interact = (callback?: () => void) => {
    if (unavailable) return;
    onInteraction?.();
    callback?.();
  };

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (unavailable) return;
    const nextValue = Number.parseInt(event.target.value, 10);
    if (Number.isNaN(nextValue)) return;
    interact(() => onChange?.(Math.min(100, Math.max(0, nextValue))));
  };

  const handleStep = (delta: -5 | 5) => {
    if ((delta === 5 && !canIncrease) || (delta === -5 && !canDecrease)) return;
    interact(() => onStep?.(delta));
  };

  return (
    <section
      className={`vertical-volume-rail vertical-volume-rail--${accent} ${unavailable ? 'is-disabled' : ''}`}
      data-accent={accent}
      data-testid={`${id}-rail`}
      aria-labelledby={`${id}-title`}
      aria-describedby={reasonId}
    >
      <h2 id={`${id}-title`} className="vertical-volume-rail__label" aria-label={volumeLabel}>
        {label}
      </h2>
      <output className="vertical-volume-rail__value" aria-live="polite">
        {value === undefined ? '—' : `${value}%`}
      </output>

      <div className="vertical-volume-rail__controls" data-testid={`${id}-controls`}>
        <button
          type="button"
          className="vertical-volume-rail__step"
          aria-label={`Aumentar ${volumeLabel.toLocaleLowerCase('pt-BR')}`}
          aria-disabled={!canIncrease ? 'true' : undefined}
          onClick={() => handleStep(5)}
          disabled={!canIncrease}
        >
          <Plus aria-hidden="true" />
        </button>

        <input
          type="range"
          min="0"
          max="100"
          step="1"
          value={currentValue}
          onChange={handleChange}
          onPointerDown={() => interact()}
          disabled={unavailable}
          className="vertical-volume-rail__slider"
          aria-label={volumeLabel}
          aria-orientation="vertical"
          aria-describedby={reasonId}
          style={{ '--volume-progress': `${currentValue}%` } as React.CSSProperties}
        />

        <button
          type="button"
          className="vertical-volume-rail__step"
          aria-label={`Diminuir ${volumeLabel.toLocaleLowerCase('pt-BR')}`}
          aria-disabled={!canDecrease ? 'true' : undefined}
          onClick={() => handleStep(-5)}
          disabled={!canDecrease}
        >
          <Minus aria-hidden="true" />
        </button>

        <button
          type="button"
          className={`vertical-volume-rail__mute ${muted ? 'is-muted' : ''}`}
          aria-label={`${muted ? 'Desativar' : 'Ativar'} mudo do ${subject}`}
          aria-disabled={unavailable ? 'true' : undefined}
          onClick={() => interact(onToggleMute)}
          disabled={unavailable}
        >
          {muted ? <VolumeX aria-hidden="true" /> : <Volume2 aria-hidden="true" />}
          <span>{muted ? 'Som' : 'Mudo'}</span>
        </button>
      </div>

      {unavailableReason ? (
        <p id={reasonId} className="vertical-volume-rail__reason">
          {unavailableReason}
        </p>
      ) : null}
    </section>
  );
};
