import React, { useCallback, useEffect, useRef, useState } from 'react'

import type {
  AuthState,
  NavigationAction,
  SearchablePlatform,
  VolumeScope,
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
import { useCommandFeedback } from '../../hooks/useCommandFeedback'
import { useStoredDevice } from '../../hooks/useStoredDevice'
import { generateRequestId } from '../../utils/uuid'
import { HomeShortcuts } from '../../components/navigation/HomeShortcuts'
import { RemoteNavigation } from '../../components/navigation/RemoteNavigation'
import { RemoteFeatureScreen } from '../../pages/remote/RemoteFeatureScreen'
import { PlatformsScreen } from '../../pages/remote/PlatformsScreen'
import { RemoteControlScreen } from '../../pages/remote/RemoteControlScreen'
import { VolumeScreen } from '../../pages/remote/VolumeScreen'
import { TouchpadScreen } from '../../pages/remote/TouchpadScreen'
import { KeyboardScreen } from '../../pages/remote/KeyboardScreen'
import { PlatformChoice } from '../../components/fawkes-remote/PlatformChoice'
import { OrbQualityPicker } from '../../components/fawkes-remote/OrbQualityPicker'
import type { OrbQuality } from '../../components/fawkes-remote/orbQuality'
import { loadOrbQuality, saveOrbQuality } from './orbPreferences'
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


function localDeviceName(): string {
  return /iPhone/i.test(navigator.userAgent) ? 'iPhone' : 'Dispositivo local'
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
  const storedDevice = useStoredDevice()
  const feedback = useCommandFeedback()
  const [orbState, setOrbState] = useState<OrbState>('idle')
  const [selectedPlatform, setSelectedPlatform] = useState<Platform | null>(null)
  const [serverState, setServerState] = useState<ServerState | null>(null)
  const [authState, setAuthState] = useState<AuthState>('checking')
  const [pairingMessage, setPairingMessage] = useState('')
  const [statusMessage, setStatusMessage] = useState('Conectando ao computador...')
  const [statusError, setStatusError] = useState(false)
  // Escolha de plataforma pendente. Some ao escolher, cancelar ou receber
  // outra resposta: nunca fica presa na tela.
  const [volumeScope, setVolumeScope] = useState<VolumeScope>('GLOBAL')
  const [volumeTarget, setVolumeTarget] = useState<string | null>(null)
  const [orbQuality, setOrbQuality] = useState<OrbQuality>(
    () => loadOrbQuality(storedDevice.load()?.deviceId ?? null),
  )
  const [pendingChoice, setPendingChoice] = useState<
    { requestId: string; query: string; platforms: SearchablePlatform[] } | null
  >(null)
  const [volumeLevel, setVolumeLevel] = useState<number | null>(null)
  const [volumeMuted, setVolumeMuted] = useState(false)
  const { currentScreen, navigate, goBack } = useRemoteNavigation()

  const {
    begin: beginFeedback,
    cancel: cancelFeedback,
    scheduleReset: scheduleFeedbackReset,
    isCurrent: isCurrentRequest,
    hasPending: hasPendingRequest,
    currentMediaAction,
    currentVolumeAction,
    currentPointerAction,
    currentKeyboardAction,
    currentNavigationAction,
  } = feedback
  const hasSentAuthThisConnection = useRef(false)
  const hasLoadedVolumeForScreen = useRef(false)

  const handleMessage = useCallback((message: ServerMessage) => {
    if (message.type === 'STATE_UPDATE') {
      setServerState(message.state)
      if (message.state !== 'READY' || !hasPendingRequest()) {
        setStatusMessage(message.message)
        setStatusError(false)
      }
      if (message.state === 'AUTH_REQUIRED') {
        const hasCredentials = storedDevice.load() !== null
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
      storedDevice.save(message.deviceId, message.token)
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
        storedDevice.clear()
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

    if ('requestId' in message && !isCurrentRequest(message.requestId)) return

    if (message.type === 'NEEDS_PLATFORM') {
      setPendingChoice({
        requestId: message.requestId,
        query: message.query,
        platforms: message.suggestedPlatforms,
      })
      setOrbState('needs_selection')
      setStatusMessage(`Onde procurar “${message.query}”?`)
      setStatusError(false)
      return
    }

    if (message.type === 'COMMAND_RESULT' || message.type === 'ERROR') {
      setPendingChoice(null)
    }

    if (message.type === 'COMMAND_RESULT') {
      if (message.data.intent === 'SYSTEM_VOLUME') {
        setVolumeLevel(message.data.level)
        setVolumeMuted(message.data.muted)
        // O que foi realmente afetado: o aplicativo ou o Windows inteiro.
        // O fallback precisa ficar visível, não implícito.
        setVolumeScope(message.data.scope)
        setVolumeTarget(message.data.target)
      }
      if (message.data.intent === 'POINTER_CONTROL') {
        cancelFeedback()
        setOrbState('idle')
        setStatusMessage(message.message)
        setStatusError(false)
        return
      }
      if (message.data.intent === 'NAVIGATION') {
        cancelFeedback()
        setOrbState('idle')
        setStatusMessage(message.message)
        setStatusError(false)
        return
      }
      if (message.data.intent === 'KEYBOARD_CONTROL') {
        cancelFeedback()
        setOrbState('idle')
        setStatusMessage(message.message)
        setStatusError(false)
        return
      }
      setOrbState('success')
      setStatusMessage(message.message)
      setStatusError(false)
      scheduleFeedbackReset(2000, () => {
        setOrbState('idle')
        setSelectedPlatform(null)
        setStatusMessage('Computador pronto.')
      })
      return
    }

    if (message.type === 'ERROR') {
      setOrbState('error')
      setStatusMessage(message.message)
      setStatusError(true)
      scheduleFeedbackReset(3000, () => {
        setOrbState('idle')
        setSelectedPlatform(null)
        setStatusMessage('Computador pronto.')
        setStatusError(false)
      })
    }
  }, [
    cancelFeedback,
    hasPendingRequest,
    isCurrentRequest,
    scheduleFeedbackReset,
    storedDevice,
  ])

  const { connectionState, sendMessage } = useWebSocket({ onMessage: handleMessage })

  useEffect(() => {
    if (connectionState !== 'connected') {
      hasSentAuthThisConnection.current = false
      hasLoadedVolumeForScreen.current = false
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

    const credentials = storedDevice.load()
    if (credentials === null) {
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
      payload: credentials,
    })
    if (!accepted) hasSentAuthThisConnection.current = false
  }, [connectionState, sendMessage, storedDevice])

  const controlsDisabled = connectionState !== 'connected'
    || authState !== 'authenticated'
    || serverState !== 'READY'
    || orbState === 'executing'

  const pointerDisabled = connectionState !== 'connected'
    || authState !== 'authenticated'
    || serverState !== 'READY'

  // Só o que torna o teclado realmente indisponível. O comando em voo ficou de
  // fora: incluí-lo desabilitava o input e o iOS fechava o teclado virtual a
  // cada envio. O backend já limita a taxa.
  const keyboardDisabled = connectionState !== 'connected'
    || authState !== 'authenticated'
    || serverState !== 'READY'

  const showOrbPreview = import.meta.env.DEV
    && new URLSearchParams(window.location.search).get('orb-preview') === '1'

  const handlePlatformSelect = (platform: Platform) => {
    if (controlsDisabled) return

    const requestId = beginFeedback()
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
      cancelFeedback()
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

    const requestId = beginFeedback()
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
      cancelFeedback()
      setOrbState('error')
      setStatusMessage('Conexão indisponível. Tente novamente.')
      setStatusError(true)
    }
    return accepted
  }

  const handleMediaAction = (action: MediaAction) => {
    if (controlsDisabled) return

    const requestId = beginFeedback({ kind: 'media', action })
    setOrbState('executing')
    setStatusMessage('Executando controle de mídia...')
    setStatusError(false)

    const accepted = sendMessage({
      protocolVersion: PROTOCOL_VERSION,
      type: action,
      requestId,
    })
    if (!accepted) {
      cancelFeedback()
      setOrbState('error')
      setStatusMessage('Conexão indisponível. Tente novamente.')
      setStatusError(true)
    }
  }

  const handleVolumeAction = useCallback((
    action: VolumeAction,
    value?: number | -5 | 5,
    background = false,
  ) => {
    if (controlsDisabled) return

    const requestId = beginFeedback({ kind: 'volume', action })
    if (!background) setOrbState('executing')
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
      cancelFeedback()
      setOrbState('error')
      setStatusMessage('Conexão indisponível. Tente novamente.')
      setStatusError(true)
    }
  }, [beginFeedback, cancelFeedback, controlsDisabled, sendMessage])

  const handlePointerAction = useCallback((
    action: PointerAction,
    payload?: PointerPayload,
  ) => {
    if (pointerDisabled) return
    const requestId = beginFeedback({ kind: 'pointer', action })
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
      cancelFeedback()
      setStatusMessage('Touchpad desconectado.')
      setStatusError(true)
    }
  }, [beginFeedback, cancelFeedback, pointerDisabled, sendMessage])

  const handleKeyboardText = useCallback((text: string): boolean => {
    if (
      keyboardDisabled
      || !text.trim()
      || text.length > 256
      || containsUnsafeKeyboardCharacter(text)
    ) return false
    const requestId = beginFeedback({ kind: 'keyboard', action: 'KEYBOARD_TEXT' })
    setStatusMessage('Enviando texto...')
    setStatusError(false)
    const accepted = sendMessage({
      protocolVersion: PROTOCOL_VERSION,
      type: 'KEYBOARD_TEXT',
      requestId,
      payload: { text },
    })
    if (!accepted) {
      cancelFeedback()
      setStatusMessage('Teclado remoto desconectado.')
      setStatusError(true)
    }
    return accepted
  }, [beginFeedback, cancelFeedback, keyboardDisabled, sendMessage])

  const handleKeyboardKey = useCallback((key: SafeKey) => {
    if (keyboardDisabled) return
    const requestId = beginFeedback({ kind: 'keyboard', action: 'KEYBOARD_KEY' })
    setStatusMessage('Enviando tecla...')
    setStatusError(false)
    const accepted = sendMessage({
      protocolVersion: PROTOCOL_VERSION,
      type: 'KEYBOARD_KEY',
      requestId,
      payload: { key },
    })
    if (!accepted) {
      cancelFeedback()
      setStatusMessage('Teclado remoto desconectado.')
      setStatusError(true)
    }
  }, [beginFeedback, cancelFeedback, keyboardDisabled, sendMessage])

  // O direcional é o único controle que não espera a resposta anterior: sem
  // isso, segurar a seta enviaria um único comando.
  const navigationDisabled = connectionState !== 'connected'
    || authState !== 'authenticated'
    || serverState !== 'READY'

  const handleChoosePlatform = useCallback((platform: SearchablePlatform) => {
    if (pendingChoice === null || controlsDisabled) return
    const query = pendingChoice.query
    const requestId = beginFeedback()
    setPendingChoice(null)
    setOrbState('executing')
    setStatusMessage('Processando comando...')
    setStatusError(false)

    // Só plataforma e consulta: a URL é montada no backend.
    const accepted = sendMessage({
      protocolVersion: PROTOCOL_VERSION,
      type: 'SEARCH_MEDIA',
      requestId,
      payload: { platform, query },
    })
    if (!accepted) {
      cancelFeedback()
      setOrbState('error')
      setStatusMessage('Conexão indisponível. Tente novamente.')
      setStatusError(true)
    }
  }, [beginFeedback, cancelFeedback, controlsDisabled, pendingChoice, sendMessage])

  const handleCancelChoice = useCallback(() => {
    setPendingChoice(null)
    cancelFeedback()
    setOrbState('idle')
    setStatusMessage('Computador pronto.')
    setStatusError(false)
  }, [cancelFeedback])

  const handleNavigationAction = useCallback((action: NavigationAction) => {
    if (navigationDisabled) return
    const requestId = beginFeedback({ kind: 'navigation', action })
    const accepted = sendMessage({
      protocolVersion: PROTOCOL_VERSION,
      type: action,
      requestId,
    })
    if (!accepted) {
      cancelFeedback()
      setStatusMessage('Navegação indisponível.')
      setStatusError(true)
    }
  }, [beginFeedback, cancelFeedback, navigationDisabled, sendMessage])

  useEffect(() => {
    if (currentScreen !== 'VOLUME' && currentScreen !== 'REMOTE_CONTROL') {
      hasLoadedVolumeForScreen.current = false
      return
    }
    if (
      hasLoadedVolumeForScreen.current
      || connectionState !== 'connected'
      || authState !== 'authenticated'
      || serverState !== 'READY'
    ) return

    hasLoadedVolumeForScreen.current = true
    handleVolumeAction('SYSTEM_VOLUME_GET', undefined, true)
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
                <RemoteOrb state={orbState} quality={orbQuality} />
                {showOrbPreview ? (
                  <>
                    <OrbStatePreview state={orbState} onChange={setOrbState} />
                    <OrbQualityPicker
                      quality={orbQuality}
                      onChange={(next) => {
                        setOrbQuality(next)
                        saveOrbQuality(storedDevice.load()?.deviceId ?? null, next)
                      }}
                    />
                  </>
                ) : null}
              </div>

              <RemoteStatusText message={statusMessage} error={statusError} />
              <AuthenticationStatus
                authState={authState}
                connected={connectionState === 'connected'}
              />

              <div className="input-area">
                {pendingChoice !== null ? (
                  <PlatformChoice
                    query={pendingChoice.query}
                    platforms={pendingChoice.platforms}
                    disabled={controlsDisabled}
                    onChoose={handleChoosePlatform}
                    onCancel={handleCancelChoice}
                  />
                ) : null}

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
              connected={connectionState === 'connected' && authState === 'authenticated'}
              navigationDisabled={navigationDisabled}
              currentAction={currentMediaAction}
              currentNavigationAction={currentNavigationAction}
              currentVolumeAction={currentVolumeAction}
              muted={volumeMuted}
              volumeLevel={volumeLevel}
              statusMessage={statusMessage}
              statusError={statusError}
              onAction={handleMediaAction}
              onNavigationAction={handleNavigationAction}
              onVolumeDelta={(delta) => handleVolumeAction('SYSTEM_VOLUME_DELTA', delta)}
              onToggleMute={() => handleVolumeAction('SYSTEM_MUTE_TOGGLE')}
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
              scope={volumeScope}
              target={volumeTarget}
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
