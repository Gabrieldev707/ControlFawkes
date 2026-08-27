import { useCallback, useMemo } from 'react'

import {
  esquecerDispositivo,
  guardarDispositivo,
  lerDispositivo,
  type DispositivoGuardado,
} from '../features/fawkes-remote/dispositivoGuardado'


export type StoredDevice = DispositivoGuardado

/**
 * O pareamento deste aparelho.
 *
 * A gaveta mudou de `localStorage` para cookie em 17/08/2026, e o motivo está
 * em `dispositivoGuardado.ts`: `localStorage` é separado por porta, então
 * trocar `:5174` por `:5173` fazia o celular pedir PIN de novo com o token
 * guardado e intacto do outro lado. Cookie é escopado por host e ignora a
 * porta.
 */
export function useStoredDevice() {
  /**
   * Devolve um objeto novo a cada chamada, de propósito: lê a gaveta na hora.
   *
   * Cuidado ao usar o resultado como prop ou como dependência de efeito — a
   * identidade nova a cada render faz o efeito disparar para sempre. Para esse
   * caso existe uma versão memorizada em FawkesRemotePage; ver o comentário lá.
   */
  const load = useCallback((): StoredDevice | null => lerDispositivo(), [])

  const save = useCallback((deviceId: string, token: string): void => {
    guardarDispositivo(deviceId, token)
  }, [])

  const clear = useCallback((): void => {
    esquecerDispositivo()
  }, [])

  return useMemo(() => ({ load, save, clear }), [clear, load, save])
}
