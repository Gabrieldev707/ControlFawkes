import {
  ArrowLeft,
  Cpu,
  Mic,
  MonitorSmartphone,
  ShieldCheck,
  Hand,
  Sparkles,
  Trash2,
  Wifi,
} from 'lucide-react'
import { useState } from 'react'

import {
  ORB_QUALITY_LEVELS,
  type OrbQuality,
} from '../../components/fawkes-remote/orbQuality'
import {
  GESTURE_SENSITIVITIES,
  type GestureSensitivity,
} from '../../features/fawkes-remote/touchpadGesture'
import { CatalogKeyCard } from '../../components/fawkes-remote/CatalogKeyCard'
import type { ConnectionState } from '../../features/fawkes-remote/types'
import type { VoiceState } from '../../hooks/useVoiceCapture'


interface SettingsScreenProps {
  connectionState: ConnectionState
  deviceId: string | null
  orbQuality: OrbQuality
  voiceState: VoiceState
  voiceMessage: string
  gestureSensitivity: GestureSensitivity
  credentials?: { deviceId: string; token: string } | null
  onChangeOrbQuality: (quality: OrbQuality) => void
  onChangeGestureSensitivity: (sensitivity: GestureSensitivity) => void
  onForgetDevice: () => void
  onBack: () => void
}

const QUALITY_LABELS: Record<OrbQuality, { name: string; hint: string }> = {
  LOW: { name: 'Leve', hint: 'Menos partículas, mais bateria' },
  BALANCED: { name: 'Equilibrado', hint: 'Padrão, nítido em tela retina' },
  HIGH: { name: 'Alta', hint: 'Aparelho recente ou tela grande' },
}

// O eixo é um só porque só existem dois jeitos de errar: a seta dispara
// quando você queria mirar o cursor, ou não dispara quando você queria navegar.
const GESTURE_LABELS: Record<GestureSensitivity, { name: string; hint: string }> = {
  ALTA: { name: 'Alta', hint: 'Deslize curto já navega' },
  PADRAO: { name: 'Padrão', hint: 'Equilíbrio entre navegar e mirar' },
  BAIXA: { name: 'Baixa', hint: 'Exige deslize longo; cursor mais livre' },
}

const CONNECTION_LABELS: Record<ConnectionState, string> = {
  connected: 'Conectado',
  connecting: 'Conectando',
  reconnecting: 'Reconectando',
  disconnected: 'Desconectado',
  error: 'Falha na conexão',
}

function voiceSummary(state: VoiceState, message: string): string {
  if (state === 'unsupported') return message || 'Indisponível neste navegador'
  if (state === 'error' && message) return message
  return 'Whisper rodando no seu computador'
}

