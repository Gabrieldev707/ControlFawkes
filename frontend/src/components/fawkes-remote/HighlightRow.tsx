import { ImageOff } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import type { Platform } from '../../features/fawkes-remote/types'


export interface Destaque {
  title: string
  year: number | null
  posterUrl: string
}

interface HighlightRowProps {
  platform: Platform
  logo: string
  name: string
  titles: Destaque[]
  disabled: boolean
  onOpenPlatform: (platform: Platform) => void
  onPickTitle: (platform: Platform, title: string) => void
}

/**
 * Uma faixa de capas por serviço.
 *
 * A tela de plataformas era uma grade de seis logotipos: pedia uma decisão
 * ("qual serviço?") que ninguém toma sem antes saber o que tem para assistir.
 * Com as capas, a pergunta vira a certa — "o que a gente vê hoje?" — e o
 * serviço é só consequência de qual capa foi tocada.
 */
export function HighlightRow({
  platform,
  logo,
  name,
  titles,
  disabled,
  onOpenPlatform,
  onPickTitle,
}: HighlightRowProps) {
  return (
    <section className="highlight-row" aria-labelledby={`destaques-${platform}`}>
      <div className="highlight-row__head">
        <img src={logo} alt="" aria-hidden="true" />
        <h3 id={`destaques-${platform}`}>{name}</h3>
        <button
          type="button"
          className="highlight-row__open"
          aria-label={`Abrir ${name}`}
          disabled={disabled}
          onClick={() => onOpenPlatform(platform)}
        >
          Abrir
        </button>
      </div>

      {/* Rolagem horizontal própria: empilhar as capas verticalmente faria a
          tela crescer sem fim, e comparar serviços exigiria rolar tudo. */}
      <div className="highlight-row__strip">
        {titles.map((item) => (
          <CartaoDeCapa
            key={`${item.title}-${item.year}`}
            item={item}
            servico={name}
            disabled={disabled}
            onEscolher={() => onPickTitle(platform, item.title)}
          />
        ))}
      </div>
    </section>
  )
}

// Quanto tempo o primeiro toque continua valendo. Curto o bastante para não
// disparar sozinho depois, longo o bastante para o segundo toque ser confortável.
const MILISSEGUNDOS_PARA_CONFIRMAR = 2500

/**
 * Um cartão que só abre no segundo toque.
 *
 * Rolar a faixa com o dedo em cima de uma capa abria o título no computador
 * sem querer — o toque acontece antes de o navegador decidir que aquilo era
 * uma rolagem. Com a confirmação, o primeiro toque só arma e mostra o nome; o
 * segundo é que manda.
 */
function CartaoDeCapa({
  item,
  servico,
  disabled,
  onEscolher,
}: {
  item: Destaque
  servico: string
  disabled: boolean
  onEscolher: () => void
}) {
  const [armado, setArmado] = useState(false)
  const prazoRef = useRef<number | null>(null)

  useEffect(() => () => {
    if (prazoRef.current !== null) window.clearTimeout(prazoRef.current)
  }, [])

  function tocar() {
    if (armado) {
      if (prazoRef.current !== null) window.clearTimeout(prazoRef.current)
      setArmado(false)
      onEscolher()
      return
    }
    setArmado(true)
    prazoRef.current = window.setTimeout(() => setArmado(false), MILISSEGUNDOS_PARA_CONFIRMAR)
  }

  return (
    <button
      type="button"
      className="highlight-card"
      data-armado={armado}
      aria-label={
        armado
          ? `Confirmar: abrir ${item.title} no ${servico}`
          : `${item.title}${item.year ? ` (${item.year})` : ''} no ${servico}`
      }
      disabled={disabled}
      onClick={tocar}
    >
      <span className="highlight-card__capa">
        <Capa src={item.posterUrl} />
        {armado ? (
          <span className="highlight-card__confirmar">Tocar de novo para abrir</span>
        ) : null}
      </span>
      <span className="highlight-card__title">{item.title}</span>
    </button>
  )
}

/**
 * Uma capa que sabe falhar.
 *
 * O pôster vem de `image.tmdb.org`, um servidor que o controle não opera: se o
 * celular estiver sem internet — só na rede local, que é um cenário normal
 * aqui — o navegador desenha o ícone de imagem quebrada em cima do cartão. O
 * lugar vazio é feio; o ícone quebrado é pior, porque parece defeito do app.
 */
function Capa({ src }: { src: string }) {
  const [falhou, setFalhou] = useState(false)

  if (falhou) {
    return (
      <span className="highlight-card__vazio highlight-card__vazio--falhou" aria-hidden="true">
        <ImageOff size={18} />
      </span>
    )
  }
  return (
    <img
      src={src}
      alt=""
      aria-hidden="true"
      loading="lazy"
      onError={() => setFalhou(true)}
    />
  )
}

/**
 * A mesma faixa, antes das capas chegarem.
 *
 * O nome e o logotipo do serviço já são conhecidos sem rede nenhuma, então
 * mostrar um spinner sobre a tela vazia era esconder de graça o que já se
 * sabia. Buscar os destaques dos seis serviços leva alguns segundos; com a
 * estrutura no lugar, só as capas aparecem depois.
 */
export function HighlightRowSkeleton({ logo, name }: { logo: string; name: string }) {
  return (
    <section className="highlight-row highlight-row--esqueleto" aria-hidden="true">
      <div className="highlight-row__head">
        <img src={logo} alt="" />
        <h3>{name}</h3>
      </div>
      <div className="highlight-row__strip">
        {[0, 1, 2, 3].map((i) => (
          <span key={i} className="highlight-card__vazio" />
        ))}
      </div>
    </section>
  )
}
