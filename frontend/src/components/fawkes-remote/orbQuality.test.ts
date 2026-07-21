import { describe, expect, it } from 'vitest';
import { getOrbQuality } from './orbQuality';

describe('getOrbQuality', () => {
  it('usa perfil equilibrado no mobile sem desmontar a galáxia', () => {
    expect(getOrbQuality(true)).toEqual({
      particleCount: 1400,
      maxLines: 1400,
      pixelRatioCap: 1.5,
      pointSizeScale: 1.35,
      antialias: false,
    });
  });

  it('preserva a geometria completa em telas maiores', () => {
    expect(getOrbQuality(false)).toEqual({
      particleCount: 2000,
      maxLines: 3000,
      pixelRatioCap: 2,
      pointSizeScale: 1,
      antialias: true,
    });
  });
});
