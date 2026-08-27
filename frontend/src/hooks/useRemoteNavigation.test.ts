import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import { useRemoteNavigation } from './useRemoteNavigation'


describe('useRemoteNavigation', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('começa no início quando não há nada guardado', () => {
    const { result } = renderHook(() => useRemoteNavigation())

    expect(result.current.currentScreen).toBe('HOME')
  })

  it('volta para a mesma tela depois de a página recarregar', () => {
    // No iPhone, sair do navegador e voltar descarta a aba e recarrega. Sem
    // guardar a tela, isso jogava a pessoa para o início no meio do uso.
    const primeira = renderHook(() => useRemoteNavigation())
    act(() => primeira.result.current.navigate('PROFILE'))
    primeira.unmount()

    const segunda = renderHook(() => useRemoteNavigation())

    expect(segunda.result.current.currentScreen).toBe('PROFILE')
  })

  it('ignora uma tela guardada que não existe mais', () => {
    sessionStorage.setItem('controlfawkes.screen', 'TELA_QUE_NAO_EXISTE')

    const { result } = renderHook(() => useRemoteNavigation())

    expect(result.current.currentScreen).toBe('HOME')
  })

  it('nunca restaura o pareamento, que é decidido pela autenticação', () => {
    sessionStorage.setItem('controlfawkes.screen', 'PAIRING')

    const { result } = renderHook(() => useRemoteNavigation())

    expect(result.current.currentScreen).toBe('HOME')
  })

  it('voltar leva à tela anterior', () => {
    const { result } = renderHook(() => useRemoteNavigation())

    act(() => result.current.navigate('PROFILE'))
    act(() => result.current.navigate('SETTINGS'))
    act(() => result.current.goBack())

    expect(result.current.currentScreen).toBe('PROFILE')
  })
})
