import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import { ProfilePhoto } from './ProfilePhoto'


describe('ProfilePhoto', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  /**
   * Onde o nome e a foto REALMENTE moram — e por que uma troca de porta os
   * levou embora.
   *
   * Relatado em 17/08/2026: o controle era aberto em `192.168.0.168:5174`,
   * passou a ser aberto em `:5173`, e nome e foto tinham sumido. Auditado: o
   * `backend/data/perfis.json` não fora tocado (e nem é sobre isto — ele guarda
   * os perfis DO SERVIÇO, tipo "quem está assistindo?" da Netflix), e o
   * histórico estava inteiro, com todos os 19 registros.
   *
   * A causa é esta: `localStorage` é separado por ORIGEM, e origem inclui a
   * porta. `http://host:5174` e `http://host:5173` são dois armazenamentos
   * diferentes, e o segundo nasce vazio. Não houve apagamento — houve mudança
   * de gaveta.
   *
   * Isto é consequência de uma decisão deliberada: a foto nunca sai do
   * aparelho, não passa pelo servidor e não é guardada nele (ver a docstring de
   * `comoQuadrado`). O preço é este. Se o preço deixar de valer a pena, a
   * decisão a rever é a de onde o dado mora — não este teste.
   */
  it('guarda nome e foto no armazenamento do navegador, que é por origem', () => {
    render(<ProfilePhoto nivel={0} total={12} />)
    fireEvent.change(screen.getByLabelText('Seu nome'), { target: { value: 'Gabriel' } })

    expect(localStorage.getItem('controlfawkes.nome')).toBe('Gabriel')

    // Trocar de porta é ter outro `localStorage`. Aqui o equivalente possível
    // em teste: o armazenamento vazio é indistinguível de um perfil novo.
    localStorage.clear()
    render(<ProfilePhoto nivel={0} total={12} />)

    const campos = screen.getAllByLabelText('Seu nome') as HTMLInputElement[]
    expect(campos[campos.length - 1].value).toBe('')
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
