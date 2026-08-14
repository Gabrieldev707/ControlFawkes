import { useCallback, useMemo } from 'react'


const DEVICE_ID_KEY = 'controlfawkes.deviceId'
const TOKEN_KEY = 'controlfawkes.token'

export interface StoredDevice {
  deviceId: string
  token: string
}

export function useStoredDevice() {
  /**
   * Devolve um objeto novo a cada chamada, de propósito: lê o disco na hora.
   *
   * Cuidado ao usar o resultado como prop ou como dependência de efeito — a
   * identidade nova a cada render faz o efeito disparar para sempre. Para esse
   * caso existe uma versão memorizada em FawkesRemotePage; ver o comentário lá.
   */
  const load = useCallback((): StoredDevice | null => {
    const deviceId = localStorage.getItem(DEVICE_ID_KEY)
    const token = localStorage.getItem(TOKEN_KEY)
    return deviceId && token ? { deviceId, token } : null
  }, [])

  const save = useCallback((deviceId: string, token: string): void => {
    localStorage.setItem(DEVICE_ID_KEY, deviceId)
    localStorage.setItem(TOKEN_KEY, token)
  }, [])

  const clear = useCallback((): void => {
    localStorage.removeItem(DEVICE_ID_KEY)
    localStorage.removeItem(TOKEN_KEY)
  }, [])

  return useMemo(() => ({ load, save, clear }), [clear, load, save])
}
