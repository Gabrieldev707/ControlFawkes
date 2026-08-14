import { useState } from 'react'
import { ExternalLink, Search, X } from 'lucide-react'

import type {
  Platform,
  SearchablePlatform,
  TitleAvailability,
} from '../../features/fawkes-remote/types'
import { PLATFORM_BRANDS } from '../../features/fawkes-remote/platformBrand'
import { TitleAvailabilityCard } from './TitleAvailabilityCard'


interface PlatformChoiceProps {
  query: string
  platforms: SearchablePlatform[]
  /** Plataformas que o controle só consegue abrir, sem levar a consulta. */
  openOnlyPlatforms?: Platform[]
  /** O que o catálogo achou. Ausente quando ele está desligado ou não sabe. */
  availability?: TitleAvailability | null
  /** A outra leitura do mesmo nome — filme contra série. */
  availabilityAlternative?: TitleAvailability | null
  disabled: boolean
  onChoose: (platform: SearchablePlatform) => void
  onOpenPlatform: (platform: Platform) => void
  onCancel: () => void
}

export function PlatformChoice({
  query,
  platforms,
  openOnlyPlatforms = [],
  availability = null,
  availabilityAlternative = null,
  disabled,
  onChoose,
  onOpenPlatform,
  onCancel,
}: PlatformChoiceProps) {
  // Qual das duas leituras está em foco. Fica aqui e não no estado da página
  // porque é escolha de apresentação: o comando enviado é o mesmo dos dois
  // lados, o que muda é para onde o botão leva.
  const [trocado, setTrocado] = useState(false)
  const emFoco = trocado ? availabilityAlternative : availability
  const aOutra = trocado ? availability : availabilityAlternative

  // Ir direto para onde o título está: busca quando a plataforma aceita a
  // consulta pela URL, abrir quando não aceita. Quem escolheu não precisa
  // saber dessa diferença.
  const goToPlatform = (platform: Platform) => {
    if (platforms.includes(platform as SearchablePlatform)) {
      onChoose(platform as SearchablePlatform)
      return
    }
    onOpenPlatform(platform)
  }

  return (
    <section
      className="platform-choice"
      role="group"
      aria-labelledby="platform-choice-title"
    >
      <div className="platform-choice__head">
        <h2 id="platform-choice-title" className="platform-choice__title">
          {emFoco !== null && emFoco.platforms.length > 0
            ? `“${query}”`
            : `Onde você quer procurar “${query}”?`}
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

      {emFoco !== null ? (
        <TitleAvailabilityCard
          availability={emFoco}
          alternative={aOutra}
          onSwitch={() => setTrocado((atual) => !atual)}
          disabled={disabled}
          onChoose={goToPlatform}
        />
      ) : null}

      {/* O rótulo do grupo é o que diz o que o toque faz; repetir a consulta em
          cada botão só faria o leitor de tela dizer o título seis vezes. */}
      <p className="platform-choice__group-label" id="platform-choice-search">
        <Search size={12} aria-hidden="true" />
        {emFoco !== null ? 'Ou procure em outra' : 'Busca direta'}
      </p>

      {/* A ordem vem do backend: ele sugere música primeiro quando o usuário
          usou um verbo musical. */}
      <div
        className="platform-choice__options"
        role="group"
        aria-labelledby="platform-choice-search"
      >
        {platforms.map((platform) => {
          const { name, logo } = PLATFORM_BRANDS[platform]
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

      {/* Max e Disney+ não têm URL de busca estável. Em vez de sumirem da lista
          — e deixarem um título que só existe lá sem caminho nenhum —, entram
          separados, dizendo exatamente o que vai acontecer. */}
      {openOnlyPlatforms.length > 0 ? (
        <>
          <p className="platform-choice__group-label" id="platform-choice-open">
            <ExternalLink size={12} aria-hidden="true" />
            Abrir e procurar por lá
          </p>
          <div
            className="platform-choice__options"
            role="group"
            aria-labelledby="platform-choice-open"
          >
            {openOnlyPlatforms.map((platform) => {
              const { name, logo } = PLATFORM_BRANDS[platform]
              return (
                <button
                  key={platform}
                  type="button"
                  className="platform-choice__option platform-choice__option--open"
                  disabled={disabled}
                  onClick={() => onOpenPlatform(platform)}
                >
                  <img src={logo} alt="" aria-hidden="true" className="platform-logo" />
                  <span>{name}</span>
                </button>
              )
            })}
          </div>
        </>
      ) : null}
    </section>
  )
}
