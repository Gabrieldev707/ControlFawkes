import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { SettingsScreen } from './SettingsScreen'


function renderSettings(overrides = {}) {
  const callbacks = {
    onChangeOrbQuality: vi.fn(),
    onChangeGestureSensitivity: vi.fn(),
    onForgetDevice: vi.fn(),
    onBack: vi.fn(),
  }
  render(
    <SettingsScreen
      connectionState="connected"
      deviceId="9f2c1ab4d5e60718"
      orbQuality="BALANCED"
      voiceState="idle"
      voiceMessage=""
      gestureSensitivity="PADRAO"
      {...callbacks}
      {...overrides}
    />,
  )
  return callbacks
}


describe('SettingsScreen', () => {
  it('mostra o estado real da conexão e do aparelho', () => {
    renderSettings()

    expect(screen.getByRole('heading', { name: 'Ajustes' })).toBeTruthy()
    expect(screen.getByText('Conectado')).toBeTruthy()
    expect(screen.getByText('9f2c1ab4d5e6…')).toBeTruthy()
  })

  it('marca a qualidade ativa e troca ao escolher outra', () => {
    const { onChangeOrbQuality } = renderSettings()

    expect(screen.getByRole('radio', { name: /Equilibrado/ }).getAttribute('aria-checked')).toBe('true')

    fireEvent.click(screen.getByRole('radio', { name: /Leve/ }))

    expect(onChangeOrbQuality).toHaveBeenCalledWith('LOW')
  })

  it('não despareia no primeiro toque', () => {
    const { onForgetDevice } = renderSettings()

    fireEvent.click(screen.getByRole('button', { name: /Desparear este aparelho/ }))

    // Recuperar exige voltar ao computador para ler o PIN: um toque só é pouco.
    expect(onForgetDevice).not.toHaveBeenCalled()
    expect(screen.getByText(/Vai precisar do PIN/)).toBeTruthy()
  })

  it('despareia depois da confirmação', () => {
    const { onForgetDevice } = renderSettings()

    fireEvent.click(screen.getByRole('button', { name: /Desparear este aparelho/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Desparear agora' }))

    expect(onForgetDevice).toHaveBeenCalledTimes(1)
  })

  it('desiste da confirmação sem apagar nada', () => {
    const { onForgetDevice } = renderSettings()

    fireEvent.click(screen.getByRole('button', { name: /Desparear este aparelho/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }))

    expect(onForgetDevice).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /Desparear este aparelho/ })).toBeTruthy()
  })

  it('não oferece desparear quem nunca pareou', () => {
    renderSettings({ deviceId: null })

    expect(screen.getByText('Não pareado')).toBeTruthy()
    expect(
      (screen.getByRole('button', { name: /Desparear este aparelho/ }) as HTMLButtonElement).disabled,
    ).toBe(true)
  })

  it('explica por que a voz não está disponível em vez de dizer que está', () => {
    renderSettings({
      voiceState: 'unsupported',
      voiceMessage: 'O microfone exige HTTPS.',
    })

    expect(screen.getByText('O microfone exige HTTPS.')).toBeTruthy()
  })
})

describe('SettingsScreen sensibilidade do gesto', () => {
  // Escopo explícito: "Alta" existe nos dois grupos de opções da tela, e sem
  // dizer de qual grupo a busca fica ambígua.
  const grupo = () => screen.getByRole('radiogroup', { name: /Sensibilidade do gesto/ })

  it('mostra o nível ativo e troca ao escolher outro', () => {
    // Os números do padrão saíram de raciocínio, não de polegar. Deixá-los
    // ajustáveis é o que transforma a sessão real em configuração, e não em
    // mais uma mudança de código.
    const { onChangeGestureSensitivity } = renderSettings()

    expect(
      within(grupo()).getByRole('radio', { name: /Padrão/ }).getAttribute('aria-checked'),
    ).toBe('true')

    fireEvent.click(within(grupo()).getByRole('radio', { name: /Baixa/ }))

    expect(onChangeGestureSensitivity).toHaveBeenCalledWith('BAIXA')
  })

  it('explica o que cada nível troca, em vez de mostrar números', () => {
    renderSettings({ gestureSensitivity: 'ALTA' })

    expect(screen.getByText('Deslize curto já navega')).toBeTruthy()
    expect(screen.getByText('Exige deslize longo; cursor mais livre')).toBeTruthy()
    expect(
      within(grupo()).getByRole('radio', { name: /Alta/ }).getAttribute('aria-checked'),
    ).toBe('true')
  })
})
