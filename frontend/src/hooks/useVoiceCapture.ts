import { useCallback, useEffect, useRef, useState } from 'react'

import { apiBaseUrl } from '../features/fawkes-remote/apiUrl'


export type VoiceState =
  | 'idle'
  | 'unsupported'
  | 'requesting'
  | 'recording'
  | 'transcribing'
  | 'error'

interface UseVoiceCaptureOptions {
  /** Credenciais do pareamento: o endpoint de voz exige as mesmas do WebSocket. */
  credentials: { deviceId: string; token: string } | null
  onTranscribed: (text: string) => void
}

/** Um comando de controle remoto é curto; o corte evita upload gigante. */
const MAX_RECORDING_MS = 15000

/**
 * Motivo de o botão poder estar indisponível antes mesmo de tentar.
 *
 * `getUserMedia` só existe em contexto seguro. Aberto pelo IP da rede em
 * `http://`, o Safari do iPhone nem expõe `navigator.mediaDevices` — e sem
 * este aviso o botão pareceria quebrado sem explicação.
 */
export function voiceUnavailableReason(): string | null {
  if (typeof navigator === 'undefined') return 'Gravação indisponível neste ambiente.'
  if (typeof MediaRecorder === 'undefined') {
    return 'Este navegador não grava áudio.'
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    return window.isSecureContext
      ? 'Este navegador não dá acesso ao microfone.'
      // O caminho existe e é curto: sem dizer qual é, a mensagem só informa
      // que não dá, e a pessoa fica sem saber o que fazer a respeito.
      : 'O microfone exige HTTPS. No computador, rode "npm run dev:https" e abra o controle pelo endereço https.'
  }
  return null
}

function pickMimeType(): string | undefined {
  // O iOS grava em mp4/aac e ignora o resto; Chrome e Firefox preferem webm.
  // Deixar o navegador escolher (undefined) é melhor do que forçar um formato
  // que ele aceita no `isTypeSupported` mas grava vazio.
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']
  return candidates.find((type) => MediaRecorder.isTypeSupported?.(type))
}

export function useVoiceCapture({ credentials, onTranscribed }: UseVoiceCaptureOptions) {
  const [state, setState] = useState<VoiceState>('idle')
  const [message, setMessage] = useState('')
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const streamRef = useRef<MediaStream | null>(null)
  const stopTimerRef = useRef<number | null>(null)
  const onTranscribedRef = useRef(onTranscribed)

  useEffect(() => {
    onTranscribedRef.current = onTranscribed
  }, [onTranscribed])

  const releaseStream = useCallback(() => {
    if (stopTimerRef.current !== null) {
      window.clearTimeout(stopTimerRef.current)
      stopTimerRef.current = null
    }
    // Soltar as trilhas é o que apaga o indicador de microfone ativo. Sem isto
    // o navegador segue mostrando que o app está ouvindo.
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    recorderRef.current = null
  }, [])

  useEffect(() => releaseStream, [releaseStream])

  const send = useCallback(async (audio: Blob) => {
    if (credentials === null) {
      setState('error')
      setMessage('Pareie o dispositivo antes de usar a voz.')
      return
    }

    setState('transcribing')
    setMessage('Transcrevendo...')

    const baseUrl = apiBaseUrl()
    const form = new FormData()
    form.append('audio', audio, 'comando.webm')

    try {
      const response = await fetch(`${baseUrl}/voice/transcribe`, {
        method: 'POST',
        headers: {
          'X-Device-Id': credentials.deviceId,
          'X-Device-Token': credentials.token,
        },
        body: form,
      })

      if (!response.ok) {
        const detail = await response.json().catch(() => null)
        setState('error')
        setMessage(
          typeof detail?.detail === 'string'
            ? detail.detail
            : 'Não foi possível transcrever o áudio.',
        )
        return
      }

      const data = await response.json()
      const text = typeof data?.text === 'string' ? data.text.trim() : ''
      if (!text) {
        setState('error')
        setMessage('Não entendi o que foi dito.')
        return
      }

      setState('idle')
      setMessage('')
      onTranscribedRef.current(text)
    } catch {
      setState('error')
      setMessage('O computador não respondeu.')
    }
  }, [credentials])

  const stop = useCallback(() => {
    const recorder = recorderRef.current
    if (recorder && recorder.state !== 'inactive') recorder.stop()
  }, [])

  const start = useCallback(async () => {
    const unavailable = voiceUnavailableReason()
    if (unavailable !== null) {
      setState('unsupported')
      setMessage(unavailable)
      return
    }

    setState('requesting')
    setMessage('Liberando o microfone...')

    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setState('error')
      setMessage('Permissão de microfone negada.')
      return
    }

    streamRef.current = stream
    chunksRef.current = []
    const mimeType = pickMimeType()
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
    recorderRef.current = recorder

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data)
    }
    recorder.onstop = () => {
      const type = recorder.mimeType || mimeType || 'audio/webm'
      const audio = new Blob(chunksRef.current, { type })
      chunksRef.current = []
      releaseStream()
      if (audio.size === 0) {
        setState('error')
        setMessage('Nada foi gravado.')
        return
      }
      void send(audio)
    }

    recorder.start()
    setState('recording')
    setMessage('Ouvindo...')
    // Rede de segurança: se a tela travar ou o toque de parar se perder, a
    // gravação não fica aberta consumindo microfone para sempre.
    stopTimerRef.current = window.setTimeout(stop, MAX_RECORDING_MS)
  }, [releaseStream, send, stop])

  const toggle = useCallback(() => {
    if (state === 'recording') {
      stop()
      return
    }
    if (state === 'requesting' || state === 'transcribing') return
    void start()
  }, [start, state, stop])

  const reset = useCallback(() => {
    setState('idle')
    setMessage('')
  }, [])

  return { state, message, toggle, reset }
}
