import { Keyboard, X } from 'lucide-react'


interface PendingSearchHandoffProps {
  query: string
  onOpenKeyboard: () => void
  onDismiss: () => void
}

/**
 * Ponte entre "abri o Max" e "achei o filme".
 *
 * Max e Disney+ não aceitam a consulta pela URL, então a plataforma abre na
 * home e o título ficaria para trás. Aqui ele continua à mão: um toque leva ao
 * teclado remoto já com o texto pronto para mandar para a busca da própria
 * plataforma.
 */
export function PendingSearchHandoff({
  query,
  onOpenKeyboard,
  onDismiss,
}: PendingSearchHandoffProps) {
  return (
    <section className="search-handoff" aria-labelledby="search-handoff-title">
      <div className="search-handoff__head">
        <p id="search-handoff-title" className="search-handoff__title">
          Abra a busca e digite daqui
        </p>
        <button
          type="button"
          className="search-handoff__dismiss"
          aria-label="Dispensar"
          onClick={onDismiss}
        >
          <X size={15} aria-hidden="true" />
        </button>
      </div>

      <p className="search-handoff__query">“{query}”</p>

      <button
        type="button"
        className="search-handoff__action"
        onClick={onOpenKeyboard}
      >
        <Keyboard size={17} aria-hidden="true" />
        Digitar no computador
      </button>
    </section>
  )
}
