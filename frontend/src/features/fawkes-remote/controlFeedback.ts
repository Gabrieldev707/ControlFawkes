export type ControlFeedbackZone =
  | 'none'
  | 'pc-volume'
  | 'player-volume'
  | 'transport'
  | 'utility'
  | 'voice'
  | 'search'
  | 'touchpad';

export interface ControlFeedbackState {
  zone: ControlFeedbackZone;
  pulseId: number;
}

export const initialControlFeedback: ControlFeedbackState = {
  zone: 'none',
  pulseId: 0,
};

export function activateControlFeedback(
  previous: ControlFeedbackState,
  zone: Exclude<ControlFeedbackZone, 'none'>,
): ControlFeedbackState {
  return {
    zone,
    pulseId: previous.pulseId + 1,
  };
}

export function clearControlFeedback(previous: ControlFeedbackState): ControlFeedbackState {
  return {
    zone: 'none',
    pulseId: previous.pulseId,
  };
}
