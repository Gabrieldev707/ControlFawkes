import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import { ProfilePhoto } from './ProfilePhoto'


describe('ProfilePhoto', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('começa sem foto e com o nível à mostra', () => {
    render(<ProfilePhoto nivel={5} total={12} />)

    // "12 medalhas" lia-se como doze conquistadas, enquanto o bloco de
    // conquistas dizia "5 de 12" na mesma tela.
    expect(screen.getByText('Nível 5 · 5 de 12 medalhas')).toBeTruthy()
    expect(screen.queryByText('Nível 5 · 12 medalhas')).toBeNull()
    expect(screen.getByRole('button', { name: 'Escolher uma foto' })).toBeTruthy()
  })

  it('guarda o nome e o traz de volta na próxima abertura', () => {
    const primeira = render(<ProfilePhoto nivel={0} total={12} />)

    fireEvent.change(screen.getByLabelText('Seu nome'), { target: { value: 'Gabriel' } })
    primeira.unmount()
    render(<ProfilePhoto nivel={0} total={12} />)

    expect((screen.getByLabelText('Seu nome') as HTMLInputElement).value).toBe('Gabriel')
  })

  it('mostra a foto já guardada sem pedir de novo', () => {
    localStorage.setItem('controlfawkes.foto', 'data:image/jpeg;base64,abc')

    render(<ProfilePhoto nivel={0} total={12} />)

    const foto = screen.getByRole('button', { name: 'Trocar a foto' }).querySelector('img')
    expect(foto?.getAttribute('src')).toBe('data:image/jpeg;base64,abc')
  })

  it('remover apaga a foto do aparelho', async () => {
    localStorage.setItem('controlfawkes.foto', 'data:image/jpeg;base64,abc')
    render(<ProfilePhoto nivel={0} total={12} />)

    fireEvent.click(screen.getByRole('button', { name: /Remover foto/ }))

    await waitFor(() => {
      expect(localStorage.getItem('controlfawkes.foto')).toBeNull()
    })
    expect(screen.getByRole('button', { name: 'Escolher uma foto' })).toBeTruthy()
  })

  it('o anel acompanha o nível', () => {
    const { container } = render(<ProfilePhoto nivel={6} total={12} />)

    const progresso = container.querySelector('.profile-photo__progresso')!
    const [pintado, volta] = progresso.getAttribute('stroke-dasharray')!.split(' ').map(Number)
    expect(pintado).toBeCloseTo(volta / 2, 1)
  })
})
