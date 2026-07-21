import { describe, expect, it } from 'vitest';
import { getRadialSpring } from './orbPhysics';

describe('getRadialSpring', () => {
  it('possui equilíbrio no raio de repouso da partícula', () => {
    expect(getRadialSpring(18, 18)).toBe(0);
  });

  it('puxa para dentro além do repouso e para fora aquém dele', () => {
    expect(getRadialSpring(24, 18)).toBeGreaterThan(0);
    expect(getRadialSpring(12, 18)).toBeLessThan(0);
  });

  it('limita a força para evitar saltos durante atrações temporárias', () => {
    expect(getRadialSpring(500, 10)).toBeLessThanOrEqual(0.03);
    expect(getRadialSpring(0, 40)).toBeGreaterThanOrEqual(-0.03);
  });
});
