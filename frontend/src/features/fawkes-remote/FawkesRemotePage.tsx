import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'

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
  NowPlayingSession,
  ServerMessage,
  TitleAvailability,
  ServerState,
  VolumeAction,
} from './types'
import { PROTOCOL_VERSION, SEARCHABLE_PLATFORMS } from './types'
import { useWebSocket } from '../../hooks/useWebSocket'
import { useRemoteNavigation } from '../../hooks/useRemoteNavigation'
import { useCommandFeedback } from '../../hooks/useCommandFeedback'
import { useStoredDevice } from '../../hooks/useStoredDevice'
import { useVoiceCapture } from '../../hooks/useVoiceCapture'
import { generateRequestId } from '../../utils/uuid'
import { HomeProfiles } from '../../components/fawkes-remote/HomeProfiles'
import { HomeShortcuts } from '../../components/navigation/HomeShortcuts'
import { RemoteNavigation } from '../../components/navigation/RemoteNavigation'
import { SettingsScreen } from '../../pages/remote/SettingsScreen'
import { PlatformsScreen } from '../../pages/remote/PlatformsScreen'
import { ProfileScreen } from '../../pages/remote/ProfileScreen'
import { RemoteControlScreen } from '../../pages/remote/RemoteControlScreen'
import { VolumeScreen } from '../../pages/remote/VolumeScreen'
import { TouchpadScreen } from '../../pages/remote/TouchpadScreen'
import { KeyboardScreen } from '../../pages/remote/KeyboardScreen'
import { PlatformChoice } from '../../components/fawkes-remote/PlatformChoice'
import { OrbQualityPicker } from '../../components/fawkes-remote/OrbQualityPicker'
import type { OrbQuality } from '../../components/fawkes-remote/orbQuality'
import { loadOrbQuality, saveOrbQuality } from './orbPreferences'
import { loadGestureSensitivity, saveGestureSensitivity } from './gesturePreferences'
import { gestureLimitsFor, type GestureSensitivity } from './touchpadGesture'
import { apiBaseUrl } from './apiUrl'
import {
  AuthenticationStatus,
  ConnectionStatus,
  FawkesMark,

  PairingScreen,
  OrbStatePreview,
  PendingSearchHandoff,
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
  const [gestureSensitivity, setGestureSensitivity] = useState<GestureSensitivity>(
    () => loadGestureSensitivity(storedDevice.load()?.deviceId ?? null),
  )
  // Referência estável: montar o objeto a cada render fazia o deck achar
  // que a sensibilidade tinha mudado o tempo todo.
  const gestureLimits = useMemo(
    () => gestureLimitsFor(gestureSensitivity),
    [gestureSensitivity],
  )
  const [pendingChoice, setPendingChoice] = useState<{
    requestId: string
    query: string
    platforms: SearchablePlatform[]
    openOnly: Platform[]
    availability: TitleAvailability | null
    alternative: TitleAvailability | null
    opcoes: TitleAvailability[]
  } | null>(null)
  const [volumeLevel, setVolumeLevel] = useState<number | null>(null)
  const [volumeMuted, setVolumeMuted] = useState(false)
  // Consulta que ficou pendente por ter caído numa plataforma sem busca por
  // URL: segue para o teclado remoto em vez de se perder.
  const [pendingSearchText, setPendingSearchText] = useState<string | null>(null)
  // O que o computador está tocando. Chega empurrado, sem o celular pedir.
  const [nowPlaying, setNowPlaying] = useState<NowPlayingSession | null>(null)
  const { currentScreen, navigate, goBack } = useRemoteNavigation()

  const {
    begin: beginFeedback,
    cancel: cancelFeedback,
    scheduleReset: scheduleFeedbackReset,
    isCurrent: isCurrentRequest,
    hasPending: hasPendingRequest,
    currentMediaAction,
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

    if (message.type === 'NOW_PLAYING') {
      setNowPlaying(message.session)
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
        openOnly: message.openOnlyPlatforms ?? [],
        availability: message.availability ?? null,
        alternative: message.availabilityAlternative ?? null,
        opcoes: message.availabilityOptions ?? [],
      })
      setOrbState('needs_selection')
      const encontrado = message.availability
      setStatusMessage(
        encontrado && encontrado.platforms.length > 0
          ? `${encontrado.title} está disponível.`
          : `Onde procurar “${message.query}”?`,
      )
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
        // Volume é controle direto, como ponteiro e teclado: não entra no ciclo
        // "executando → sucesso → reset". Esse ciclo mantinha a tela ocupada
        // por 2s a cada ajuste, e arrastar o slider virava uma sequência de
        // travadas. O texto de status já é o retorno.
        cancelFeedback()
        setOrbState('idle')
        setStatusMessage(message.message)
        setStatusError(false)
        return
      }
      if (message.data.intent === 'SCREEN_CONTROL') {
        // Mesmo tratamento do ponteiro: retorno imediato, sem prender a tela.
        cancelFeedback()
        setOrbState('idle')
        setStatusMessage(message.message)
        setStatusError(false)
        return
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
      if (message.data.intent === 'MEDIA_CONTROL') {
        // Play/pause é controle direto, como o direcional: não pode entrar no
        // ciclo "executando → sucesso → 2s". Esse ciclo deixava a tela ocupada
        // depois de cada toque, e um segundo toque logo em seguida — pausar e
        // voltar, que é o uso normal — era simplesmente descartado.
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

  const {
    connectionState,
    sendMessage,
    reconnect,
    nextRetryAt,
  } = useWebSocket({ onMessage: handleMessage })

  useEffect(() => {
    if (connectionState !== 'connected') {
      hasSentAuthThisConnection.current = false
      hasLoadedVolumeForScreen.current = false
      setNowPlaying(null)
      setServerState(null)
      setStatusMessage(
        connectionState === 'connecting'
          ? 'Conectando ao computador...'
          : connectionState === 'reconnecting'
            ? 'Reconectando...'
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

  /**
   * As credenciais com identidade estável.
   *
   * `storedDevice.load()` lê o disco e devolve um objeto novo a cada chamada.
   * Passar isso direto como prop dava identidade nova a cada render, e todo
   * `useEffect` que dependia das credenciais disparava de novo — para sempre.
   *
   * Medido no servidor: `GET /screen/profiles` dezenas de vezes por segundo com
   * ninguém tocando em nada. Os destaques e a capa da mídia estavam no mesmo
   * laço, só que sem barulho visível.
   *
   * Reler quando o pareamento muda de estado é suficiente: é o único momento em
   * que o par deviceId/token deixa de valer.
   */
  const credenciaisEstaveis = useMemo(
    // Antes de autenticar não há credencial que preste: os recursos protegidos
    // responderiam 401. E é a mudança de `authState` que diz quando vale a pena
    // reler o disco — no resto do tempo a identidade fica parada, que é o
    // ponto.
    () => (authState === 'authenticated' ? storedDevice.load() : null),
    [authState, storedDevice],
  )

  const controlsDisabled = connectionState !== 'connected'
    || authState !== 'authenticated'
    || serverState !== 'READY'
    || orbState === 'executing'

  // Mídia depende da conexão, não de haver outro comando em voo: play/pause
  // repetido é uso normal e não pode ser descartado.
  const mediaDisabled = connectionState !== 'connected'
    || authState !== 'authenticated'
    || serverState !== 'READY'

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

  /**
   * Retomar um título do histórico.
   *
   * Não existe link para o minuto exato: o controle abre o serviço, não uma
   * URL com timestamp. Então retomar é procurar o título de novo — o que, na
   * prática, cai na tela onde o próprio serviço oferece "continuar assistindo".
   */
  const handleResume = useCallback((_platform: Platform | null, title: string) => {
    if (controlsDisabled) return
    const requestId = beginFeedback()
    setStatusMessage(`Procurando ${title}...`)
    setStatusError(false)
    // Volta para a tela inicial antes de mandar: é lá que a resposta aparece.
    //
    // Medido clicando de verdade no cartão: o comando ia, o servidor achava o
    // título e respondia com onde assistir — mas a escolha de plataforma só é
    // desenhada na tela inicial. Quem tocou em "continuar assistindo" ficava no
    // Perfil vendo uma frase solta ("A Casa do Dragão está disponível.") e nada
    // acontecia. O toque funcionava; a resposta é que não tinha onde caber.
    navigate('HOME')
    // Vai pelo comando de texto, o mesmo caminho da busca da tela inicial: ele
    // já sabe consultar o catálogo, abrir o serviço certo e lidar com Max e
    // Disney+, que não aceitam busca por URL. Mandar direto para a plataforma
    // deixaria esses dois de fora.
    if (!sendMessage({
      protocolVersion: PROTOCOL_VERSION,
      type: 'TEXT_COMMAND',
      requestId,
      payload: { query: title },
    })) {
      cancelFeedback()
      setStatusMessage('Conexão indisponível. Tente novamente.')
      setStatusError(true)
    }
  }, [beginFeedback, cancelFeedback, controlsDisabled, navigate, sendMessage])

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

  // A fala vira exatamente o mesmo comando de texto que o campo digitado. Não
  // existe caminho separado: o que a voz produz passa pelo mesmo parser, pelas
  // mesmas validações e pelos mesmos limites.
  const voice = useVoiceCapture({
    credentials: storedDevice.load(),
    onTranscribed: (text) => {
      setStatusMessage(`“${text}”`)
      handleTextSubmit(text)
    },
  })

  const { reset: resetVoice } = voice

  useEffect(() => {
    if (voice.state === 'recording') {
      setOrbState('listening')
      return
    }
    if (voice.state === 'transcribing') {
      setOrbState('transcribing')
      return
    }
    if (voice.state === 'error' || voice.state === 'unsupported') {
      setOrbState('error')
      setStatusMessage(voice.message)
      setStatusError(true)
      // Sem esta volta, um "microfone indisponível" deixava o orb vermelho e o
      // status em erro para sempre, mesmo depois de a pessoa usar o controle
      // normalmente por outro caminho.
      const timer = window.setTimeout(resetVoice, 4000)
      return () => window.clearTimeout(timer)
    }
    // Só desfaz o que a própria voz pintou: um comando disparado pela
    // transcrição já colocou o orb em "executando" e não pode ser interrompido.
    setOrbState((current) => (
      current === 'listening' || current === 'transcribing' || current === 'error'
        ? 'idle'
        : current
    ))
    setStatusError(false)
  }, [voice.state, voice.message, resetVoice])

  const handleMediaAction = (action: MediaAction) => {
    // `mediaDisabled` e não `controlsDisabled`: este último inclui "comando em
    // voo", e era ele que descartava o segundo toque no play — pausar e voltar
    // logo em seguida é o uso normal, não um acidente a ser filtrado.
    if (mediaDisabled) return

    const requestId = beginFeedback({ kind: 'media', action })
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

  // O volume não passa por `controlsDisabled`: aquele estado inclui "comando em
  // voo", e era ele que engolia a leitura inicial ao entrar na tela. O pedido
  // era descartado em silêncio, o nível ficava em "—" e todos os controles
  // apareciam desabilitados. Aqui basta a conexão estar pronta.
  const volumeDisabled = connectionState !== 'connected'
    || authState !== 'authenticated'
    || serverState !== 'READY'

  const handleVolumeAction = useCallback((
    action: VolumeAction,
    value?: number | -5 | 5,
    background = false,
  ): boolean => {
    if (volumeDisabled) return false

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
    return accepted
  }, [beginFeedback, cancelFeedback, sendMessage, volumeDisabled])

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
    } else {
      // Digitado, deixa de estar pendente: senão o aviso voltaria a aparecer.
      setPendingSearchText(null)
    }
    return accepted
  }, [beginFeedback, cancelFeedback, keyboardDisabled, sendMessage])

  // Toque na foto da tela e escolha de perfil seguem o caminho do ponteiro:
  // ação direta, sem o ciclo "executando -> sucesso" que prenderia a tela por
  // dois segundos a cada toque.
  const handleScreenTap = useCallback((platform: Platform, x: number, y: number) => {
    if (controlsDisabled) return
    const requestId = beginFeedback()
    setStatusMessage('Tocando na tela...')
    setStatusError(false)
    if (!sendMessage({
      protocolVersion: PROTOCOL_VERSION,
      type: 'SCREEN_TAP',
      requestId,
      payload: { platform, x, y },
    })) {
      cancelFeedback()
      setStatusMessage('Conexão indisponível. Tente novamente.')
      setStatusError(true)
    }
  }, [beginFeedback, cancelFeedback, controlsDisabled, sendMessage])

  const handleSelectProfile = useCallback((platform: Platform, profileId: string) => {
    if (controlsDisabled) return
    const requestId = beginFeedback()
    setStatusMessage('Entrando no perfil...')
    setStatusError(false)
    if (!sendMessage({
      protocolVersion: PROTOCOL_VERSION,
      type: 'PROFILE_SELECT',
      requestId,
      payload: { platform, profileId },
    })) {
      cancelFeedback()
      setStatusMessage('Conexão indisponível. Tente novamente.')
      setStatusError(true)
    }
  }, [beginFeedback, cancelFeedback, controlsDisabled, sendMessage])

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

  // Max e Disney+ não aceitam a consulta pela URL. Em vez de sumirem da lista,
  // abrem a plataforma e a consulta fica guardada: o próximo passo vira digitar
  // o título lá dentro pelo teclado remoto, que é como a pessoa faria à mão.
  const handleOpenPlatformForQuery = useCallback((platform: Platform) => {
    if (pendingChoice === null || controlsDisabled) return
    const query = pendingChoice.query
    const requestId = beginFeedback()
    setPendingChoice(null)
    setSelectedPlatform(platform)
    setOrbState('executing')
    setStatusMessage('Abrindo a plataforma...')
    setStatusError(false)

    const accepted = sendMessage({
      protocolVersion: PROTOCOL_VERSION,
      type: 'PLATFORM_SELECTED',
      requestId,
      // Veio de uma consulta: cai na tela de busca da plataforma, para o
      // texto poder ser digitado sem procurar a lupa antes.
      payload: { platform, openSearch: true },
    })
    if (accepted) {
      setPendingSearchText(query)
    } else {
      cancelFeedback()
      setSelectedPlatform(null)
      setOrbState('error')
      setStatusMessage('Conexão indisponível. Tente novamente.')
      setStatusError(true)
    }
  }, [beginFeedback, cancelFeedback, controlsDisabled, pendingChoice, sendMessage])

  // Capa tocada na tela de plataformas: já sabemos o título e o serviço, então
  // não há o que perguntar. Vai direto para a busca de lá — e onde não há busca
  // por URL, abre na tela de busca com o título pronto para digitar.
  const handlePickHighlight = useCallback((platform: Platform, title: string) => {
    if (controlsDisabled) return
    const requestId = beginFeedback()
    setOrbState('executing')
    setStatusMessage(`Abrindo “${title}”...`)
    setStatusError(false)

    const buscavel = (SEARCHABLE_PLATFORMS as readonly Platform[]).includes(platform)
    const accepted = buscavel
      ? sendMessage({
          protocolVersion: PROTOCOL_VERSION,
          type: 'SEARCH_MEDIA',
          requestId,
          payload: { platform: platform as SearchablePlatform, query: title },
        })
      : sendMessage({
          protocolVersion: PROTOCOL_VERSION,
          type: 'PLATFORM_SELECTED',
          requestId,
          payload: { platform, openSearch: true },
        })

    if (!accepted) {
      cancelFeedback()
      setOrbState('error')
      setStatusMessage('Conexão indisponível. Tente novamente.')
      setStatusError(true)
      return
    }
    if (!buscavel) setPendingSearchText(title)
  }, [beginFeedback, cancelFeedback, controlsDisabled, sendMessage])

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

  // Trocar de aplicativo troca o alvo do volume — o que era "Chrome a 43%"
  // vira "Spotify a 80%". Sem reperguntar, o controle segue mostrando o número
  // do alvo anterior, que é a forma mais silenciosa de mentir.
  const aplicativoTocando = nowPlaying?.app ?? null
  useEffect(() => {
    hasLoadedVolumeForScreen.current = false
  }, [aplicativoTocando])

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

    // Só marca como carregado se o pedido realmente saiu. Marcar antes fazia a
    // tela desistir para sempre quando o envio era recusado.
    hasLoadedVolumeForScreen.current = handleVolumeAction(
      'SYSTEM_VOLUME_GET',
      undefined,
      true,
    )
  }, [currentScreen, connectionState, authState, serverState, handleVolumeAction])

  const handleForgetDevice = useCallback(() => {
    storedDevice.clear()
    setAuthState('pairing_required')
    setPairingMessage('Aparelho desconectado. Use o PIN do computador para parear de novo.')
    setStatusMessage('Autenticação necessária.')
    setStatusError(false)
    // Volta o socket ao estado de quem nunca autenticou: sem isto a sessão
    // continuaria valendo no servidor até a conexão cair.
    hasSentAuthThisConnection.current = false
    reconnect()
  }, [reconnect, storedDevice])

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
        <FawkesMark />
        <ConnectionStatus state={connectionState} nextRetryAt={nextRetryAt} />
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
                    // Escolha nova zera a alternância filme/série da anterior.
                    key={pendingChoice.requestId}
                    query={pendingChoice.query}
                    platforms={pendingChoice.platforms}
                    openOnlyPlatforms={pendingChoice.openOnly}
                    availability={pendingChoice.availability}
                    availabilityAlternative={pendingChoice.alternative}
                    availabilityOptions={pendingChoice.opcoes}
                    disabled={controlsDisabled}
                    onChoose={handleChoosePlatform}
                    onOpenPlatform={handleOpenPlatformForQuery}
                    onCancel={handleCancelChoice}
                  />
                ) : null}

                {pendingSearchText !== null ? (
                  <PendingSearchHandoff
                    query={pendingSearchText}
                    // Controle e não Teclado: lá a mesma tela clica no campo
                    // (pela superfície) e digita. No Teclado faltaria o clique.
                    onOpenKeyboard={() => navigate('REMOTE_CONTROL')}
                    onDismiss={() => setPendingSearchText(null)}
                  />
                ) : null}

                <PlatformGrid
                  selectedPlatform={selectedPlatform}
                  disabled={controlsDisabled}
                  onSelect={handlePlatformSelect}
                />

                <HomeProfiles
                  // A escolha explícita vence o que está tocando: o título da
                  // janela muda de aba e fazia a seção trocar de serviço sozinha
                  // — o perfil foi salvo no Max e pedido na Netflix.
                  platform={selectedPlatform ?? nowPlaying?.platform ?? null}
                  credentials={credenciaisEstaveis}
                  disabled={controlsDisabled}
                  onTap={handleScreenTap}
                  onSelectProfile={handleSelectProfile}
                />

                <div className="main-controls">
                  <TextInput
                    disabled={controlsDisabled}
                    executing={orbState === 'executing'}
                    onSubmit={handleTextSubmit}
                  />
                  <VoiceButton
                    state={voice.state}
                    disabled={controlsDisabled && voice.state !== 'unsupported'}
                    onToggle={voice.toggle}
                  />
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
              muted={volumeMuted}
              volumeLevel={volumeLevel}
              volumeTarget={volumeScope === 'LOCAL' ? volumeTarget : null}
              statusMessage={statusMessage}
              statusError={statusError}
              nowPlaying={nowPlaying}
              apiBaseUrl={apiBaseUrl()}
              credentials={credenciaisEstaveis}
              gestureLimits={gestureLimits}
              onAction={handleMediaAction}
              onNavigationAction={handleNavigationAction}
              onPointerAction={handlePointerAction}
              onKey={handleKeyboardKey}
              pendingSearchText={pendingSearchText}
              onText={handleKeyboardText}
              onSetVolume={(nivel) => handleVolumeAction('SYSTEM_VOLUME_SET', nivel)}
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
              credentials={credenciaisEstaveis}
              onSelect={handlePlatformSelect}
              onPickTitle={handlePickHighlight}
              onBack={goBack}
            />
          ) : currentScreen === 'PROFILE' ? (
            <ProfileScreen
              disabled={controlsDisabled}
              statusMessage={statusMessage}
              statusError={statusError}
              credentials={credenciaisEstaveis}
              /* Recarrega quando o que está tocando muda — OU quando o
                 servidor escreve no histórico.

                 Trocar de obra é UM dos momentos em que o histórico muda, e
                 era o único que esta tela enxergava. Esperar o ciclo de um
                 minuto fazia a pessoa trocar de série e ver a anterior —
                 medido em 26/08/2026: três minutos até a tela admitir a troca,
                 e só depois de recarregar a página na mão.

                 Só que ele NÃO é o único, e o caso que faltava é o mais comum
                 de todos: começar a assistir. A obra entra no histórico aos 90
                 segundos, e até lá o título já era o mesmo — então a chave não
                 mudava e sobrava o relógio. Medido no mesmo dia, com Gavião
                 Arqueiro: a linha estava no disco às 15:16 e a tela ainda não
                 a mostrava.

                 `historyRevision` é um contador que o servidor incrementa a
                 cada gravação bem-sucedida. Com ele a tela recarrega UMA vez,
                 no instante certo, em vez de perguntar de minuto em minuto se
                 mudou alguma coisa. */
              recarregarQuando={
                // `null` continua querendo dizer "não recarregar": é assim que
                // `ProfileScreen` distingue "nada tocando" de uma chave nova, e
                // uma string sempre presente dispararia um carregamento a mais
                // toda vez que a tela montasse.
                nowPlaying === null
                  ? null
                  : `${nowPlaying.title}|${nowPlaying.historyRevision ?? ''}`
              }
              onResume={handleResume}
              onBack={goBack}
            />
          ) : currentScreen === 'VOLUME' ? (
            <VolumeScreen
              disabled={volumeDisabled}
              loading={volumeLevel === null}
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
              initialText={pendingSearchText}
              onText={(text) => {
                const sent = handleKeyboardText(text)
                // A consulta cumpriu o papel: não volta a aparecer na home.
                if (sent) setPendingSearchText(null)
                return sent
              }}
              onKey={handleKeyboardKey}
              onBack={goBack}
            />
          ) : (
            <SettingsScreen
              connectionState={connectionState}
              deviceId={storedDevice.load()?.deviceId ?? null}
              orbQuality={orbQuality}
              voiceState={voice.state}
              voiceMessage={voice.message}
              gestureSensitivity={gestureSensitivity}
              credentials={credenciaisEstaveis}
              onChangeGestureSensitivity={(next) => {
                setGestureSensitivity(next)
                saveGestureSensitivity(storedDevice.load()?.deviceId ?? null, next)
              }}
              onChangeOrbQuality={(next) => {
                setOrbQuality(next)
                saveOrbQuality(storedDevice.load()?.deviceId ?? null, next)
              }}
              onForgetDevice={handleForgetDevice}
              onBack={goBack}
            />
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
