import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { PairingScreen } from './PairingScreen'


describe('PairingScreen', () => {
  it('submits a complete six-digit PIN', () => {
    const onPair = vi.fn()
    render(
      <PairingScreen
        connected
        pending={false}
        message=""
        error={false}
        onPair={onPair}
      />,
    )

    fireEvent.change(screen.getByLabelText('PIN de pareamento'), {
      target: { value: '123456' },
    })
    fireEvent.submit(screen.getByRole('button', { name: 'Parear dispositivo' }).closest('form')!)

    expect(onPair).toHaveBeenCalledWith('123456')
  })

  it('keeps only six numeric characters', () => {
    render(
      <PairingScreen
        connected
        pending={false}
        message=""
        error={false}
        onPair={vi.fn()}
      />,
    )

    const input = screen.getByLabelText('PIN de pareamento') as HTMLInputElement
    fireEvent.change(input, { target: { value: '12a34-5678' } })

    expect(input.value).toBe('123456')
  })

  it('blocks submission while disconnected, incomplete, or pending', () => {
    const { rerender } = render(
      <PairingScreen
        connected={false}
        pending={false}
        message=""
        error={false}
        onPair={vi.fn()}
      />,
    )
    const input = screen.getByLabelText('PIN de pareamento')
    const button = screen.getByRole('button', { name: 'Parear dispositivo' }) as HTMLButtonElement
    fireEvent.change(input, { target: { value: '123456' } })
    expect(button.disabled).toBe(true)

    rerender(
      <PairingScreen
        connected
        pending
        message="Validando PIN..."
        error={false}
        onPair={vi.fn()}
      />,
    )
    expect((screen.getByRole('button', { name: 'Pareando...' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('announces an error without exposing secret data', () => {
    render(
      <PairingScreen
        connected
        pending={false}
        message="PIN incorreto."
        error
        onPair={vi.fn()}
      />,
    )

    expect(screen.getByRole('alert').textContent).toBe('PIN incorreto.')
  })
})
