import { Minus, Plus, Volume2, VolumeX } from 'lucide-react'
import { useEffect, useState } from 'react'


interface VolumeBarProps {
  level: number | null
  muted: boolean
  disabled: boolean
  /** De quem é este volume: o aplicativo tocando, ou o Windows inteiro. */
  target: string | null
  onSetLevel: (level: number) => void
  /** Passo de 5 em 5, para quem prefere tocar a arrastar. */
  onDelta: (delta: -5 | 5) => void
  onToggleMute: () => void
}

/**
 * O volume do Controle, como uma barra.
 *
 * Antes eram quatro caixas iguais lado a lado — menos, mudo, número, mais —,
 * do mesmo tamanho dos outros doze botões da tela. Nada dizia qual era o mais
 * importante, e ajustar de 5 em 5 exigia uma fileira de toques.
 *
 * Aqui o arrasto é o controle principal, e os passos de 5 em 5 ficam nas
 * pontas da barra — onde o polegar já está. Os dois convivem porque servem a
 * momentos diferentes: arrastar para mudar muito, tocar para acertar o
 * último degrau. O mudo continua como botão porque é sim ou não, não
 * quantidade.
 */
export function VolumeBar({
  level,
  muted,
  disabled,
  target,
  onSetLevel,
  onDelta,
  onToggleMute,
}: VolumeBarProps) {
  // Enquanto o dedo arrasta, manda o valor do dedo — não o último confirmado
  // pelo Windows. Sem isso cada movimento voltava ao valor antigo até a
  // resposta chegar, e a barra parecia emperrada.
  const [rascunho, setRascunho] = useState<number | null>(null)

  useEffect(() => {
    if (rascunho === null) return
    if (level === rascunho) {
      setRascunho(null)
      return
    }
    // Rede de segurança para quando o Windows arredonda e nunca devolve
    // exatamente o valor pedido.
    const prazo = window.setTimeout(() => setRascunho(null), 700)
    return () => window.clearTimeout(prazo)
  }, [rascunho, level])

  const mostrado = rascunho ?? level ?? 0
  const indisponivel = disabled || level === null

  return (
    <section
      className="volume-bar"
      aria-label={`Volume ${target === null ? 'do Windows' : `do ${target}`}`}
    >
      <button
        type="button"
        className="volume-bar__mudo"
        aria-label={muted ? 'Desativar mudo' : 'Ativar mudo'}
        aria-pressed={muted}
        disabled={disabled}
        onClick={onToggleMute}
      >
        {muted
          ? <VolumeX size={20} aria-hidden="true" />
          : <Volume2 size={20} aria-hidden="true" />}
      </button>

      <p className="volume-bar__alvo">{target ?? 'Windows'}</p>
      <output className="volume-bar__valor" aria-live="polite">
        {level === null ? '—' : `${mostrado}%`}
      </output>

      <button
        type="button"
        className="volume-bar__passo"
        aria-label="Diminuir volume"
        disabled={indisponivel}
        onClick={() => onDelta(-5)}
      >
        <Minus size={17} aria-hidden="true" />
      </button>

      <input
        className="volume-bar__slider"
        type="range"
        min={0}
        max={100}
        step={1}
        value={mostrado}
        disabled={indisponivel}
        aria-label="Nível do volume"
        onChange={(evento) => {
          const valor = Number(evento.target.value)
          setRascunho(valor)
          onSetLevel(valor)
        }}
      />

      <button
        type="button"
        className="volume-bar__passo"
        aria-label="Aumentar volume"
        disabled={indisponivel}
        onClick={() => onDelta(5)}
      >
        <Plus size={17} aria-hidden="true" />
      </button>
    </section>
  )
}
