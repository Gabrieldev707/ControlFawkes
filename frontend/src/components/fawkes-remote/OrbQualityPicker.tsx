import {
  ORB_QUALITY_LEVELS,
  type OrbQuality,
} from './orbQuality'


interface OrbQualityPickerProps {
  quality: OrbQuality
  onChange: (quality: OrbQuality) => void
}

const LABELS: Record<OrbQuality, string> = {
  LOW: 'Leve',
  BALANCED: 'Equilibrado',
  HIGH: 'Máximo',
}

/** Painel de ajuste do orb. Só é montado em desenvolvimento. */
export function OrbQualityPicker({ quality, onChange }: OrbQualityPickerProps) {
  return (
    <div className="orb-quality-picker" role="group" aria-label="Qualidade do orb">
      {ORB_QUALITY_LEVELS.map((level) => (
        <button
          key={level}
          type="button"
          aria-pressed={level === quality}
          onClick={() => onChange(level)}
        >
          {LABELS[level]}
        </button>
      ))}
    </div>
  )
}
