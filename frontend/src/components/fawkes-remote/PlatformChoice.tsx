import { X } from 'lucide-react'

import type { SearchablePlatform } from '../../features/fawkes-remote/types'


interface PlatformChoiceProps {
  query: string
  platforms: SearchablePlatform[]
  disabled: boolean
  onChoose: (platform: SearchablePlatform) => void
  onCancel: () => void
}

const PLATFORM_DETAILS: Record<SearchablePlatform, { name: string; logo: string }> = {
  NETFLIX: { name: 'Netflix', logo: '/platforms/netflix.svg' },
  PRIME_VIDEO: { name: 'Prime Video', logo: '/platforms/prime-video.svg' },
  YOUTUBE: { name: 'YouTube', logo: '/platforms/youtube.svg' },
  SPOTIFY: { name: 'Spotify', logo: '/platforms/spotify.svg' },
}

export function PlatformChoice({
  query,
  platforms,
  disabled,
  onChoose,
  onCancel,
}: PlatformChoiceProps) {
  return (
    <section
      className="platform-choice"
      role="group"
      aria-labelledby="platform-choice-title"
    >
      <div className="platform-choice__head">
        <h2 id="platform-choice-title" className="platform-choice__title">
          Onde você quer procurar “{query}”?
        </h2>
        <button
          type="button"
          className="platform-choice__cancel"
          aria-label="Cancelar busca"
          onClick={onCancel}
        >
          <X size={18} aria-hidden="true" />
        </button>
      </div>

      {/* A ordem vem do backend: ele sugere música primeiro quando o usuário
          usou um verbo musical. */}
      <div className="platform-choice__options">
        {platforms.map((platform) => {
          const { name, logo } = PLATFORM_DETAILS[platform]
          return (
            <button
              key={platform}
              type="button"
              className="platform-choice__option"
              disabled={disabled}
              onClick={() => onChoose(platform)}
            >
              <img src={logo} alt="" aria-hidden="true" className="platform-logo" />
              <span>{name}</span>
            </button>
          )
        })}
      </div>
    </section>
  )
}
