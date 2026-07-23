import { ShieldCheck } from 'lucide-react'

import type { AuthState } from '../../features/fawkes-remote/types'


interface AuthenticationStatusProps {
  authState: AuthState
  connected: boolean
}

const AUTH_LABELS: Record<AuthState, string> = {
  checking: 'Verificando autenticação',
  pairing_required: 'Pareamento necessário',
  pairing: 'Pareando dispositivo',
  authenticated: 'Dispositivo autenticado',
  rejected: 'Autenticação recusada',
}

export function AuthenticationStatus({ authState, connected }: AuthenticationStatusProps) {
  const label = connected ? AUTH_LABELS[authState] : 'Autenticação aguardando conexão'

  return (
    <p
      className={`authentication-status${authState === 'authenticated' && connected ? ' authentication-status--verified' : ''}`}
      aria-live="polite"
    >
      <ShieldCheck size={13} aria-hidden="true" />
      {label}
    </p>
  )
}
