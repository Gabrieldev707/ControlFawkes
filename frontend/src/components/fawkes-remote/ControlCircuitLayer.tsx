import type { ControlFeedbackZone } from '../../features/fawkes-remote/controlFeedback';
import './CosmicRemoteControl.css';

export interface ControlCircuitLayerProps {
  activeZone: ControlFeedbackZone;
  pulseId: number;
  reducedMotion?: boolean;
}

type CircuitZone = Extract<
  ControlFeedbackZone,
  'pc-volume' | 'player-volume' | 'transport' | 'utility' | 'voice'
>;

interface CircuitDefinition {
  zone: CircuitZone;
  path: string;
  origin: readonly [number, number];
  nodes: readonly (readonly [number, number])[];
}

const circuits: readonly CircuitDefinition[] = [
  {
    zone: 'pc-volume',
    path: 'M 64 142 H 108 Q 122 142 133 151',
    origin: [64, 142],
    nodes: [[105, 142], [133, 151]],
  },
  {
    zone: 'player-volume',
    path: 'M 292 142 H 248 Q 234 142 223 151',
    origin: [292, 142],
    nodes: [[251, 142], [223, 151]],
  },
  {
    zone: 'transport',
    path: 'M 178 128 C 207 128 230 151 230 180 C 230 209 207 232 178 232 C 149 232 126 209 126 180 C 126 151 149 128 178 128 Z',
    origin: [178, 128],
    nodes: [[230, 180], [178, 232]],
  },
  {
    zone: 'utility',
    path: 'M 178 136 C 202 136 222 156 222 180 C 222 204 202 224 178 224 C 154 224 134 204 134 180 C 134 156 154 136 178 136 Z',
    origin: [178, 136],
    nodes: [[222, 180], [178, 224]],
  },
  {
    zone: 'voice',
    path: 'M 178 232 V 242',
    origin: [178, 232],
    nodes: [[178, 237], [178, 242]],
  },
];

export function ControlCircuitLayer({
  activeZone,
  pulseId,
  reducedMotion = false,
}: ControlCircuitLayerProps) {
  return (
    <svg
      aria-hidden="true"
      className={`control-circuit-layer${reducedMotion ? ' is-reduced-motion' : ''}`}
      data-pulse-id={pulseId}
      focusable="false"
      pointerEvents="none"
      role="presentation"
      style={{ pointerEvents: 'none' }}
      preserveAspectRatio="xMidYMid meet"
      viewBox="0 0 356 620"
    >
      {circuits.map(({ zone, path, origin, nodes }) => {
        const isActive = activeZone === zone;

        return (
          <g
            className={`control-circuit-layer__zone control-circuit-layer__zone--${zone}${
              isActive ? ' is-active' : ''
            }`}
            data-zone={zone}
            key={zone}
          >
            <path className="control-circuit-layer__base" d={path} data-circuit-base />
            <path
              className="control-circuit-layer__pulse"
              d={path}
              data-circuit-pulse
              data-pulse-id={pulseId}
              key={`${zone}-pulse-${pulseId}`}
              pathLength={100}
              strokeDasharray={reducedMotion ? 'none' : undefined}
              strokeDashoffset={reducedMotion ? 0 : undefined}
            />
            <circle
              className="control-circuit-layer__origin"
              cx={origin[0]}
              cy={origin[1]}
              data-circuit-origin
              r="5"
            />
            {nodes.map(([x, y]) => (
              <circle
                className="control-circuit-layer__node"
                cx={x}
                cy={y}
                data-circuit-node
                key={`${zone}-${x}-${y}`}
                r="3.5"
              />
            ))}
          </g>
        );
      })}
    </svg>
  );
}
