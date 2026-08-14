import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ScreenMirror } from './ScreenMirror'


const CREDENCIAIS = { deviceId: 'aparelho', token: 'segredo' }

function renderMirror(overrides: Record<string, unknown> = {}) {
  const onTap = vi.fn()
  const onRegister = vi.fn().mockResolvedValue(true)
  render(
    <ScreenMirror
      platform="NETFLIX"
      credentials={CREDENCIAIS}
      disabled={false}
      onTap={onTap}
      onRegister={onRegister}
      {...overrides}
    />,
  )
  return { onTap, onRegister }
}

function responderComFoto() {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
    ok: true,
    status: 200,
    blob: () => Promise.resolve(new Blob([new Uint8Array([1, 2, 3])], { type: 'image/jpeg' })),
  })))
}

/** A imagem só tem tamanho num navegador de verdade; aqui ele é fingido. */
function darTamanhoAImagem(elemento: HTMLElement, largura = 300, altura = 200) {
  elemento.getBoundingClientRect = () => ({
    left: 0, top: 0, width: largura, height: altura,
    right: largura, bottom: altura, x: 0, y: 0, toJSON: () => ({}),
  })
}


describe('ScreenMirror', () => {
  // Só os dois métodos, nunca o `URL` inteiro: trocar o objeto global apaga o
  // construtor, e aí todo arquivo de teste que roda depois neste worker quebra
  // ao fazer `new URL(...)`. Aconteceu — 23 arquivos caíram de uma vez.
  const criar = URL.createObjectURL
  const revogar = URL.revokeObjectURL

  beforeEach(() => {
    URL.createObjectURL = () => 'blob:quadro'
    URL.revokeObjectURL = () => {}
  })

  afterEach(() => {
    URL.createObjectURL = criar
    URL.revokeObjectURL = revogar
  })

  it('não fotografa nada antes de pedirem', () => {
    const chamadas = vi.fn()
    vi.stubGlobal('fetch', chamadas)

    renderMirror()

    // Um quadro por toque, nunca uma transmissão ligada sozinha: é a promessa
    // que torna a feature explicável.
    expect(chamadas).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /Ver a tela/ })).toBeTruthy()
  })

  it('avisa quando a plataforma não está aberta em vez de mostrar erro cru', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: false, status: 404 })))

    renderMirror()
    fireEvent.click(screen.getByRole('button', { name: /Ver a tela/ }))

    expect(await screen.findByText(/Netflix não está aberto no computador/)).toBeTruthy()
  })

  it('tocar na foto marca o ponto, mas não clica no computador', async () => {
    // Clicar durante o cadastro faria a Netflix sair da tela de perfis, e o
    // recorte do avatar — que acontece ao salvar — pegaria a tela seguinte.
    responderComFoto()
    const { onTap } = renderMirror()

    fireEvent.click(screen.getByRole('button', { name: /Ver a tela/ }))
    const foto = await screen.findByAltText(/Foto da janela do Netflix/)
    darTamanhoAImagem(foto, 300, 200)

    fireEvent.click(foto, { clientX: 75, clientY: 100 })

    expect(onTap).not.toHaveBeenCalled()
    expect(screen.getByLabelText('Guardar este ponto como perfil')).toBeTruthy()
  })

  it('clica no ponto marcado só quando pedem, e na fração certa', async () => {
    responderComFoto()
    const { onTap } = renderMirror()

    fireEvent.click(screen.getByRole('button', { name: /Ver a tela/ }))
    const foto = await screen.findByAltText(/Foto da janela do Netflix/)
    darTamanhoAImagem(foto, 300, 200)
    fireEvent.click(foto, { clientX: 75, clientY: 100 })

    fireEvent.click(screen.getByRole('button', { name: /Só clicar aqui/ }))

    // Um quarto da largura, metade da altura — é isso que o computador precisa
    // para achar o pixel, seja qual for o tamanho da janela lá.
    expect(onTap).toHaveBeenCalledWith(0.25, 0.5)
  })

  it('só oferece cadastrar depois que existe um ponto escolhido', async () => {
    responderComFoto()
    renderMirror()

    fireEvent.click(screen.getByRole('button', { name: /Ver a tela/ }))
    const foto = await screen.findByAltText(/Foto da janela do Netflix/)
    expect(screen.queryByLabelText('Guardar este ponto como perfil')).toBeNull()

    darTamanhoAImagem(foto)
    fireEvent.click(foto, { clientX: 30, clientY: 40 })

    expect(screen.getByLabelText('Guardar este ponto como perfil')).toBeTruthy()
  })

  it('guarda o perfil com o nome digitado e o ponto tocado', async () => {
    responderComFoto()
    const { onRegister } = renderMirror()

    fireEvent.click(screen.getByRole('button', { name: /Ver a tela/ }))
    const foto = await screen.findByAltText(/Foto da janela do Netflix/)
    darTamanhoAImagem(foto, 300, 200)
    fireEvent.click(foto, { clientX: 150, clientY: 50 })

    fireEvent.change(screen.getByLabelText('Guardar este ponto como perfil'), {
      target: { value: '  Gabriel  ' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar perfil' }))

    expect(onRegister).toHaveBeenCalledWith(0.5, 0.25, 'Gabriel')
    // Guardado, o formulário sai da frente: o próximo toque começa limpo.
    await waitFor(() => {
      expect(screen.queryByLabelText('Guardar este ponto como perfil')).toBeNull()
    })
  })

  it('não deixa guardar sem nome', async () => {
    responderComFoto()
    renderMirror()

    fireEvent.click(screen.getByRole('button', { name: /Ver a tela/ }))
    const foto = await screen.findByAltText(/Foto da janela do Netflix/)
    darTamanhoAImagem(foto)
    fireEvent.click(foto, { clientX: 10, clientY: 10 })

    expect(screen.getByRole('button', { name: 'Guardar perfil' })).toHaveProperty('disabled', true)
  })
})
