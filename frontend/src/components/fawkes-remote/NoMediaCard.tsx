import { LayoutGrid, Moon } from 'lucide-react'


interface NoMediaCardProps {
  /** Ainda esperando a primeira leitura do computador. */
  loading?: boolean
  onOpenPlatforms: () => void
}

/**
 * "Nada tocando" é um estado normal, não uma falha.
 *
 * Antes, sem sessão de mídia, cada toque no play virava o erro "nenhuma
 * plataforma de mídia ativa foi identificada" — e o controle parecia quebrado
 * justamente na situação mais comum de todas: você acabou de pegar o celular
 * e ainda não começou a assistir nada.
 *
 * Aqui o estado é dito com calma e sai daqui com uma saída: abrir uma
 * plataforma. O resto do controle — direcional, cursor, volume, teclado —
 * continua funcionando, porque nenhum deles depende de mídia tocando.
 */
export function NoMediaCard({ loading = false, onOpenPlatforms }: NoMediaCardProps) {
  return (
    <section className="no-media" aria-label="Nada tocando">
      <span className="no-media__icon" aria-hidden="true">
        <Moon size={19} />
      </span>

      <div className="no-media__body">
        <p className="no-media__title">
          {loading ? 'Procurando o que está tocando…' : 'Nada tocando agora'}
        </p>
        <p className="no-media__hint">
          Direcional, cursor, volume e teclado seguem funcionando.
        </p>
      </div>

      <button
        type="button"
        className="no-media__action"
        aria-label="Abrir plataformas"
        onClick={onOpenPlatforms}
      >
        <LayoutGrid size={15} aria-hidden="true" />
        Abrir
      </button>
    </section>
  )
}
