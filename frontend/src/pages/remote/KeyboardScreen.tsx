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
import { useState } from 'react'

import { RemoteStatusText } from '../../components/fawkes-remote/RemoteStatusText'
import type { SafeKey } from '../../features/fawkes-remote/types'


interface KeyboardScreenProps {
  disabled: boolean
  loading: boolean
  statusMessage: string
  statusError: boolean
  onText: (text: string) => boolean
  onKey: (key: SafeKey) => void
  onBack: () => void
}

const SPECIAL_KEYS: ReadonlyArray<{
  key: SafeKey
  label: string
  content?: string
  icon?: typeof ArrowUp
}> = [
  { key: 'ESCAPE', label: 'Escape', content: 'Esc' },
  { key: 'TAB', label: 'Tab', content: 'Tab' },
  { key: 'BACKSPACE', label: 'Backspace', icon: Delete },
  { key: 'ARROW_UP', label: 'Seta para cima', icon: ArrowUp },
  { key: 'ARROW_LEFT', label: 'Seta para esquerda', icon: ArrowLeft },
  { key: 'ARROW_DOWN', label: 'Seta para baixo', icon: ArrowDown },
  { key: 'ARROW_RIGHT', label: 'Seta para direita', icon: ArrowRight },
  { key: 'SPACE', label: 'Espaço', icon: Space },
  { key: 'ENTER', label: 'Enter', icon: CornerDownLeft },
]

export function KeyboardScreen({
  disabled,
  loading,
  statusMessage,
  statusError,
  onText,
  onKey,
  onBack,
}: KeyboardScreenProps) {
  const [text, setText] = useState('')
  const controlsDisabled = disabled || loading

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
        {SPECIAL_KEYS.map(({ key, label, content, icon: Icon }) => (
          <button
            key={key}
            type="button"
            aria-label={label}
            disabled={controlsDisabled}
            onClick={() => onKey(key)}
          >
            {Icon ? <Icon size={19} aria-hidden="true" /> : content}
          </button>
        ))}
      </section>

      <p className="keyboard-screen__notice">
        Ctrl, Alt, atalhos combinados e comandos arbitrários não são enviados.
      </p>
    </main>
  )
}
