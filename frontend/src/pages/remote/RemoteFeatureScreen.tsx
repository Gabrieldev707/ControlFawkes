import {
  ArrowLeft,
  Keyboard,
  MousePointer2,
  Settings,
  Volume2,
} from 'lucide-react'

import type { NavigableScreen } from '../../state/currentScreen'


type FeatureScreen = Exclude<NavigableScreen, 'HOME' | 'PLATFORMS' | 'REMOTE_CONTROL'>

interface RemoteFeatureScreenProps {
  screen: FeatureScreen
  onBack: () => void
}

const SCREEN_CONTENT = {
  TOUCHPAD: {
    title: 'Touchpad',
    description: 'A superfície de ponteiro será ativada depois da validação dos controles.',
    icon: MousePointer2,
  },
  KEYBOARD: {
    title: 'Teclado',
    description: 'A entrada remota de texto será adicionada com validação e limites próprios.',
    icon: Keyboard,
  },
  VOLUME: {
    title: 'Volume',
    description: 'O volume do Windows será conectado por um adaptador isolado e testável.',
    icon: Volume2,
  },
  SETTINGS: {
    title: 'Configurações',
    description: 'Preferências locais e informações do dispositivo ficarão organizadas aqui.',
    icon: Settings,
  },
} as const satisfies Record<FeatureScreen, {
  title: string
  description: string
  icon: typeof Keyboard
}>

export function RemoteFeatureScreen({ screen, onBack }: RemoteFeatureScreenProps) {
  const content = SCREEN_CONTENT[screen]
  const Icon = content.icon

  return (
    <main className="remote-screen" aria-labelledby="remote-screen-title">
      <button
        type="button"
        className="remote-screen__back"
        aria-label="Voltar"
        onClick={onBack}
      >
        <ArrowLeft size={18} aria-hidden="true" />
        Voltar
      </button>

      <div className="remote-screen__content">
        <span className="remote-screen__icon" aria-hidden="true">
          <Icon size={34} strokeWidth={1.6} />
        </span>
        <p className="remote-screen__eyebrow">ControlFawkes</p>
        <h2 id="remote-screen-title">{content.title}</h2>
        <p>{content.description}</p>
        <span className="remote-screen__status">Próxima etapa</span>
      </div>
    </main>
  )
}
