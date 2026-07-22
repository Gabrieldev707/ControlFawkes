import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { PlatformGrid } from './PlatformGrid'


describe('PlatformGrid assets', () => {
  it('uses the local Max wordmark with the exact production path and contain class', () => {
    render(<PlatformGrid selectedPlatform={null} disabled={false} onSelect={vi.fn()} />)

    const logo = screen.getByRole('img', { name: 'Max' })
    expect(logo.getAttribute('src')).toBe('/platforms/max.svg')
    expect(logo.classList.contains('platform-logo')).toBe(true)
  })
})
