import type { Platform } from './types'


export interface PlatformBrand {
  name: string
  logo: string
}

/**
 * Nome e logo de cada serviço, em um lugar só.
 *
 * Este mapa estava copiado em quatro telas. Quando o Disney+ ganhou um caminho
 * próprio na busca, três delas foram atualizadas e uma ficou para trás — o tipo
 * de divergência que não quebra o build e só aparece na tela.
 */
export const PLATFORM_BRANDS: Record<Platform, PlatformBrand> = {
  NETFLIX: { name: 'Netflix', logo: '/platforms/netflix.svg' },
  MAX: { name: 'Max', logo: '/platforms/max.svg' },
  DISNEY_PLUS: { name: 'Disney+', logo: '/platforms/disney-plus.svg' },
  PRIME_VIDEO: { name: 'Prime Video', logo: '/platforms/prime-video.svg' },
  YOUTUBE: { name: 'YouTube', logo: '/platforms/youtube.svg' },
  SPOTIFY: { name: 'Spotify', logo: '/platforms/spotify.svg' },
}

export function platformName(platform: Platform): string {
  return PLATFORM_BRANDS[platform].name
}

export function platformLogo(platform: Platform): string {
  return PLATFORM_BRANDS[platform].logo
}
