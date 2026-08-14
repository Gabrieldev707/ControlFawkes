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
