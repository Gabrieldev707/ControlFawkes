import { describe, it, expect } from 'vitest';
import { isPlatform, PLATFORMS } from './types';

describe('types and validation', () => {
  it('isPlatform should return true for valid platforms', () => {
    PLATFORMS.forEach(platform => {
      expect(isPlatform(platform)).toBe(true);
    });
  });

  it('isPlatform should return false for invalid strings', () => {
    expect(isPlatform('XYZ')).toBe(false);
    expect(isPlatform('netflix')).toBe(false); // Case sensitive
    expect(isPlatform('')).toBe(false);
  });

  it('isPlatform should return false for non-strings', () => {
    expect(isPlatform(null)).toBe(false);
    expect(isPlatform(undefined)).toBe(false);
    expect(isPlatform(123)).toBe(false);
    expect(isPlatform({})).toBe(false);
  });
});
