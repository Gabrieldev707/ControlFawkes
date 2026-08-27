import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { ControlDeck } from './ControlDeck'
import { gestureLimitsFor } from '../../features/fawkes-remote/touchpadGesture'


function renderDeck(overrides = {}) {
  const callbacks = {
    onNavigationAction: vi.fn(),
    onPointerAction: vi.fn(),
    onKey: vi.fn(),
  }
  const utils = render(
    <ControlDeck
      disabled={false}
      navigationDisabled={false}
      currentNavigationAction={null}
      {...callbacks}
      {...overrides}
    />,
  )
  return { ...utils, ...callbacks }
}

function superficie() {
  return screen.getByRole('application', { name: 'Controle direcional' })
}

function arrastar(alvo: Element, de: [number, number], para: [number, number]) {
  fireEvent.pointerDown(alvo, { pointerId: 1, clientX: de[0], clientY: de[1] })
  fireEvent.pointerMove(alvo, { pointerId: 1, clientX: para[0], clientY: para[1] })
  // O movimento é acumulado e enviado num quadro de animação; soltar o dedo é
  // o que força o envio sem depender do `requestAnimationFrame` do ambiente.
  fireEvent.pointerUp(alvo, { pointerId: 1, clientX: para[0], clientY: para[1] })
}


describe('ControlDeck', () => {
  it('move o cursor ao arrastar', () => {
    const { onPointerAction } = renderDeck()

    arrastar(superficie(), [200, 200], [260, 230])

    // O movimento é acumulado num quadro; o efeito chega no flush.
    expect(onPointerAction).toHaveBeenCalled()
  })

  it('sobrevive a um render no meio do arrasto', () => {
    // Este era o bug: o objeto de limites era montado a cada render da página,
    // um efeito dependia da identidade dele, e a máquina de gestos era trocada
    // por uma zerada no meio do movimento — o cursor parava de responder.
    const { rerender, onPointerAction } = renderDeck()
    const alvo = superficie()

    fireEvent.pointerDown(alvo, { pointerId: 1, clientX: 200, clientY: 200 })

    // Re-render com um objeto novo, exatamente como a página fazia.
    rerender(
      <ControlDeck
        disabled={false}
        navigationDisabled={false}
        currentNavigationAction={null}
        onNavigationAction={vi.fn()}
        onPointerAction={onPointerAction}
        onKey={vi.fn()}
        gestureLimits={gestureLimitsFor('PADRAO')}
      />,
    )

    onPointerAction.mockClear()
    fireEvent.pointerMove(alvo, { pointerId: 1, clientX: 280, clientY: 200 })
    fireEvent.pointerUp(alvo, { pointerId: 1, clientX: 280, clientY: 200 })

    // O gesto continuou de pé: o `up` fecha com o flick que o movimento merece.
    expect(onPointerAction).toHaveBeenCalled()
  })

  it('manda Tab pelo botão de campo', () => {
    const { onKey } = renderDeck()

    fireEvent.click(screen.getByRole('button', { name: 'Próximo campo' }))

    expect(onKey).toHaveBeenCalledWith('TAB')
  })
})


// ── O deslize que pulava o filme ──────────────────────────────────────────
//
// Relatado em 26/08/2026: "quando mexo o mouse no controle ele sempre adianta
// tempo no que estou assistindo, tipo pula em 5seg 10seg".
//
// Não era falha intermitente. `NAVIGATE_RIGHT` vira `ARROW_RIGHT`, e seta num
// player de vídeo não navega: ela PULA. O detector de flick decide no fim do
// gesto e o comentário dele dizia que o cursor andar junto era "inofensivo,
// porque mover o cursor num menu não aciona nada" — vale num menu, e durante a
// reprodução cada movimento rápido do dedo virava um salto no filme.

describe('o deslize enquanto algo toca', () => {
  function deslizar(elemento: HTMLElement) {
    const comum = { pointerId: 1, pointerType: 'touch', isPrimary: true }
    fireEvent.pointerDown(elemento, { ...comum, clientX: 10, clientY: 100 })
    fireEvent.pointerMove(elemento, { ...comum, clientX: 90, clientY: 100 })
    fireEvent.pointerUp(elemento, { ...comum, clientX: 90, clientY: 100 })
  }

  it('com o flick habilitado, o deslize vira seta', () => {
    const onNavigationAction = vi.fn()
    render(
      <ControlDeck
        disabled={false}
        navigationDisabled={false}
        currentNavigationAction={null}
        onNavigationAction={onNavigationAction}
        onPointerAction={vi.fn()}
        onKey={vi.fn()}
        flickHabilitado
      />,
    )

    deslizar(screen.getByRole('application'))

    expect(onNavigationAction).toHaveBeenCalledWith('NAVIGATE_RIGHT')
  })

  it('TOCANDO, o mesmo deslize NÃO manda seta nenhuma', () => {
    const onNavigationAction = vi.fn()
    render(
      <ControlDeck
        disabled={false}
        navigationDisabled={false}
        currentNavigationAction={null}
        onNavigationAction={onNavigationAction}
        onPointerAction={vi.fn()}
        onKey={vi.fn()}
        flickHabilitado={false}
      />,
    )

    deslizar(screen.getByRole('application'))

    expect(onNavigationAction).not.toHaveBeenCalled()
  })

  it('o cursor continua se movendo — é o que a pessoa queria', () => {
    const onPointerAction = vi.fn()
    render(
      <ControlDeck
        disabled={false}
        navigationDisabled={false}
        currentNavigationAction={null}
        onNavigationAction={vi.fn()}
        onPointerAction={onPointerAction}
        onKey={vi.fn()}
        flickHabilitado={false}
      />,
    )

    deslizar(screen.getByRole('application'))

    expect(onPointerAction).toHaveBeenCalled()
  })

  it('a dica de uso diz o que mudou', () => {
    const { rerender } = render(
      <ControlDeck
        disabled={false}
        navigationDisabled={false}
        currentNavigationAction={null}
        onNavigationAction={vi.fn()}
        onPointerAction={vi.fn()}
        onKey={vi.fn()}
        flickHabilitado
      />,
    )
    expect(screen.getByText(/Deslize rápido para navegar/)).toBeTruthy()

    rerender(
      <ControlDeck
        disabled={false}
        navigationDisabled={false}
        currentNavigationAction={null}
        onNavigationAction={vi.fn()}
        onPointerAction={vi.fn()}
        onKey={vi.fn()}
        flickHabilitado={false}
      />,
    )
    expect(screen.getByText(/use as setas/)).toBeTruthy()
  })
})
