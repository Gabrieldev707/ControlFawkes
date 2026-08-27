import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { VoiceButton } from './VoiceButton'


describe('VoiceButton', () => {
  it('convida a falar quando está parado', () => {
    const onToggle = vi.fn()
    render(<VoiceButton state="idle" onToggle={onToggle} />)

    const button = screen.getByRole('button', { name: 'Falar um comando' }) as HTMLButtonElement
    expect(button.disabled).toBe(false)

    fireEvent.click(button)
    expect(onToggle).toHaveBeenCalledTimes(1)
  })

  it('vira um botão de parar enquanto grava', () => {
    render(<VoiceButton state="recording" onToggle={vi.fn()} />)

    const button = screen.getByRole('button', { name: 'Parar de gravar' })
    expect(button.getAttribute('aria-pressed')).toBe('true')
  })

  it('não aceita toque durante a transcrição', () => {
    const onToggle = vi.fn()
    render(<VoiceButton state="transcribing" onToggle={onToggle} />)

    const button = screen.getByRole('button', { name: 'Transcrevendo o áudio' }) as HTMLButtonElement
    expect(button.disabled).toBe(true)

    fireEvent.click(button)
    expect(onToggle).not.toHaveBeenCalled()
  })

  it('continua clicável sem microfone, porque o toque é o que revela o motivo', () => {
    const onToggle = vi.fn()
    render(<VoiceButton state="unsupported" onToggle={onToggle} />)

    const button = screen.getByRole('button', { name: 'Microfone indisponível' }) as HTMLButtonElement
    expect(button.disabled).toBe(false)

    fireEvent.click(button)
    expect(onToggle).toHaveBeenCalledTimes(1)
  })
})
