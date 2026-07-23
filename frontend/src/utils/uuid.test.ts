import { describe, expect, it, vi } from 'vitest'

import { generateRequestId } from './uuid'


describe('generateRequestId', () => {
  it('uses native randomUUID when available', () => {
    const fillRandomValues = vi.fn<(values: Uint8Array<ArrayBuffer>) => void>()

    const id = generateRequestId({
      randomUUID: () => '11111111-2222-4333-8444-555555555555',
      fillRandomValues,
    })

    expect(id).toBe('11111111-2222-4333-8444-555555555555')
    expect(fillRandomValues).not.toHaveBeenCalled()
  })

  it('creates an RFC 4122 version 4 identifier without randomUUID', () => {
    const id = generateRequestId({
      fillRandomValues: (values) => {
        values.forEach((_, index) => { values[index] = index })
      },
    })

    expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
  })
})
