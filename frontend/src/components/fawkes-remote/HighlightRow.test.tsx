import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { HighlightRow } from './HighlightRow'


const TITULOS = [
  { title: 'Duna', year: 2021, posterUrl: 'https://image.tmdb.org/duna.jpg' },
  { title: 'Interestelar', year: 2014, posterUrl: 'https://image.tmdb.org/inter.jpg' },
]

function renderRow() {
  const onPickTitle = vi.fn()
  const onOpenPlatform = vi.fn()
  render(
    <HighlightRow
      platform="MAX"
      logo="/platforms/max.svg"
      name="Max"
      titles={TITULOS}
      disabled={false}
      onOpenPlatform={onOpenPlatform}
      onPickTitle={onPickTitle}
    />,
  )
  return { onPickTitle, onOpenPlatform }
}


describe('HighlightRow', () => {
  beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }))
  afterEach(() => vi.useRealTimers())

  it('o primeiro toque não abre nada', () => {
    // Rolar a faixa com o dedo em cima da capa abria o título no computador
    // sem querer: o toque acontece antes de o navegador decidir que era rolagem.
    const { onPickTitle } = renderRow()

    fireEvent.click(screen.getByRole('button', { name: /Duna \(2021\) no Max/ }))

    expect(onPickTitle).not.toHaveBeenCalled()
    expect(screen.getByText('Tocar de novo para abrir')).toBeTruthy()
  })

  it('o segundo toque abre', () => {
    const { onPickTitle } = renderRow()

    fireEvent.click(screen.getByRole('button', { name: /Duna \(2021\) no Max/ }))
    fireEvent.click(screen.getByRole('button', { name: /Confirmar: abrir Duna/ }))

    expect(onPickTitle).toHaveBeenCalledWith('MAX', 'Duna')
  })

  it('a confirmação expira sozinha, para não disparar muito depois', () => {
    const { onPickTitle } = renderRow()

    fireEvent.click(screen.getByRole('button', { name: /Duna \(2021\) no Max/ }))
    act(() => { vi.advanceTimersByTime(3000) })

    expect(screen.queryByText('Tocar de novo para abrir')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /Duna \(2021\) no Max/ }))
    expect(onPickTitle).not.toHaveBeenCalled()
  })

  it('cada capa se arma sozinha, sem contaminar a vizinha', () => {
    const { onPickTitle } = renderRow()

    fireEvent.click(screen.getByRole('button', { name: /Duna \(2021\) no Max/ }))
    fireEvent.click(screen.getByRole('button', { name: /Interestelar \(2014\) no Max/ }))

    expect(onPickTitle).not.toHaveBeenCalled()
  })

  it('abrir o serviço inteiro continua num toque só', () => {
    const { onOpenPlatform } = renderRow()

    fireEvent.click(screen.getByRole('button', { name: 'Abrir Max' }))

    expect(onOpenPlatform).toHaveBeenCalledWith('MAX')
  })
})
