import React, { useCallback, useEffect, useRef, useState } from 'react'

import type {
  AuthState,
  KeyboardAction,
  MediaAction,
  OrbState,
  Platform,
  PointerAction,
  PointerPayload,
  SafeKey,
  ServerMessage,
  ServerState,
  VolumeAction,
} from './types'
import { PROTOCOL_VERSION } from './types'
import { useWebSocket } from '../../hooks/useWebSocket'
import { useRemoteNavigation } from '../../hooks/useRemoteNavigation'
import { generateRequestId } from '../../utils/uuid'
import { HomeShortcuts } from '../../components/navigation/HomeShortcuts'
import { RemoteNavigation } from '../../components/navigation/RemoteNavigation'
import { RemoteFeatureScreen } from '../../pages/remote/RemoteFeatureScreen'
import { PlatformsScreen } from '../../pages/remote/PlatformsScreen'
import { RemoteControlScreen } from '../../pages/remote/RemoteControlScreen'
import { VolumeScreen } from '../../pages/remote/VolumeScreen'
import { TouchpadScreen } from '../../pages/remote/TouchpadScreen'
import { KeyboardScreen } from '../../pages/remote/KeyboardScreen'
import {
  AuthenticationStatus,
  ConnectionStatus,
  PairingScreen,
  OrbStatePreview,
  PlatformGrid,
  RemoteOrb,
  RemoteStatusText,
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

function containsUnsafeKeyboardCharacter(value: string): boolean {
  for (let index = 0; index < value.length; index += 1) {
    const codeUnit = value.charCodeAt(index)
    if (codeUnit <= 0x1f || (codeUnit >= 0x7f && codeUnit <= 0x9f)) return true
    if (codeUnit >= 0xd800 && codeUnit <= 0xdbff) {
      const next = value.charCodeAt(index + 1)
      if (next < 0xdc00 || next > 0xdfff) return true
      index += 1
    } else if (codeUnit >= 0xdc00 && codeUnit <= 0xdfff) {
      return true
    }
  }
  return false
}

export const FawkesRemotePage: React.FC = () => {
  const [orbState, setOrbState] = useState<OrbState>('idle')
  const [selectedPlatform, setSelectedPlatform] = useState<Platform | null>(null)
  const [serverState, setServerState] = useState<ServerState | null>(null)
  const [authState, setAuthState] = useState<AuthState>('checking')
  const [pairingMessage, setPairingMessage] = useState('')
  const [statusMessage, setStatusMessage] = useState('Conectando ao computador...')
  const [statusError, setStatusError] = useState(false)
  const [currentMediaAction, setCurrentMediaAction] = useState<MediaAction | null>(null)
  const [currentVolumeAction, setCurrentVolumeAction] = useState<VolumeAction | null>(null)
  const [currentPointerAction, setCurrentPointerAction] = useState<PointerAction | null>(null)
  const [currentKeyboardAction, setCurrentKeyboardAction] = useState<KeyboardAction | null>(null)
  const [volumeLevel, setVolumeLevel] = useState<number | null>(null)
  const [volumeMuted, setVolumeMuted] = useState(false)
  const { currentScreen, navigate, goBack } = useRemoteNavigation()

  const currentRequestId = useRef<string | null>(null)
  const successTimeoutRef = useRef<number | null>(null)
  const hasSentAuthThisConnection = useRef(false)
  const hasLoadedVolumeScreen = useRef(false)

  const handleMessage = useCallback((message: ServerMessage) => {
    if (message.type === 'STATE_UPDATE') {
      setServerState(message.state)
      if (message.state !== 'READY' || currentRequestId.current === null) {
        setStatusMessage(message.message)
        setStatusError(false)
      }
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
      setStatusMessage(message.message)
      setStatusError(false)
      return
    }

    if (message.type === 'PAIR_RESULT') {
      localStorage.setItem(DEVICE_ID_KEY, message.deviceId)
      localStorage.setItem(TOKEN_KEY, message.token)
      setAuthState('authenticated')
      setPairingMessage('')
      setStatusMessage(message.message)
      setStatusError(false)
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
        setStatusMessage(message.message)
        setStatusError(true)
        return
      }

      if (
        message.code === 'PIN_INVALID'
        || message.code === 'PIN_EXPIRED'
        || message.code === 'TOO_MANY_ATTEMPTS'
      ) {
        setAuthState('rejected')
        setPairingMessage(message.message)
        setStatusMessage(message.message)
        setStatusError(true)
        return
      }
    }

    if ('requestId' in message && message.requestId !== currentRequestId.current) return

    if (message.type === 'COMMAND_RESULT') {
      if (message.data.intent === 'SYSTEM_VOLUME') {
        setVolumeLevel(message.data.level)
        setVolumeMuted(message.data.muted)
      }
      if (message.data.intent === 'POINTER_CONTROL') {
        setCurrentPointerAction(null)
        currentRequestId.current = null
        setOrbState('idle')
        setStatusMessage(message.message)
        setStatusError(false)
        return
      }
      if (message.data.intent === 'KEYBOARD_CONTROL') {
        setCurrentKeyboardAction(null)
        currentRequestId.current = null
        setOrbState('idle')
        setStatusMessage(message.message)
        setStatusError(false)
        return
      }
      setOrbState('success')
      setStatusMessage(message.message)
      setStatusError(false)
      if (successTimeoutRef.current) clearTimeout(successTimeoutRef.current)
      successTimeoutRef.current = window.setTimeout(() => {
        setOrbState('idle')
        setSelectedPlatform(null)
        setCurrentMediaAction(null)
        setCurrentVolumeAction(null)
        setCurrentPointerAction(null)
        setCurrentKeyboardAction(null)
        currentRequestId.current = null
        setStatusMessage('Computador pronto.')
      }, 2000)
      return
    }

    if (message.type === 'ERROR') {
      setOrbState('error')
      setStatusMessage(message.message)
      setStatusError(true)
      if (successTimeoutRef.current) clearTimeout(successTimeoutRef.current)
      successTimeoutRef.current = window.setTimeout(() => {
        setOrbState('idle')
        setSelectedPlatform(null)
        setCurrentMediaAction(null)
        setCurrentVolumeAction(null)
        setCurrentPointerAction(null)
        setCurrentKeyboardAction(null)
        currentRequestId.current = null
        setStatusMessage('Computador pronto.')
        setStatusError(false)
      }, 3000)
    }
  }, [])

  const { connectionState, sendMessage } = useWebSocket({ onMessage: handleMessage })

  useEffect(() => {
    if (connectionState !== 'connected') {
      hasSentAuthThisConnection.current = false
      hasLoadedVolumeScreen.current = false
      setServerState(null)
      setStatusMessage(
        connectionState === 'connecting'
          ? 'Conectando ao computador...'
          : 'Conexão perdida.',
      )
      setStatusError(connectionState === 'error')
      return
    }
    if (hasSentAuthThisConnection.current) return

    const deviceId = localStorage.getItem(DEVICE_ID_KEY)
    const token = localStorage.getItem(TOKEN_KEY)
    if (!deviceId || !token) {
      setAuthState('pairing_required')
      setStatusMessage('Autenticação necessária.')
      return
    }

    hasSentAuthThisConnection.current = true
    setAuthState('checking')
    setStatusMessage('Autenticando dispositivo...')
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

  const pointerDisabled = connectionState !== 'connected'
    || authState !== 'authenticated'
    || serverState !== 'READY'

  const keyboardDisabled = connectionState !== 'connected'
    || authState !== 'authenticated'
    || serverState !== 'READY'
    || currentKeyboardAction !== null

  const showOrbPreview = import.meta.env.DEV
    && new URLSearchParams(window.location.search).get('orb-preview') === '1'

  const handlePlatformSelect = (platform: Platform) => {
    if (controlsDisabled) return
    if (successTimeoutRef.current) clearTimeout(successTimeoutRef.current)

    const requestId = generateRequestId()
    currentRequestId.current = requestId
    setSelectedPlatform(platform)
    setOrbState('executing')
    setStatusMessage('Processando comando...')
    setStatusError(false)

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
      setStatusMessage('Conexão indisponível. Tente novamente.')
      setStatusError(true)
    }
  }

  const handleTextSubmit = (query: string): boolean => {
    if (controlsDisabled) {
      setStatusMessage('Conexão indisponível. Tente novamente.')
      setStatusError(true)
      return false
    }

    const requestId = generateRequestId()
    currentRequestId.current = requestId
    setOrbState('executing')
    setStatusMessage('Processando comando...')
    setStatusError(false)

    const accepted = sendMessage({
      protocolVersion: PROTOCOL_VERSION,
      type: 'TEXT_COMMAND',
      requestId,
      payload: { query },
    })
    if (!accepted) {
      currentRequestId.current = null
      setOrbState('error')
      setStatusMessage('Conexão indisponível. Tente novamente.')
      setStatusError(true)
    }
    return accepted
  }

  const handleMediaAction = (action: MediaAction) => {
    if (controlsDisabled) return
    if (successTimeoutRef.current) clearTimeout(successTimeoutRef.current)

    const requestId = generateRequestId()
    currentRequestId.current = requestId
    setCurrentMediaAction(action)
    setOrbState('executing')
    setStatusMessage('Executando controle de mídia...')
    setStatusError(false)

    const accepted = sendMessage({
      protocolVersion: PROTOCOL_VERSION,
      type: action,
      requestId,
    })
    if (!accepted) {
      currentRequestId.current = null
      setCurrentMediaAction(null)
      setOrbState('error')
      setStatusMessage('Conexão indisponível. Tente novamente.')
      setStatusError(true)
    }
  }

  const handleVolumeAction = useCallback((
    action: VolumeAction,
    value?: number | -5 | 5,
  ) => {
    if (controlsDisabled) return
    if (successTimeoutRef.current) clearTimeout(successTimeoutRef.current)

    const requestId = generateRequestId()
    currentRequestId.current = requestId
    setCurrentVolumeAction(action)
    setOrbState('executing')
    setStatusMessage(action === 'SYSTEM_VOLUME_GET' ? 'Carregando volume...' : 'Ajustando volume...')
    setStatusError(false)

    const message = action === 'SYSTEM_VOLUME_SET'
      ? {
          protocolVersion: PROTOCOL_VERSION,
          type: action,
          requestId,
          payload: { level: value as number },
        }
      : action === 'SYSTEM_VOLUME_DELTA'
        ? {
            protocolVersion: PROTOCOL_VERSION,
            type: action,
            requestId,
            payload: { delta: value as -5 | 5 },
          }
        : {
            protocolVersion: PROTOCOL_VERSION,
            type: action,
            requestId,
          }

    const accepted = sendMessage(message)
    if (!accepted) {
      currentRequestId.current = null
      setCurrentVolumeAction(null)
      setOrbState('error')
      setStatusMessage('Conexão indisponível. Tente novamente.')
      setStatusError(true)
    }
  }, [controlsDisabled, sendMessage])

  const handlePointerAction = useCallback((
    action: PointerAction,
    payload?: PointerPayload,
  ) => {
    if (pointerDisabled) return
    const requestId = generateRequestId()
    currentRequestId.current = requestId
    setCurrentPointerAction(action)
    setStatusMessage(action === 'POINTER_MOVE' ? 'Movendo ponteiro...' : 'Enviando comando...')
    setStatusError(false)

    let accepted = false
    if (action === 'POINTER_MOVE' && payload && 'dx' in payload) {
      accepted = sendMessage({
        protocolVersion: PROTOCOL_VERSION,
        type: action,
        requestId,
        payload,
      })
    } else if (action === 'POINTER_SCROLL' && payload && 'delta' in payload) {
      accepted = sendMessage({
        protocolVersion: PROTOCOL_VERSION,
        type: action,
        requestId,
        payload,
      })
    } else if (action !== 'POINTER_MOVE' && action !== 'POINTER_SCROLL' && payload === undefined) {
      accepted = sendMessage({
        protocolVersion: PROTOCOL_VERSION,
        type: action,
        requestId,
      })
    }
    if (!accepted) {
      currentRequestId.current = null
      setCurrentPointerAction(null)
      setStatusMessage('Touchpad desconectado.')
      setStatusError(true)
    }
  }, [pointerDisabled, sendMessage])

  const handleKeyboardText = useCallback((text: string): boolean => {
    if (
      keyboardDisabled
      || !text.trim()
      || text.length > 256
      || containsUnsafeKeyboardCharacter(text)
    ) return false
    const requestId = generateRequestId()
    currentRequestId.current = requestId
    setCurrentKeyboardAction('KEYBOARD_TEXT')
    setStatusMessage('Enviando texto...')
    setStatusError(false)
    const accepted = sendMessage({
      protocolVersion: PROTOCOL_VERSION,
      type: 'KEYBOARD_TEXT',
      requestId,
      payload: { text },
    })
    if (!accepted) {
      currentRequestId.current = null
      setCurrentKeyboardAction(null)
      setStatusMessage('Teclado remoto desconectado.')
      setStatusError(true)
    }
    return accepted
  }, [keyboardDisabled, sendMessage])

  const handleKeyboardKey = useCallback((key: SafeKey) => {
    if (keyboardDisabled) return
    const requestId = generateRequestId()
    currentRequestId.current = requestId
    setCurrentKeyboardAction('KEYBOARD_KEY')
    setStatusMessage('Enviando tecla...')
    setStatusError(false)
    const accepted = sendMessage({
      protocolVersion: PROTOCOL_VERSION,
      type: 'KEYBOARD_KEY',
      requestId,
      payload: { key },
    })
    if (!accepted) {
      currentRequestId.current = null
      setCurrentKeyboardAction(null)
      setStatusMessage('Teclado remoto desconectado.')
      setStatusError(true)
    }
  }, [keyboardDisabled, sendMessage])

  useEffect(() => {
    if (currentScreen !== 'VOLUME') {
      hasLoadedVolumeScreen.current = false
      return
    }
    if (
      hasLoadedVolumeScreen.current
      || connectionState !== 'connected'
      || authState !== 'authenticated'
      || serverState !== 'READY'
    ) return

    hasLoadedVolumeScreen.current = true
    handleVolumeAction('SYSTEM_VOLUME_GET')
  }, [currentScreen, connectionState, authState, serverState, handleVolumeAction])

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
          {currentScreen === 'HOME' ? (
            <main className="remote-home">
              <div className="orb-container">
                <RemoteOrb state={orbState} />
                {showOrbPreview ? (
                  <OrbStatePreview state={orbState} onChange={setOrbState} />
                ) : null}
              </div>

              <RemoteStatusText message={statusMessage} error={statusError} />
              <AuthenticationStatus
                authState={authState}
                connected={connectionState === 'connected'}
              />

              <div className="input-area">
                <PlatformGrid
                  selectedPlatform={selectedPlatform}
                  disabled={controlsDisabled}
                  onSelect={handlePlatformSelect}
                />

                <div className="main-controls">
                  <TextInput
                    disabled={controlsDisabled}
                    executing={orbState === 'executing'}
                    onSubmit={handleTextSubmit}
                  />
                  <VoiceButton />
                </div>

                <HomeShortcuts onNavigate={navigate} />
              </div>
            </main>
          ) : currentScreen === 'REMOTE_CONTROL' ? (
            <RemoteControlScreen
              disabled={controlsDisabled}
              currentAction={currentMediaAction}
              statusMessage={statusMessage}
              statusError={statusError}
              onAction={handleMediaAction}
              onNavigate={navigate}
              onBack={goBack}
            />
          ) : currentScreen === 'PLATFORMS' ? (
            <PlatformsScreen
              selectedPlatform={selectedPlatform}
              disabled={controlsDisabled}
              statusMessage={statusMessage}
              statusError={statusError}
              onSelect={handlePlatformSelect}
              onBack={goBack}
            />
          ) : currentScreen === 'VOLUME' ? (
            <VolumeScreen
              disabled={controlsDisabled}
              loading={currentVolumeAction !== null && orbState === 'executing'}
              level={volumeLevel}
              muted={volumeMuted}
              statusMessage={statusMessage}
              statusError={statusError}
              onSetLevel={(level) => handleVolumeAction('SYSTEM_VOLUME_SET', level)}
              onDelta={(delta) => handleVolumeAction('SYSTEM_VOLUME_DELTA', delta)}
              onToggleMute={() => handleVolumeAction('SYSTEM_MUTE_TOGGLE')}
              onBack={goBack}
            />
          ) : currentScreen === 'TOUCHPAD' ? (
            <TouchpadScreen
              disabled={pointerDisabled}
              currentAction={currentPointerAction}
              statusMessage={statusMessage}
              statusError={statusError}
              onAction={handlePointerAction}
              onBack={goBack}
            />
          ) : currentScreen === 'KEYBOARD' ? (
            <KeyboardScreen
              disabled={keyboardDisabled}
              loading={currentKeyboardAction !== null}
              statusMessage={statusMessage}
              statusError={statusError}
              onText={handleKeyboardText}
              onKey={handleKeyboardKey}
              onBack={goBack}
            />
          ) : (
            <RemoteFeatureScreen screen={currentScreen} onBack={goBack} />
          )}

          <RemoteNavigation
            currentScreen={currentScreen}
            onNavigate={navigate}
          />
        </>
      )}
    </div>
  )
}
