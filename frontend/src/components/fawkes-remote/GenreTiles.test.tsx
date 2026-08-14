import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { GenreTiles } from './GenreTiles'


const formatar = (segundos: number) => `${Math.round(segundos / 60)} min`

function anelDe(nome: string): SVGCircleElement {
  const selo = screen.getByText(nome).closest('.genre-tile')!
  return selo.querySelector('.genre-tile__anel') as SVGCircleElement
}


describe('GenreTiles', () => {
  it('desenha um selo por gênero, com o tempo de cada um', () => {
    render(
      <GenreTiles
        generos={[
          { nome: 'Animação', segundos: 3600 },
          { nome: 'Crime', segundos: 1800 },
        ]}
        formatar={formatar}
      />,
    )

    expect(screen.getByText('Animação')).toBeTruthy()
    expect(screen.getByText('60 min')).toBeTruthy()
    expect(screen.getByText('30 min')).toBeTruthy()
  })

  it('o anel do mais assistido fecha, e o do menor não', () => {
    render(
      <GenreTiles
        generos={[
          { nome: 'Animação', segundos: 3600 },
          { nome: 'Crime', segundos: 900 },
        ]}
        formatar={formatar}
      />,
    )

    const cheio = anelDe('Animação').getAttribute('stroke-dasharray')!
    const parcial = anelDe('Crime').getAttribute('stroke-dasharray')!

    // O primeiro número é o trecho pintado; o segundo, a volta inteira.
    const [pintadoCheio, volta] = cheio.split(' ').map(Number)
    const [pintadoParcial] = parcial.split(' ').map(Number)
    expect(pintadoCheio).toBeCloseTo(volta, 3)
    expect(pintadoParcial).toBeLessThan(volta / 2)
  })

  it('um gênero quase sem tempo ainda mostra anel', () => {
    // Sem um piso, o selo pareceria quebrado em vez de pouco assistido.
    render(
      <GenreTiles
        generos={[
          { nome: 'Animação', segundos: 36000 },
          { nome: 'Romance', segundos: 60 },
        ]}
        formatar={formatar}
      />,
    )

    const [pintado] = anelDe('Romance').getAttribute('stroke-dasharray')!.split(' ').map(Number)
    expect(pintado).toBeGreaterThan(0)
  })

  it('não ocupa espaço quando não há gênero nenhum', () => {
    const { container } = render(<GenreTiles generos={[]} formatar={formatar} />)

    expect(container.querySelector('.genre-tiles')).toBeNull()
  })

  it('mostra no máximo seis, para caber em duas linhas', () => {
    const generos = Array.from({ length: 9 }, (_, i) => ({
      nome: `Gênero ${i}`,
      segundos: 600,
    }))

    const { container } = render(<GenreTiles generos={generos} formatar={formatar} />)

    expect(container.querySelectorAll('.genre-tile')).toHaveLength(6)
  })
})

describe('nomes de gênero', () => {
  it('traduz os que o TMDB devolve em inglês', () => {
    // Ele ignora `language=pt-BR` nos gêneros que só existem no catálogo de
    // séries, e "Action & Adventure" ficava no meio de nomes em português.
    render(
      <GenreTiles
        generos={[
          { nome: 'Action & Adventure', segundos: 600 },
          { nome: 'Sci-Fi & Fantasy', segundos: 300 },
          { nome: 'Mistério', segundos: 120 },
        ]}
        formatar={formatar}
      />,
    )

    expect(screen.getByText('Ação e Aventura')).toBeTruthy()
    expect(screen.getByText('Ficção e Fantasia')).toBeTruthy()
    expect(screen.getByText('Mistério')).toBeTruthy()
  })

  it('o ícone não é esticado junto com o anel', () => {
    // O seletor amplo pegava todo `svg` do selo, e o ícone virava um borrão
    // girado 90 graus — dois gêneros diferentes viravam o mesmo desenho.
    const { container } = render(
      <GenreTiles generos={[{ nome: 'Crime', segundos: 600 }]} formatar={formatar} />,
    )

    const aros = container.querySelectorAll('.genre-tile__aro')
    const svgs = container.querySelectorAll('.genre-tile__marca svg')
    expect(aros).toHaveLength(1)
    expect(svgs.length).toBe(2)
  })
})

describe('escolha do desenho', () => {
  function iconeDe(nome: string): string {
    const selo = screen.getByText(nome).closest('.genre-tile')!
    return selo.querySelector('.genre-tile__icone')!.getAttribute('class') ?? ''
  }

  it('Animação e Ação não compartilham o mesmo desenho', () => {
    // "animacao" contém "acao": sem fronteira de palavra, Animação recebia o
    // ícone de espadas e os dois gêneros ficavam idênticos na tela.
    render(
      <GenreTiles
        generos={[
          { nome: 'Animação', segundos: 600 },
          { nome: 'Ação', segundos: 600 },
        ]}
        formatar={formatar}
      />,
    )

    expect(iconeDe('Animação')).not.toBe(iconeDe('Ação'))
    expect(iconeDe('Animação')).toContain('palette')
    expect(iconeDe('Ação')).toContain('swords')
  })

  it('um gênero desconhecido cai na claquete, sem sugerir a coisa errada', () => {
    render(
      <GenreTiles generos={[{ nome: 'Gênero Inventado', segundos: 60 }]} formatar={formatar} />,
    )

    expect(iconeDe('Gênero Inventado')).toContain('clapperboard')
  })
})
