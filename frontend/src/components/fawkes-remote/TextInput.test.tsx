import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { TextInput } from './TextInput'


function renderInput(overrides: Partial<React.ComponentProps<typeof TextInput>> = {}) {
  const onSubmit = vi.fn<(query: string) => boolean>().mockReturnValue(true)
  render(
    <TextInput
      disabled={false}
      executing={false}
      onSubmit={onSubmit}
      {...overrides}
    />,
  )
  return { onSubmit }
}


describe('TextInput', () => {
  it('trims and submits a command with Enter', () => {
    const { onSubmit } = renderInput()
    const input = screen.getByLabelText('Comando de texto') as HTMLInputElement
    fireEvent.change(input, { target: { value: '  abre netflix  ' } })

    fireEvent.submit(input.closest('form')!)

    expect(onSubmit).toHaveBeenCalledWith('abre netflix')
    expect(input.value).toBe('')
  })

  it('blocks empty text', () => {
    const { onSubmit } = renderInput()
    const input = screen.getByLabelText('Comando de texto')
    fireEvent.change(input, { target: { value: '   ' } })

    fireEvent.submit(input.closest('form')!)

    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('is disabled while disconnected or executing', () => {
    const { rerender } = render(
      <TextInput disabled executing={false} onSubmit={vi.fn()} />,
    )
    expect((screen.getByLabelText('Comando de texto') as HTMLInputElement).disabled).toBe(true)

    rerender(<TextInput disabled={false} executing onSubmit={vi.fn()} />)
    expect((screen.getByLabelText('Comando de texto') as HTMLInputElement).disabled).toBe(true)
  })

  it('keeps text and reports an unavailable socket when sending is rejected', () => {
    renderInput({ onSubmit: () => false })
    const input = screen.getByLabelText('Comando de texto') as HTMLInputElement
    fireEvent.change(input, { target: { value: 'abre spotify' } })

    fireEvent.submit(input.closest('form')!)

    expect(input.value).toBe('abre spotify')
    expect(screen.getByRole('alert').textContent).toBe('Conexão indisponível. Tente novamente.')
  })

  it('limits the command to 500 characters', () => {
    renderInput()

    expect((screen.getByLabelText('Comando de texto') as HTMLInputElement).maxLength).toBe(500)
  })
})
