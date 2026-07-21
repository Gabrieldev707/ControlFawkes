import { ORB_STATES, type OrbState } from '../../features/fawkes-remote/types'


interface OrbStatePreviewProps {
  state: OrbState
  onChange: (state: OrbState) => void
}

export function OrbStatePreview({ state, onChange }: OrbStatePreviewProps) {
  return (
    <div className="orb-state-preview" role="group" aria-label="Teste visual da orb">
      {ORB_STATES.map((candidate) => (
        <button
          key={candidate}
          type="button"
          aria-label={`Testar estado ${candidate}`}
          aria-pressed={candidate === state}
          onClick={() => onChange(candidate)}
        >
          {candidate.replace('_', ' ')}
        </button>
      ))}
    </div>
  )
}
