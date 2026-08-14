import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Achievements, type Conquista } from './Achievements'


const CONQUISTAS: Conquista[] = [
  {
    codigo: 'PRIMEIRO_PLAY',
    nome: 'Primeiro play',
    descricao: 'Assista alguma coisa por mais de 90 segundos.',
    atual: 1,
    alvo: 1,
    conquistada: true,
  },
  {
    codigo: 'COLECIONADOR',
    nome: 'Colecionador',
    descricao: 'Dez títulos diferentes.',
    atual: 3,
    alvo: 10,
    conquistada: false,
  },
]


describe('Achievements', () => {
  it('desenha uma medalha por conquista', () => {
    const { container } = render(
      <Achievements conquistas={CONQUISTAS} progresso={null} />,
    )

    expect(container.querySelectorAll('.badge')).toHaveLength(2)
    expect(screen.getByText('Primeiro play')).toBeTruthy()
  })

  it('a trancada mostra o quanto falta, e a conquistada não', () => {
    // Uma medalha trancada que só diz "trancada" é enfeite; dizendo "3 de 10"
    // ela convida.
    render(<Achievements conquistas={CONQUISTAS} progresso={null} />)

    expect(screen.getByText('3/10')).toBeTruthy()
    expect(screen.queryByText('1/1')).toBeNull()
  })

  it('distingue conquistada de trancada no próprio desenho', () => {
    const { container } = render(
      <Achievements conquistas={CONQUISTAS} progresso={null} />,
    )

    const estados = [...container.querySelectorAll('.badge')]
      .map((b) => b.getAttribute('data-conquistada'))
    expect(estados).toEqual(['true', 'false'])
  })

  it('tocar numa medalha abre o detalhe por cima da tela', () => {
    // Antes o texto aparecia embaixo da grade, fora da vista de quem tocou numa
    // medalha de cima — e parecia que o toque não fazia nada.
    render(<Achievements conquistas={CONQUISTAS} progresso={null} />)

    fireEvent.click(screen.getByRole('button', { name: /Colecionador/ }))

    const caixa = screen.getByRole('dialog')
    expect(caixa.textContent).toContain('Dez títulos diferentes')
    expect(caixa.textContent).toContain('3 de 10')
  })

  it('o detalhe fecha pelo botão e pelo fundo', () => {
    render(<Achievements conquistas={CONQUISTAS} progresso={null} />)

    fireEvent.click(screen.getByRole('button', { name: /Colecionador/ }))
    fireEvent.click(screen.getAllByRole('button', { name: 'Fechar' })[0])

    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('a conquistada diz que está conquistada, sem barra de progresso', () => {
    render(<Achievements conquistas={CONQUISTAS} progresso={null} />)

    fireEvent.click(screen.getByRole('button', { name: /Primeiro play/ }))

    const caixa = screen.getByRole('dialog')
    expect(caixa.textContent).toContain('Conquistada')
    expect(caixa.querySelector('.conquista-modal__trilho')).toBeNull()
  })

  it('mostra o nível e a próxima conquista alcançável', () => {
    render(
      <Achievements
        conquistas={CONQUISTAS}
        progresso={{ nivel: 1, total: 2, proxima: CONQUISTAS[1] }}
      />,
    )

    expect(screen.getByText('Nível 1')).toBeTruthy()
    expect(screen.getByText('1 de 2 medalhas')).toBeTruthy()
    expect(screen.getByText(/A caminho:/)).toBeTruthy()
  })

  it('não ocupa espaço quando não há conquista nenhuma', () => {
    const { container } = render(<Achievements conquistas={[]} progresso={null} />)

    expect(container.querySelector('.achievements')).toBeNull()
  })
})