export function SettingsScreen({
  connectionState,
  deviceId,
  orbQuality,
  voiceState,
  voiceMessage,
  gestureSensitivity,
  credentials = null,
  onChangeOrbQuality,
  onChangeGestureSensitivity,
  onForgetDevice,
  onBack,
}: SettingsScreenProps) {
  // Desparear apaga o acesso deste aparelho: exige um segundo toque, porque
  // recuperar significa voltar ao computador para ler o PIN de novo.
  const [confirmingForget, setConfirmingForget] = useState(false)

  return (
    <main className="remote-screen settings-screen" aria-labelledby="settings-screen-title">
      <button type="button" className="remote-screen__back" aria-label="Voltar" onClick={onBack}>
        <ArrowLeft size={18} aria-hidden="true" />
        Voltar
      </button>

      <div className="settings-screen__heading">
        <p className="remote-screen__eyebrow">ControlFawkes</p>
        <h2 id="settings-screen-title">Ajustes</h2>
      </div>

      <section className="settings-card" aria-labelledby="settings-status-title">
        <h3 id="settings-status-title" className="settings-card__title">
          <Wifi size={15} aria-hidden="true" />
          Conexão
        </h3>
        <dl className="settings-rows">
          <div className="settings-row">
            <dt>Estado</dt>
            <dd data-state={connectionState}>{CONNECTION_LABELS[connectionState]}</dd>
          </div>
          <div className="settings-row">
            <dt>Servidor</dt>
            <dd>{window.location.hostname}</dd>
          </div>
        </dl>
      </section>

      <section className="settings-card" aria-labelledby="settings-device-title">
        <h3 id="settings-device-title" className="settings-card__title">
          <MonitorSmartphone size={15} aria-hidden="true" />
          Este aparelho
        </h3>
        <dl className="settings-rows">
          <div className="settings-row">
            <dt>Identificador</dt>
            {/* Só o prefixo: o id inteiro não cabe e não serve para nada aqui. */}
            <dd className="settings-row__mono">
              {deviceId === null ? 'Não pareado' : `${deviceId.slice(0, 12)}…`}
            </dd>
          </div>
        </dl>

        {confirmingForget ? (
          <div className="settings-confirm" role="group" aria-label="Confirmar despareamento">
            <p>Vai precisar do PIN do computador para voltar.</p>
            <div>
              <button
                type="button"
                className="settings-confirm__cancel"
                onClick={() => setConfirmingForget(false)}
              >
                Cancelar
              </button>
              <button
                type="button"
                className="settings-danger"
                onClick={() => {
                  setConfirmingForget(false)
                  onForgetDevice()
                }}
              >
                Desparear agora
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            className="settings-danger"
            disabled={deviceId === null}
            onClick={() => setConfirmingForget(true)}
          >
            <Trash2 size={15} aria-hidden="true" />
            Desparear este aparelho
          </button>
        )}
      </section>

      <section className="settings-card" aria-labelledby="settings-orb-title">
        <h3 id="settings-orb-title" className="settings-card__title">
          <Sparkles size={15} aria-hidden="true" />
          Qualidade do orb
        </h3>
        <div className="settings-choices" role="radiogroup" aria-labelledby="settings-orb-title">
          {ORB_QUALITY_LEVELS.map((quality) => {
            const { name, hint } = QUALITY_LABELS[quality]
            const active = quality === orbQuality
            return (
              <button
                key={quality}
                type="button"
                role="radio"
                aria-checked={active}
                className={`settings-choice${active ? ' settings-choice--active' : ''}`}
                onClick={() => onChangeOrbQuality(quality)}
              >
                <strong>{name}</strong>
                <span>{hint}</span>
              </button>
            )
          })}
        </div>
      </section>

      <section className="settings-card" aria-labelledby="settings-gesture-title">
        <h3 id="settings-gesture-title" className="settings-card__title">
          <Hand size={15} aria-hidden="true" />
          Sensibilidade do gesto
        </h3>
        <p className="settings-card__text">
          Quanto de deslize é preciso para virar seta, na tela de Controle.
        </p>
        <div className="settings-choices" role="radiogroup" aria-labelledby="settings-gesture-title">
          {GESTURE_SENSITIVITIES.map((sensitivity) => {
            const { name, hint } = GESTURE_LABELS[sensitivity]
            const active = sensitivity === gestureSensitivity
            return (
              <button
                key={sensitivity}
                type="button"
                role="radio"
                aria-checked={active}
                className={`settings-choice${active ? ' settings-choice--active' : ''}`}
                onClick={() => onChangeGestureSensitivity(sensitivity)}
              >
                <strong>{name}</strong>
                <span>{hint}</span>
              </button>
            )
          })}
        </div>
      </section>

      <section className="settings-card" aria-labelledby="settings-voice-title">
        <h3 id="settings-voice-title" className="settings-card__title">
          <Mic size={15} aria-hidden="true" />
          Comando por voz
        </h3>
        <p className="settings-card__text" data-warning={voiceState === 'unsupported'}>
          {voiceSummary(voiceState, voiceMessage)}
        </p>
      </section>

      <CatalogKeyCard credentials={credentials} />

      <section className="settings-card" aria-labelledby="settings-privacy-title">
        <h3 id="settings-privacy-title" className="settings-card__title">
          <ShieldCheck size={15} aria-hidden="true" />
          Privacidade
        </h3>
        <ul className="settings-list">
          <li>O áudio da voz é transcrito no seu computador e descartado em seguida.</li>
          <li>O servidor guarda só o hash do token, nunca o token em si.</li>
          <li>Nada do que você digita ou fala é enviado para fora da rede local.</li>
        </ul>
      </section>

      <p className="settings-screen__footer">
        <Cpu size={13} aria-hidden="true" />
        Tudo roda local. Sem nuvem, sem conta, sem histórico.
      </p>
    </main>
  )
}
