import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { PlatformChoice } from './PlatformChoice'


function renderChoice(overrides = {}) {
  const callbacks = {
    onChoose: vi.fn(),
    onOpenPlatform: vi.fn(),
    onCancel: vi.fn(),
  }
  render(
    <PlatformChoice
      query="Harry Potter"
      platforms={['NETFLIX', 'PRIME_VIDEO', 'YOUTUBE', 'SPOTIFY']}
      openOnlyPlatforms={['MAX', 'DISNEY_PLUS']}
      disabled={false}
      {...callbacks}
      {...overrides}
    />,
  )
  return callbacks
}


describe('PlatformChoice', () => {
  it('separa quem recebe a consulta de quem só é aberta', () => {
    renderChoice()

    const busca = screen.getByRole('group', { name: /Busca direta/ })
    const abrir = screen.getByRole('group', { name: /Abrir e procurar por lá/ })

    expect(within(busca).getByRole('button', { name: 'Netflix' })).toBeTruthy()
    expect(within(abrir).getByRole('button', { name: 'Max' })).toBeTruthy()
    // A promessa precisa bater com o que o backend consegue cumprir.
    expect(within(busca).queryByRole('button', { name: 'Max' })).toBeNull()
  })

  it('manda buscar quando a plataforma tem busca', () => {
    const { onChoose, onOpenPlatform } = renderChoice()

    fireEvent.click(screen.getByRole('button', { name: 'Netflix' }))

    expect(onChoose).toHaveBeenCalledWith('NETFLIX')
    expect(onOpenPlatform).not.toHaveBeenCalled()
  })

  it('manda abrir quando a plataforma não tem busca por URL', () => {
    const { onChoose, onOpenPlatform } = renderChoice()

    fireEvent.click(screen.getByRole('button', { name: 'Max' }))

    expect(onOpenPlatform).toHaveBeenCalledWith('MAX')
    expect(onChoose).not.toHaveBeenCalled()
  })

  it('esconde o grupo de abrir quando o backend não sugere nenhuma', () => {
    renderChoice({ openOnlyPlatforms: [] })

    expect(screen.queryByRole('group', { name: /Abrir e procurar/ })).toBeNull()
  })

  it('deixa cancelar sem escolher nada', () => {
    const { onCancel } = renderChoice()

    fireEvent.click(screen.getByRole('button', { name: 'Cancelar busca' }))

    expect(onCancel).toHaveBeenCalledTimes(1)
  })
})

describe('PlatformChoice com catálogo', () => {
  const harryPotter = {
    title: 'Harry Potter e a Pedra Filosofal',
    year: 2001,
    posterUrl: 'https://image.tmdb.org/t/p/w185/abc.jpg',
    platforms: ['MAX' as const],
  }

  it('responde onde o título está em vez de perguntar', () => {
    renderChoice({ availability: harryPotter })

    expect(screen.getByText(/Harry Potter e a Pedra Filosofal/)).toBeTruthy()
    expect(screen.getByText('(2001)')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Assistir no Max' })).toBeTruthy()
  })

  it('abre a plataforma quando ela não aceita a consulta pela URL', () => {
    // Max não tem busca por URL: quem escolheu não precisa saber disso, então
    // o cartão decide entre buscar e abrir sozinho.
    const { onOpenPlatform, onChoose } = renderChoice({ availability: harryPotter })

    fireEvent.click(screen.getByRole('button', { name: 'Assistir no Max' }))

    expect(onOpenPlatform).toHaveBeenCalledWith('MAX')
    expect(onChoose).not.toHaveBeenCalled()
  })

  it('vai direto para a busca quando a plataforma aceita a consulta', () => {
    const { onChoose, onOpenPlatform } = renderChoice({
      availability: { ...harryPotter, platforms: ['NETFLIX' as const] },
    })

    fireEvent.click(screen.getByRole('button', { name: 'Assistir no Netflix' }))

    expect(onChoose).toHaveBeenCalledWith('NETFLIX')
    expect(onOpenPlatform).not.toHaveBeenCalled()
  })

  it('diz quando o título não está em nenhuma assinatura', () => {
    renderChoice({ availability: { ...harryPotter, platforms: [] } })

    expect(screen.getByText(/Não está em nenhuma assinatura/)).toBeTruthy()
    // A escolha manual continua ali: o catálogo pode estar incompleto.
    expect(screen.getByRole('button', { name: 'Netflix' })).toBeTruthy()
  })

  it('mantém a escolha manual como saída mesmo com o título encontrado', () => {
    renderChoice({ availability: harryPotter })

    expect(screen.getByRole('group', { name: /Ou procure em outra/ })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Netflix' })).toBeTruthy()
  })

  it('sem catálogo, continua exatamente como antes', () => {
    renderChoice({ availability: null })

    expect(screen.getByText(/Onde você quer procurar/)).toBeTruthy()
    expect(screen.queryByText(/Encontrado no catálogo/)).toBeNull()
  })

  describe('quando o nome serve para duas obras', () => {
    const filme = {
      title: 'O Justiceiro',
      year: 2004,
      posterUrl: null,
      platforms: ['MAX'] as const,
      kind: 'MOVIE' as const,
    }
    const serie = {
      title: 'Marvel - O Justiceiro',
      year: 2017,
      posterUrl: null,
      platforms: ['DISNEY_PLUS'] as const,
      kind: 'TV' as const,
    }

    function renderDuplo() {
      return renderChoice({
        query: 'o justiceiro',
        availability: { ...filme, platforms: [...filme.platforms] },
        availabilityAlternative: { ...serie, platforms: [...serie.platforms] },
      })
    }

    it('mostra os dois tipos e começa pelo melhor resultado', () => {
      renderDuplo()

      const escolha = screen.getByRole('group', { name: 'Filme ou série' })
      expect(within(escolha).getByRole('button', { name: 'Filme' })).toBeTruthy()
      expect(within(escolha).getByRole('button', { name: 'Série' })).toBeTruthy()
      expect(screen.getByRole('heading', { level: 3 }).textContent).toBe('O Justiceiro (2004)')
    })

    it('troca o título e a plataforma ao escolher o outro tipo', () => {
      renderDuplo()

      fireEvent.click(screen.getByRole('button', { name: 'Série' }))

      expect(screen.getByRole('heading', { level: 3 }).textContent)
        .toBe('Marvel - O Justiceiro (2017)')
      // O caminho para assistir precisa acompanhar: era o Max, agora é o
      // Disney+. Manter o botão antigo levaria para a obra errada.
      expect(screen.getByRole('button', { name: 'Assistir no Disney+' })).toBeTruthy()
      expect(screen.queryByRole('button', { name: 'Assistir no Max' })).toBeNull()
    })

    it('não oferece escolha nenhuma quando só existe uma leitura', () => {
      renderChoice({ availability: { ...filme, platforms: [...filme.platforms] } })

      expect(screen.queryByRole('group', { name: 'Filme ou série' })).toBeNull()
    })
  })
})
