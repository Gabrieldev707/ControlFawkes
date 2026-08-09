import { useCallback, useMemo } from 'react'


const DEVICE_ID_KEY = 'controlfawkes.deviceId'
const TOKEN_KEY = 'controlfawkes.token'

export interface StoredDevice {
  deviceId: string
  token: string
}

export function useStoredDevice() {
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
