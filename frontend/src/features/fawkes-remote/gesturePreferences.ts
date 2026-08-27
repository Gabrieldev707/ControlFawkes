import {
  DEFAULT_GESTURE_SENSITIVITY,
  isGestureSensitivity,
  type GestureSensitivity,
} from './touchpadGesture'


/**
 * Sensibilidade do gesto, guardada por dispositivo.
 *
 * Por dispositivo e não global: o polegar de cada um é diferente, e o mesmo
 * navegador pareado como outro aparelho não deve herdar a escolha anterior.
 */
const LEGACY_KEY = 'controlfawkes.gestureSensitivity'

function keyFor(deviceId: string | null): string {
  return deviceId ? `controlfawkes.gestureSensitivity.${deviceId}` : LEGACY_KEY
}

export function loadGestureSensitivity(deviceId: string | null): GestureSensitivity {
  try {
    const stored = localStorage.getItem(keyFor(deviceId))
    return isGestureSensitivity(stored) ? stored : DEFAULT_GESTURE_SENSITIVITY
  } catch {
    // Safari em navegação privada pode recusar o storage: cair no padrão é
    // melhor do que quebrar a tela.
    return DEFAULT_GESTURE_SENSITIVITY
  }
}

export function saveGestureSensitivity(
  deviceId: string | null,
  sensitivity: GestureSensitivity,
): void {
  try {
    localStorage.setItem(keyFor(deviceId), sensitivity)
  } catch {
    // Preferência de conforto não vale derrubar a interface.
  }
}
