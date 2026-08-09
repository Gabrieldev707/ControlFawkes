import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { KeyboardScreen } from './KeyboardScreen'


describe('KeyboardScreen', () => {
  it('sends bounded text and clears it only after transport accepts it', () => {
    const onText = vi.fn(() => true)
    render(
      <KeyboardScreen
        disabled={false}
        loading={false}
        statusMessage="Computador pronto."
        statusError={false}
        onText={onText}
        onKey={vi.fn()}
        onBack={vi.fn()}
      />,
    )

    const input = screen.getByLabelText('Texto para enviar') as HTMLTextAreaElement
    fireEvent.change(input, { target: { value: 'Olá, Fawkes!' } })
    fireEvent.submit(input.closest('form')!)

    expect(onText).toHaveBeenCalledWith('Olá, Fawkes!')
    expect(input.value).toBe('')
    expect(input.maxLength).toBe(256)
  })

  it('exposes only the safe special-key allowlist', () => {
    const onKey = vi.fn()
    render(
      <KeyboardScreen
        disabled={false}
        loading={false}
        statusMessage="Computador pronto."
        statusError={false}
        onText={vi.fn(() => true)}
        onKey={onKey}
        onBack={vi.fn()}
      />,
    )

    const keys = [
      ['Enter', 'ENTER'],
      ['Backspace', 'BACKSPACE'],
      ['Escape', 'ESCAPE'],
      ['Seta para cima', 'ARROW_UP'],
      ['Seta para baixo', 'ARROW_DOWN'],
      ['Seta para esquerda', 'ARROW_LEFT'],
      ['Seta para direita', 'ARROW_RIGHT'],
      ['Tab', 'TAB'],
      ['Espaço', 'SPACE'],
    ] as const

    for (const [label, key] of keys) {
      fireEvent.click(screen.getByRole('button', { name: label }))
      expect(onKey).toHaveBeenLastCalledWith(key)
    }
    expect(screen.queryByRole('button', { name: 'Ctrl' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Alt' })).toBeNull()
  })

  it('keeps typing available while a command is in flight', () => {
    // Desabilitar o input em voo fechava o teclado virtual do iOS a cada
    // envio: o usuário tinha de tocar no campo de novo a cada tecla. O estado
    // em voo passou a ser apenas visual.
    render(
      <KeyboardScreen
        disabled={false}
        loading
        statusMessage="Enviando texto..."
        statusError={false}
        onText={vi.fn(() => true)}
        onKey={vi.fn()}
        onBack={vi.fn()}
      />,
    )

    const input = screen.getByLabelText('Texto para enviar') as HTMLInputElement
    expect(input.disabled).toBe(false)
    expect(input.getAttribute('aria-busy')).toBe('true')
    expect((screen.getByRole('button', { name: 'Enter' }) as HTMLButtonElement).disabled).toBe(false)
  })

  it('blocks everything only when the keyboard is really unavailable', () => {
    render(
      <KeyboardScreen
        disabled
        loading={false}
        statusMessage="Desconectado."
        statusError
        onText={vi.fn(() => true)}
        onKey={vi.fn()}
        onBack={vi.fn()}
      />,
    )

    expect((screen.getByLabelText('Texto para enviar') as HTMLInputElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: 'Enter' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('keeps the text when sending fails and clears it on success', () => {
    const failing = vi.fn(() => false)
    const { unmount } = render(
      <KeyboardScreen
        disabled={false}
        loading={false}
        statusMessage=""
        statusError={false}
        onText={failing}
        onKey={vi.fn()}
        onBack={vi.fn()}
      />,
    )

    const input = screen.getByLabelText('Texto para enviar') as HTMLInputElement
    fireEvent.change(input, { target: { value: 'texto importante' } })
    fireEvent.submit(input.closest('form')!)
    expect(input.value).toBe('texto importante')
    unmount()

    const succeeding = vi.fn(() => true)
    render(
      <KeyboardScreen
        disabled={false}
        loading={false}
        statusMessage=""
        statusError={false}
        onText={succeeding}
        onKey={vi.fn()}
        onBack={vi.fn()}
      />,
    )
    const second = screen.getByLabelText('Texto para enviar') as HTMLInputElement
    fireEvent.change(second, { target: { value: 'Olá 👋 café' } })
    fireEvent.submit(second.closest('form')!)

    expect(succeeding).toHaveBeenCalledWith('Olá 👋 café')
    expect(second.value).toBe('')
  })
})
