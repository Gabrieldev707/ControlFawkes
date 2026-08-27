import { Clapperboard, Play, SearchX } from 'lucide-react'
import { useState } from 'react'

import { PLATFORM_BRANDS } from '../../features/fawkes-remote/platformBrand'
import type { Platform, TitleAvailability } from '../../features/fawkes-remote/types'


interface TitleAvailabilityCardProps {
  /** O que está sendo mostrado agora. */
  availability: TitleAvailability
  /**
   * A outra leitura do mesmo nome, quando existe.
   *
   * Medido no catálogo: "o justiceiro" é um filme de 2004 no Max e a série da
   * Marvel de 2017 no Disney+; "one piece" é o anime de 1999 e um filme de
   * 2026. Escolher sozinho manda metade das pessoas para a plataforma errada.
   */
  alternative?: TitleAvailability | null
  onSwitch?: () => void
  disabled: boolean
  onChoose: (platform: Platform) => void
}

function rotuloDoTipo(availability: TitleAvailability): string {
  return availability.kind === 'TV' ? 'Série' : 'Filme'
}

/**
 * A resposta em vez da pergunta.
 *
 * Antes o controle listava seis plataformas e deixava a pessoa adivinhar em
 * qual o título estava — e a resposta certa era, várias vezes, uma das duas que
 * nem apareciam na lista. Aqui ele diz onde está e oferece ir direto.
 */
export function TitleAvailabilityCard({
  availability,
  alternative = null,
  onSwitch,
  disabled,
  onChoose,
}: TitleAvailabilityCardProps) {
  const { title, year, posterUrl, platforms } = availability
  const podeTrocar = alternative !== null && onSwitch !== undefined
  // O pôster vem de fora; sem internet no celular o navegador desenharia o
  // ícone de imagem quebrada, que parece defeito do controle. Guarda a URL
  // que falhou porque trocar filme por série troca o pôster no mesmo cartão.
  const [capaQuebrada, setCapaQuebrada] = useState<string | null>(null)

  return (
    <section className="title-card" aria-labelledby="title-card-name">
      {posterUrl !== null && posterUrl !== capaQuebrada ? (
        <img
          className="title-card__poster"
          src={posterUrl}
          alt=""
          aria-hidden="true"
          onError={() => setCapaQuebrada(posterUrl)}
        />
      ) : (
        <span className="title-card__poster title-card__poster--empty" aria-hidden="true">
          <Clapperboard size={22} />
        </span>
      )}

      <div className="title-card__body">
        {/* Os dois botões ficam sempre visíveis, e não um link "ver o outro":
            o que o usuário precisa saber primeiro é que existe uma escolha. */}
        {podeTrocar ? (
          <div className="title-card__kinds" role="group" aria-label="Filme ou série">
            <button
              type="button"
              className="title-card__kind title-card__kind--on"
              aria-pressed={true}
            >
              {rotuloDoTipo(availability)}
            </button>
            <button
              type="button"
              className="title-card__kind"
              aria-pressed={false}
              onClick={onSwitch}
            >
              {rotuloDoTipo(alternative)}
            </button>
          </div>
        ) : (
          <p className="title-card__eyebrow">Encontrado no catálogo</p>
        )}

        <h3 id="title-card-name">
          {title}
          {year !== null ? <span className="title-card__year"> ({year})</span> : null}
        </h3>

        {platforms.length === 0 ? (
          <p className="title-card__none">
            <SearchX size={13} aria-hidden="true" />
            Não está em nenhuma assinatura sua. Procure manualmente abaixo.
          </p>
        ) : (
          <div className="title-card__platforms">
            {platforms.map((platform) => (
              <button
                key={platform}
                type="button"
                className="title-card__go"
                aria-label={`Assistir no ${PLATFORM_BRANDS[platform].name}`}
                disabled={disabled}
                onClick={() => onChoose(platform)}
              >
                <img src={PLATFORM_BRANDS[platform].logo} alt="" aria-hidden="true" />
                <span>{PLATFORM_BRANDS[platform].name}</span>
                <Play size={13} aria-hidden="true" fill="currentColor" />
              </button>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
