import { useState } from 'react'
import { Clapperboard, ExternalLink, Search, X } from 'lucide-react'

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
  /**
   * Tudo o que o catálogo achou, em ordem.
   *
   * Os dois campos acima são os dois primeiros desta lista, mantidos porque o
   * protocolo antigo só tinha eles. Dois era o formato de "adivinhar a obra e
   * oferecer a alternativa"; para BUSCAR é pouco, e o quanto ficou medido em
   * 25/08/2026 — "capitão américa" mostrava o filme de 1990, que não está em
   * serviço nenhum, e mais um. Os quatro da Marvel não cabiam no protocolo.
   */
  availabilityOptions?: TitleAvailability[]
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
  availabilityOptions = [],
  disabled,
  onChoose,
  onOpenPlatform,
  onCancel,
}: PlatformChoiceProps) {
  // Qual resultado está em foco. Fica aqui e não no estado da página porque é
  // escolha de apresentação: o comando enviado é o mesmo para todos, o que
  // muda é para onde o botão leva.
  const [emFocoIndice, setEmFocoIndice] = useState(0)

  // A lista, com recuo para os dois campos antigos quando ela não vem — é o
  // que mantém um servidor mais velho funcionando com esta tela.
  const opcoes = availabilityOptions.length > 0
    ? availabilityOptions
    : [availability, availabilityAlternative].filter(
      (o): o is TitleAvailability => o !== null,
    )

  const emFoco = opcoes[emFocoIndice] ?? opcoes[0] ?? null
  const outras = opcoes.filter((_, i) => i !== emFocoIndice)

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

      {emFoco != null ? (
        <TitleAvailabilityCard
          availability={emFoco}
          disabled={disabled}
          onChoose={goToPlatform}
        />
      ) : null}

      {/* Os outros resultados, em vez de um botão que alterna entre dois.
          
          A troca binária era honesta quando havia duas leituras do mesmo nome.
          Ela deixou de ser quando a busca passou a devolver oito: com dois
          slots, "capitão américa" escondia os quatro filmes da Marvel atrás de
          um resultado de 1990 que não está em serviço nenhum.

          Onde assistir vai em cada linha porque é o que decide o toque — e uma
          lista de nomes sem isso obrigaria a abrir um por um para descobrir. */}
      {outras.length > 0 ? (
        <>
          <p className="platform-choice__group-label">
            <Clapperboard size={12} aria-hidden="true" />
            Não é esse?
          </p>
          <ul className="platform-choice__outras">
            {outras.map((opcao) => (
              <li key={`${opcao.title}-${opcao.year}-${opcao.kind}`}>
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => setEmFocoIndice(opcoes.indexOf(opcao))}
                >
                  <span className="platform-choice__outra-nome">
                    {opcao.title}
                    {opcao.year !== null ? ` (${opcao.year})` : ''}
                  </span>
                  <span className="platform-choice__outra-onde">
                    {opcao.kind === 'TV' ? 'Série' : 'Filme'}
                    {opcao.platforms.length > 0
                      ? ` · ${opcao.platforms.map((p) => PLATFORM_BRANDS[p].name).join(', ')}`
                      : ' · não encontrado nos seus serviços'}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </>
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
