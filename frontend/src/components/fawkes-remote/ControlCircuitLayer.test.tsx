import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ControlCircuitLayer } from './ControlCircuitLayer';

const circuitZones = ['pc-volume', 'player-volume', 'transport', 'utility', 'voice'] as const;

describe('ControlCircuitLayer', () => {
  it.each(circuitZones)('ativa somente o circuito de %s', (activeZone) => {
    const { container } = render(<ControlCircuitLayer activeZone={activeZone} pulseId={1} />);

    const zones = container.querySelectorAll<SVGGElement>('[data-zone]');
    expect(zones).toHaveLength(5);

    zones.forEach((zone) => {
      expect(zone.classList.contains('is-active')).toBe(zone.dataset.zone === activeZone);
      expect(zone.querySelector('[data-circuit-base]')).not.toBeNull();
      expect(zone.querySelector('[data-circuit-pulse]')).not.toBeNull();
      expect(zone.querySelectorAll('[data-circuit-origin]')).toHaveLength(1);
      expect(zone.querySelectorAll('[data-circuit-node]')).toHaveLength(2);
    });
  });

  it.each(['none', 'search', 'touchpad'] as const)('não ativa nenhum circuito para %s', (activeZone) => {
    const { container } = render(<ControlCircuitLayer activeZone={activeZone} pulseId={1} />);

    expect(container.querySelectorAll('[data-zone].is-active')).toHaveLength(0);
  });

  it('expõe o pulseId e recria a linha ativa quando ele muda', () => {
    const { container, rerender } = render(
      <ControlCircuitLayer activeZone="transport" pulseId={4} />,
    );
    const firstPulse = container.querySelector('[data-zone="transport"] [data-circuit-pulse]');

    expect(container.querySelector('svg')?.getAttribute('data-pulse-id')).toBe('4');
    expect(firstPulse?.getAttribute('data-pulse-id')).toBe('4');

    rerender(<ControlCircuitLayer activeZone="transport" pulseId={5} />);
    const restartedPulse = container.querySelector('[data-zone="transport"] [data-circuit-pulse]');

    expect(restartedPulse?.getAttribute('data-pulse-id')).toBe('5');
    expect(restartedPulse).not.toBe(firstPulse);
  });

  it('é uma camada SVG estritamente apresentacional e não intercepta ponteiros', () => {
    const { container } = render(<ControlCircuitLayer activeZone="none" pulseId={0} />);
    const svg = container.querySelector('svg');

    expect(svg?.getAttribute('aria-hidden')).toBe('true');
    expect(svg?.getAttribute('focusable')).toBe('false');
    expect(svg?.getAttribute('viewBox')).toBeTruthy();
    expect(svg?.classList.contains('control-circuit-layer')).toBe(true);
    expect(svg?.style.pointerEvents).toBe('none');
  });

  it('remove qualquer deslocamento do traço quando reducedMotion é solicitado', () => {
    const { container } = render(
      <ControlCircuitLayer activeZone="pc-volume" pulseId={3} reducedMotion />,
    );

    const svg = container.querySelector('svg');
    const pulses = container.querySelectorAll<SVGPathElement>('[data-circuit-pulse]');

    expect(svg?.classList).toContain('is-reduced-motion');
    expect(pulses).toHaveLength(5);
    pulses.forEach((pulse) => {
      expect(pulse.getAttribute('stroke-dasharray')).toBe('none');
      expect(pulse.getAttribute('stroke-dashoffset')).toBe('0');
    });
  });
});
