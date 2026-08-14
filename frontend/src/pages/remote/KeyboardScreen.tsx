import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  CornerDownLeft,
  Delete,
  Send,
  Space,
} from 'lucide-react'
import { useEffect, useState } from 'react'

import { RemoteStatusText } from '../../components/fawkes-remote/RemoteStatusText'
import type { SafeKey } from '../../features/fawkes-remote/types'


interface KeyboardScreenProps {
  disabled: boolean
  loading: boolean
  statusMessage: string
  statusError: boolean
  /** Texto já digitado por outra tela — hoje, a consulta que ficou pendente. */
  initialText?: string | null
  onText: (text: string) => boolean
  onKey: (key: SafeKey) => void
  onBack: () => void
}

interface Tecla {
  key: SafeKey
  label: string
  content?: string
  icon?: typeof ArrowUp
}

const UTILITARIAS: ReadonlyArray<Tecla> = [
  { key: 'ESCAPE', label: 'Escape', content: 'Esc' },
  { key: 'TAB', label: 'Tab', content: 'Tab' },
  { key: 'BACKSPACE', label: 'Backspace', icon: Delete },
]

// Em cruz, não em fila. Numa grade de três colunas as quatro setas caíam como
// "cima, esquerda, baixo" e "direita" ia para a linha de baixo, ao lado do
// espaço: para apertar "baixo" a pessoa precisava ler o ícone, porque a
// posição dizia outra coisa.
const SETAS: ReadonlyArray<Tecla> = [
  { key: 'ARROW_UP', label: 'Seta para cima', icon: ArrowUp },
  { key: 'ARROW_LEFT', label: 'Seta para esquerda', icon: ArrowLeft },
  { key: 'ARROW_DOWN', label: 'Seta para baixo', icon: ArrowDown },
  { key: 'ARROW_RIGHT', label: 'Seta para direita', icon: ArrowRight },
]

const CONFIRMACAO: ReadonlyArray<Tecla> = [
  { key: 'SPACE', label: 'Espaço', icon: Space },
  { key: 'ENTER', label: 'Enter', icon: CornerDownLeft },
]

export function KeyboardScreen({
  disabled,
  loading,
  statusMessage,
  statusError,
  initialText = null,
  onText,
  onKey,
  onBack,
}: KeyboardScreenProps) {
  const [text, setText] = useState(initialText ?? '')

  // Só semeia quando muda de verdade: reaplicar a cada render sobrescreveria o
  // que a pessoa está digitando.
  useEffect(() => {
    if (initialText) setText(initialText)
  }, [initialText])
  // `loading` (comando em voo) NÃO desabilita nada: no iOS, marcar um input
  // focado como disabled fecha o teclado virtual na hora, então cada envio
  // derrubava o teclado e o usuário precisava tocar no campo de novo.
  // O estado em voo agora é só visual, via aria-busy.
  const controlsDisabled = disabled

  const botao = ({ key, label, content, icon: Icon }: Tecla) => (
    <button
      key={key}
      type="button"
      className={`keyboard-keys__key keyboard-keys__key--${key.toLowerCase()}`}
      aria-label={label}
      disabled={controlsDisabled}
      onClick={() => onKey(key)}
    >
      {Icon ? <Icon size={19} aria-hidden="true" /> : content}
    </button>
  )

  return (
    <main className="remote-screen keyboard-screen" aria-labelledby="keyboard-screen-title">
      <button type="button" className="remote-screen__back" aria-label="Voltar" onClick={onBack}>
        <ArrowLeft size={18} aria-hidden="true" />
        Voltar
      </button>

      <div className="keyboard-screen__heading">
        <p className="remote-screen__eyebrow">Entrada remota</p>
        <h2 id="keyboard-screen-title">Teclado</h2>
        <p>Texto temporário e teclas especiais seguras.</p>
      </div>

      <RemoteStatusText message={statusMessage} error={statusError} />

      <form
        className="keyboard-text"
        aria-busy={loading}
        onSubmit={(event) => {
          event.preventDefault()
          if (controlsDisabled || !text.trim()) return
          if (onText(text)) setText('')
        }}
      >
        <label htmlFor="remote-keyboard-text">Texto para enviar</label>
        <div>
          <input
            id="remote-keyboard-text"
            type="text"
            value={text}
            maxLength={256}
            autoComplete="off"
            spellCheck={false}
            disabled={controlsDisabled}
            placeholder="Digite sem salvar histórico"
            enterKeyHint="send"
            autoCapitalize="sentences"
            autoCorrect="off"
            aria-busy={loading}
            onChange={(event) => setText(event.target.value)}
          />
          <button
            type="submit"
            aria-label="Enviar texto"
            disabled={controlsDisabled || !text.trim()}
          >
            <Send size={19} aria-hidden="true" />
          </button>
        </div>
        <span>{text.length}/256 · não armazenado</span>
      </form>

      <section className="keyboard-keys" aria-label="Teclas especiais seguras">
        <div className="keyboard-keys__row">{UTILITARIAS.map(botao)}</div>
        <div className="keyboard-keys__arrows">{SETAS.map(botao)}</div>
        <div className="keyboard-keys__row keyboard-keys__row--pair">
          {CONFIRMACAO.map(botao)}
        </div>
      </section>

      <p className="keyboard-screen__notice">
        Ctrl, Alt, atalhos combinados e comandos arbitrários não são enviados.
      </p>
    </main>
  )
}
