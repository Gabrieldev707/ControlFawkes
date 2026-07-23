import React from 'react'


interface RemoteStatusTextProps {
  message: string
  error: boolean
}

export const RemoteStatusText: React.FC<RemoteStatusTextProps> = ({ message, error }) => (
  <p
    className={`remote-status-text${error ? ' remote-status-text--error' : ''}`}
    aria-live="polite"
    role={error ? 'alert' : undefined}
  >
    {message || '\u00a0'}
  </p>
)
