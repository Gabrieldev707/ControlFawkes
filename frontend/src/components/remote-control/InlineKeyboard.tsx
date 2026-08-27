import { CornerDownLeft, Send } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import type { SafeKey } from '../../features/fawkes-remote/types'


interface InlineKeyboardProps {
  disabled: boolean
  /**
   * A consulta que ficou pendente por cair numa plataforma sem busca por URL.
   *
   * Sem isto, o controle mandava abrir o Disney+, avisava "digite no
   * computador" e entregava um campo vazio — a pessoa tinha que lembrar e
   * redigitar o que acabara de escrever na tela inicial.
   */
  initialText?: string | null
  onText: (text: string) => boolean
  onKey: (key: SafeKey) => void
}

/**
 * Digitar sem sair da tela de Controle.
 *
 * O login de uma plataforma exigia um vaivém absurdo: ir ao Touchpad para
 * clicar no campo, ao Teclado para digitar, voltar ao Touchpad para o campo
 * seguinte, e ao Teclado de novo. Três telas para preencher dois campos.
 *
 * Com a superfície aqui do lado — que já clica e já manda Tab — falta só o
 * texto. Junto, dá para entrar numa conta inteira sem trocar de tela uma vez.
 *
 * O teclado completo continua existindo, para as teclas especiais.
 */
export function InlineKeyboard({
  disabled,
  initialText = null,
  onText,
  onKey,
}: InlineKeyboardProps) {
  const [text, setText] = useState(initialText ?? '')
  const semeado = useRef(initialText)

  // Só semeia quando muda de verdade: reaplicar a cada render sobrescreveria o
  // que a pessoa está digitando.
  useEffect(() => {
    if (initialText === semeado.current) return
    semeado.current = initialText
    if (initialText !== null) setText(initialText)
  }, [initialText])

  const enviar = () => {
    if (!text.trim()) return
    // Só limpa quando o envio foi aceito: perder o que foi digitado por causa
    // de uma conexão instável seria pior do que repetir o toque.
    if (onText(text)) setText('')
  }

  return (
    <form
      className="inline-keyboard"
      aria-label="Digitar no computador"
      onSubmit={(event) => {
        event.preventDefault()
        enviar()
      }}
    >
      <input
        type="text"
        value={text}
        disabled={disabled}
        aria-label="Texto para o computador"
        placeholder="Digitar no computador…"
        autoComplete="off"
        autoCorrect="off"
        autoCapitalize="none"
        spellCheck={false}
        maxLength={256}
        onChange={(event) => setText(event.target.value)}
      />
      <button type="submit" aria-label="Enviar texto" disabled={disabled || !text.trim()}>
        <Send size={16} aria-hidden="true" />
      </button>
      <button
        type="button"
        aria-label="Enter"
        disabled={disabled}
        onClick={() => onKey('ENTER')}
      >
        <CornerDownLeft size={16} aria-hidden="true" />
      </button>
    </form>
  )
}
