import React, { useState } from 'react'


interface PairingScreenProps {
  connected: boolean
  pending: boolean
  message: string
  error: boolean
  onPair: (pin: string) => void
}

export const PairingScreen: React.FC<PairingScreenProps> = ({
  connected,
  pending,
  message,
  error,
  onPair,
}) => {
  const [pin, setPin] = useState('')
  const canSubmit = connected && !pending && pin.length === 6

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (canSubmit) onPair(pin)
  }

  return (
    <section className="pairing-panel" aria-labelledby="pairing-title">
      <p className="pairing-kicker">Conexão protegida</p>
      <h2 id="pairing-title">Parear este dispositivo</h2>
      <p className="pairing-instructions">
        Digite o PIN de seis dígitos exibido no computador.
      </p>

      <form className="pairing-form" onSubmit={handleSubmit}>
        <label htmlFor="pairing-pin">PIN de pareamento</label>
        <input
          id="pairing-pin"
          type="text"
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="[0-9]{6}"
          maxLength={6}
          value={pin}
          disabled={!connected || pending}
          onChange={(event) => setPin(event.target.value.replace(/\D/g, '').slice(0, 6))}
        />
        <button type="submit" disabled={!canSubmit}>
          {pending ? 'Pareando...' : 'Parear dispositivo'}
        </button>
      </form>

      <p
        className={`pairing-message${error ? ' pairing-message--error' : ''}`}
        aria-live="polite"
        role={error ? 'alert' : undefined}
      >
        {message || (!connected ? 'Aguardando conexão com o computador.' : '\u00a0')}
      </p>
    </section>
  )
}
