import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { VoiceButton } from './VoiceButton'


describe('VoiceButton', () => {
  it('is disabled and identifies voice input as coming soon', () => {
    render(<VoiceButton />)

    const button = screen.getByRole('button', { name: 'Entrada por voz — em breve' }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
    expect(screen.getByText('Em breve')).toBeTruthy()
  })
})
