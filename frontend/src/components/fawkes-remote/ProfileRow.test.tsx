import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ProfileRow } from './ProfileRow'


const CREDENCIAIS = { deviceId: 'aparelho', token: 'segredo' }

function renderRow(profiles = [{ id: 'p1', nome: 'Gabriel', temAvatar: true }]) {
  const onSelect = vi.fn()
  const onRemove = vi.fn()
  const utils = render(
    <ProfileRow
      platform="NETFLIX"
      profiles={profiles}
      credentials={CREDENCIAIS}
      disabled={false}
      onSelect={onSelect}
      onRemove={onRemove}
    />,
  )
  return { ...utils, onSelect, onRemove }
}


describe('ProfileRow', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: false })))
  })

  it('não ocupa espaço quando não há perfil cadastrado', () => {
    const { container } = renderRow([])

    expect(container.querySelector('.profile-row')).toBeNull()
  })

  it('entra no perfil com um toque', () => {
    const { onSelect } = renderRow()

    fireEvent.click(screen.getByRole('button', { name: 'Entrar como Gabriel' }))

    expect(onSelect).toHaveBeenCalledWith('p1')
  })

  it('busca o avatar com as credenciais, porque src não manda cabeçalho', () => {
    const chamadas = vi.fn((_url: string, _opcoes?: RequestInit) =>
      Promise.resolve({ ok: false }))
    vi.stubGlobal('fetch', chamadas)

    renderRow()

    const [url, opcoes] = chamadas.mock.calls[0]
    expect(url).toContain('/screen/profiles/NETFLIX/p1/avatar')
    const cabecalhos = (opcoes ?? {}).headers as Record<string, string>
    expect(cabecalhos['X-Device-Token']).toBe('segredo')
  })

  it('não pede imagem para perfil que não tem avatar', () => {
    const chamadas = vi.fn(() => Promise.resolve({ ok: false }))
    vi.stubGlobal('fetch', chamadas)

    renderRow([{ id: 'p2', nome: 'Visitante', temAvatar: false }])

    expect(chamadas).not.toHaveBeenCalled()
  })

  it('deixa remover um perfil cadastrado errado', () => {
    const { onRemove } = renderRow()

    fireEvent.click(screen.getByRole('button', { name: 'Remover o perfil Gabriel' }))

    expect(onRemove).toHaveBeenCalledWith('p1')
  })
})
