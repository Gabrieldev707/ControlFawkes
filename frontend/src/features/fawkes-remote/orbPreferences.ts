import {
  DEFAULT_ORB_QUALITY,
  isOrbQuality,
  type OrbQuality,
} from '../../components/fawkes-remote/orbQuality'


/**
 * Preferência visual do orb, guardada por dispositivo.
 *
 * A chave leva o deviceId para que o mesmo navegador, pareado como outro
 * dispositivo, não herde a escolha anterior.
 */
const LEGACY_KEY = 'controlfawkes.orbQuality'

function keyFor(deviceId: string | null): string {
  return deviceId ? `controlfawkes.orbQuality.${deviceId}` : LEGACY_KEY
}

export function loadOrbQuality(deviceId: string | null): OrbQuality {
  try {
    const stored = localStorage.getItem(keyFor(deviceId))
    return isOrbQuality(stored) ? stored : DEFAULT_ORB_QUALITY
  } catch {
    // Safari em navegação privada pode recusar o storage: cair no padrão é
    // melhor do que quebrar a tela.
    return DEFAULT_ORB_QUALITY
  }
}

export function saveOrbQuality(deviceId: string | null, quality: OrbQuality): void {
  try {
    localStorage.setItem(keyFor(deviceId), quality)
  } catch {
    // Preferência visual não vale derrubar a interface.
  }
}
