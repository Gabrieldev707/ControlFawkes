import React, { useCallback, useEffect, useRef, useState } from 'react'

import type {
  AuthState,
  OrbState,
  Platform,
  ServerMessage,
  ServerState,
} from './types'
import { PROTOCOL_VERSION } from './types'
import { useWebSocket } from '../../hooks/useWebSocket'
import { generateRequestId } from '../../utils/uuid'
import {
  ConnectionStatus,
  PairingScreen,
  PlatformGrid,
  RemoteOrb,
  TextInput,
  VoiceButton,
} from '../../components/fawkes-remote'
import '../../styles/fawkes-remote.css'


const DEVICE_ID_KEY = 'controlfawkes.deviceId'
const TOKEN_KEY = 'controlfawkes.token'

function localDeviceName(): string {
  return /iPhone/i.test(navigator.userAgent) ? 'iPhone' : 'Dispositivo local'
}

function clearStoredCredentials(): void {
  localStorage.removeItem(DEVICE_ID_KEY)
  localStorage.removeItem(TOKEN_KEY)
}

export const FawkesRemotePage: React.FC = () => {
  const [orbState, setOrbState] = useState<OrbState>('idle')
  const [selectedPlatform, setSelectedPlatform] = useState<Platform | null>(null)
  const [serverState, setServerState] = useState<ServerState | null>(null)
  const [authState, setAuthState] = useState<AuthState>('checking')
  const [pairingMessage, setPairingMessage] = useState('')

  const currentRequestId = useRef<string | null>(null)
  const successTimeoutRef = useRef<number | null>(null)
  const hasSentAuthThisConnection = useRef(false)

  const handleMessage = useCallback((message: ServerMessage) => {
    if (message.type === 'STATE_UPDATE') {
      setServerState(message.state)
      if (message.state === 'AUTH_REQUIRED') {
        const hasCredentials = Boolean(
          localStorage.getItem(DEVICE_ID_KEY) && localStorage.getItem(TOKEN_KEY),
        )
        if (!hasCredentials) setAuthState('pairing_required')
      }
      return
    }

    if (message.type === 'AUTH_RESULT') {
      setAuthState('authenticated')
      setPairingMessage('')
      return
    }

    if (message.type === 'PAIR_RESULT') {
      localStorage.setItem(DEVICE_ID_KEY, message.deviceId)
      localStorage.setItem(TOKEN_KEY, message.token)
      setAuthState('authenticated')
      setPairingMessage('')
      return
    }

    if (message.type === 'ERROR') {
      if (
        message.code === 'INVALID_TOKEN'
        || message.code === 'UNAUTHORIZED'
        || message.code === 'PAIRING_REQUIRED'
      ) {
        clearStoredCredentials()
        setServerState('AUTH_REQUIRED')
        setAuthState('pairing_required')
        setPairingMessage(message.message)
        return
      }

      if (
        message.code === 'PIN_INVALID'
        || message.code === 'PIN_EXPIRED'
        || message.code === 'TOO_MANY_ATTEMPTS'
      ) {
        setAuthState('rejected')
        setPairingMessage(message.message)
        return
      }
    }

    if ('requestId' in message && message.requestId !== currentRequestId.current) return

    if (message.type === 'COMMAND_RESULT') {
      setOrbState('success')
      if (successTimeoutRef.current) clearTimeout(successTimeoutRef.current)
      successTimeoutRef.current = window.setTimeout(() => {
        setOrbState('idle')
        setSelectedPlatform(null)
        currentRequestId.current = null
      }, 2000)
      return
    }

    if (message.type === 'ERROR') {
      setOrbState('error')
      if (successTimeoutRef.current) clearTimeout(successTimeoutRef.current)
      successTimeoutRef.current = window.setTimeout(() => {
        setOrbState('idle')
        setSelectedPlatform(null)
        currentRequestId.current = null
      }, 3000)
    }
  }, [])

  const { connectionState, sendMessage } = useWebSocket({ onMessage: handleMessage })

  useEffect(() => {
    if (connectionState !== 'connected') {
      hasSentAuthThisConnection.current = false
      setServerState(null)
      return
    }
    if (hasSentAuthThisConnection.current) return

    const deviceId = localStorage.getItem(DEVICE_ID_KEY)
    const token = localStorage.getItem(TOKEN_KEY)
    if (!deviceId || !token) {
      setAuthState('pairing_required')
      return
    }

    hasSentAuthThisConnection.current = true
    setAuthState('checking')
    const accepted = sendMessage({
      protocolVersion: PROTOCOL_VERSION,
      type: 'AUTH',
      requestId: generateRequestId(),
      payload: { deviceId, token },
    })
    if (!accepted) hasSentAuthThisConnection.current = false
  }, [connectionState, sendMessage])

  useEffect(() => () => {
    if (successTimeoutRef.current) clearTimeout(successTimeoutRef.current)
  }, [])

  const controlsDisabled = connectionState !== 'connected'
    || authState !== 'authenticated'
    || serverState !== 'READY'
    || orbState === 'executing'

  const handlePlatformSelect = (platform: Platform) => {
    if (controlsDisabled) return
    if (successTimeoutRef.current) clearTimeout(successTimeoutRef.current)

    const requestId = generateRequestId()
    currentRequestId.current = requestId
    setSelectedPlatform(platform)
    setOrbState('executing')

    const accepted = sendMessage({
      protocolVersion: PROTOCOL_VERSION,
      type: 'PLATFORM_SELECTED',
      requestId,
      payload: { platform },
    })
    if (!accepted) {
      currentRequestId.current = null
      setSelectedPlatform(null)
      setOrbState('error')
    }
  }

  const attemptPairing = (pin: string) => {
    setPairingMessage('')
    const accepted = sendMessage({
      protocolVersion: PROTOCOL_VERSION,
      type: 'PAIR_DEVICE',
      requestId: generateRequestId(),
      payload: { pin, deviceName: localDeviceName() },
    })
    if (accepted) {
      setAuthState('pairing')
    } else {
      setAuthState('rejected')
      setPairingMessage('Conexão indisponível. Tente novamente.')
    }
  }

  const showPairing = authState === 'pairing_required'
    || authState === 'pairing'
    || authState === 'rejected'

  return (
    <div className="remote-container">
      <div className="remote-header">
        <h1 className="remote-title">FAWKES</h1>
        <ConnectionStatus state={connectionState} />
      </div>

      {showPairing ? (
        <PairingScreen
          connected={connectionState === 'connected'}
          pending={authState === 'pairing'}
          message={pairingMessage}
          error={authState === 'rejected' || Boolean(pairingMessage)}
          onPair={attemptPairing}
        />
      ) : (
        <>
          <div className="orb-container">
            <RemoteOrb state={orbState} />
          </div>

          <div className="input-area">
            <PlatformGrid
              selectedPlatform={selectedPlatform}
              disabled={controlsDisabled}
              onSelect={handlePlatformSelect}
            />

            <div className="main-controls">
              <TextInput />
              <VoiceButton />
            </div>
          </div>
        </>
      )}
    </div>
  )
}
