import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { CatalogKeyCard } from './CatalogKeyCard'


const CREDENCIAIS = { deviceId: 'd1', token: 't1' }

function responder(dados: unknown, ok = true, status = 200) {
  return Promise.resolve({ ok, status, json: () => Promise.resolve(dados) })
}

describe('CatalogKeyCard', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('diz que está desligado antes de qualquer chave', async () => {
    vi.mocked(fetch).mockReturnValue(responder({
      enabled: false, source: 'NENHUMA', region: 'BR', envOverrides: false,
    }) as never)

    render(<CatalogKeyCard credentials={CREDENCIAIS} />)

    expect(await screen.findByText(/Desligado/)).toBeTruthy()
  })

  it('mostra o resultado da busca como prova, não um "ok" genérico', async () => {
    // O catálogo falha em silêncio de propósito, então chave errada, rede
    // caída e título inexistente eram indistinguíveis. O veredito precisa
    // mostrar o que a chave realmente conseguiu buscar.
    vi.mocked(fetch)
      .mockReturnValueOnce(responder({
        enabled: false, source: 'NENHUMA', region: 'BR', envOverrides: false,
      }) as never)
      .mockReturnValueOnce(responder({
        enabled: true,
        source: 'GUARDADA',
        region: 'BR',
        sample: { title: 'Interestelar', year: 2014, platforms: ['MAX'] },
      }) as never)

    render(<CatalogKeyCard credentials={CREDENCIAIS} />)
    fireEvent.change(await screen.findByLabelText('Chave do TMDB'), {
      target: { value: 'minha-chave' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Verificar' }))

    expect(await screen.findByRole('status')).toHaveProperty(
      'textContent',
      expect.stringContaining('Interestelar'),
    )
    expect(screen.getByRole('status').textContent).toContain('Max')
  })

  it('mostra o motivo quando a chave não presta', async () => {
    vi.mocked(fetch)
      .mockReturnValueOnce(responder({
        enabled: false, source: 'NENHUMA', region: 'BR', envOverrides: false,
      }) as never)
      .mockReturnValueOnce(responder(
        { detail: 'A chave não funcionou. Confira se copiou a chave inteira.' },
        false,
        422,
      ) as never)

    render(<CatalogKeyCard credentials={CREDENCIAIS} />)
    fireEvent.change(await screen.findByLabelText('Chave do TMDB'), {
      target: { value: 'errada' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Verificar' }))

    expect(await screen.findByRole('alert')).toHaveProperty(
      'textContent',
      expect.stringContaining('não funcionou'),
    )
  })

  it('avisa quando a variável de ambiente tem prioridade', async () => {
    // Aceitar a chave e não usá-la seria mentir para quem colou.
    vi.mocked(fetch).mockReturnValue(responder({
      enabled: true, source: 'AMBIENTE', region: 'BR', envOverrides: true,
    }) as never)

    render(<CatalogKeyCard credentials={CREDENCIAIS} />)

    expect(await screen.findByText(/variável de ambiente/)).toBeTruthy()
    expect(screen.queryByLabelText('Chave do TMDB')).toBeNull()
  })

  it('não pede nada ao servidor sem credenciais', async () => {
    render(<CatalogKeyCard credentials={null} />)

    await waitFor(() => expect(fetch).not.toHaveBeenCalled())
  })
})
