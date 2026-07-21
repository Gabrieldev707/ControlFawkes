import { describe, expect, it } from 'vitest';
import {
  activateControlFeedback,
  clearControlFeedback,
  initialControlFeedback,
} from './controlFeedback';

// @ts-expect-error Control feedback zones must be one of the declared values.
const invalidZone: Parameters<typeof activateControlFeedback>[1] = 'invalid-zone';
void invalidZone;

describe('control feedback', () => {
  it('starts inactive with the initial pulse identifier', () => {
    expect(initialControlFeedback).toEqual({ zone: 'none', pulseId: 0 });
  });

  it('activates the PC volume zone and increments the pulse identifier', () => {
    expect(activateControlFeedback(initialControlFeedback, 'pc-volume')).toEqual({
      zone: 'pc-volume',
      pulseId: 1,
    });
  });

  it('increments the pulse identifier when activating the same zone again', () => {
    const firstActivation = activateControlFeedback(initialControlFeedback, 'pc-volume');

    expect(activateControlFeedback(firstActivation, 'pc-volume')).toEqual({
      zone: 'pc-volume',
      pulseId: 2,
    });
  });

  it('clears the zone without resetting the pulse identifier', () => {
    const activeFeedback = activateControlFeedback(initialControlFeedback, 'transport');

    expect(clearControlFeedback(activeFeedback)).toEqual({
      zone: 'none',
      pulseId: 1,
    });
  });
});
