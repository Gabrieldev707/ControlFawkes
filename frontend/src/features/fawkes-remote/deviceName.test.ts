import { describe, it, expect } from 'vitest';
import { getDefaultDeviceName } from './deviceName';

describe('getDefaultDeviceName', () => {
  it('should return iPhone for iPhone user agent', () => {
    expect(getDefaultDeviceName('Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)')).toBe('iPhone');
  });

  it('should return Celular for Android user agent', () => {
    expect(getDefaultDeviceName('Mozilla/5.0 (Linux; Android 10; SM-G981B)')).toBe('Celular');
  });

  it('should return Celular for generic Mobile user agent', () => {
    expect(getDefaultDeviceName('Mozilla/5.0 (Mobile; rv:10.0)')).toBe('Celular');
  });

  it('should return Navegador for Desktop user agent', () => {
    expect(getDefaultDeviceName('Mozilla/5.0 (Windows NT 10.0; Win64; x64)')).toBe('Navegador');
  });

  it('should return Navegador when no user agent is provided', () => {
    expect(getDefaultDeviceName('')).toBe('Navegador');
  });
});
