import React, { useState } from 'react'
import { Send } from 'lucide-react'


interface TextInputProps {
  disabled: boolean
  executing: boolean
  onSubmit: (query: string) => boolean
}

export const TextInput: React.FC<TextInputProps> = ({ disabled, executing, onSubmit }) => {
  const [query, setQuery] = useState('')
  const [errorMessage, setErrorMessage] = useState('')
  const unavailable = disabled || executing

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const normalizedQuery = query.trim()
    if (!normalizedQuery || unavailable) return

    if (onSubmit(normalizedQuery)) {
      setQuery('')
      setErrorMessage('')
    } else {
      setErrorMessage('Conexão indisponível. Tente novamente.')
    }
  }

  return (
    <form className="text-input-wrapper" onSubmit={handleSubmit}>
      <label className="visually-hidden" htmlFor="text-command">Comando de texto</label>
      <input
        id="text-command"
        type="text"
        placeholder="O que vamos assistir?"
        autoComplete="off"
        maxLength={500}
        value={query}
        disabled={unavailable}
        onChange={(event) => {
          setQuery(event.target.value)
          if (errorMessage) setErrorMessage('')
        }}
      />
      <button
        className="text-submit-btn"
        type="submit"
        aria-label="Enviar comando"
        disabled={unavailable || !query.trim()}
      >
        <Send size={18} aria-hidden="true" />
      </button>
      {errorMessage && <p className="text-input-error" role="alert">{errorMessage}</p>}
    </form>
  )
}
