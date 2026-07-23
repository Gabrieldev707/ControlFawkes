/**
 * Níveis de qualidade do orb.
 *
 * Motivo: no iPhone as partículas ficavam quase invisíveis. Foram quatro
 * causas somadas, todas medidas antes de mexer:
 *
 * 1. A paleta do estado idle tinha 5 de 7 cores abaixo de 2,2:1 de contraste
 *    contra o fundo #050508 — quatro delas abaixo de 2:1, que somem em OLED
 *    com brilho normal. Corrigido em orbTheme.ts.
 * 2. `electronRate: 0` no idle: o estado padrão não emitia elétron nenhum.
 * 3. O canvas era limitado a `min(devicePixelRatio, 1.5)`, mas o iPhone tem
 *    DPR 3. O canvas renderizava a meia resolução e era ampliado, o que borra
 *    justamente pontos de 1 px.
 * 4. `size: 0.35` no idle, o menor de todos os estados.
 *
 * O teto de pixel ratio existe por desempenho: cada passo multiplica a área a
 * rasterizar. DPR 3 num iPhone custa 4x mais fragmentos que DPR 1.5, por isso
 * o padrão para em 2 — que já resolve a nitidez sem derrubar o frame rate.
 */

export const ORB_QUALITY_LEVELS = ['LOW', 'BALANCED', 'HIGH'] as const

export type OrbQuality = (typeof ORB_QUALITY_LEVELS)[number]

export const DEFAULT_ORB_QUALITY: OrbQuality = 'BALANCED'

export interface OrbQualityProfile {
  /** Teto do devicePixelRatio do canvas. */
  pixelRatioCap: number
  /** Multiplicador da quantidade de partículas. */
  particleScale: number
  /** Multiplicador do tamanho do ponto. */
  sizeScale: number
  /** Multiplicador da taxa de emissão de elétrons. */
  electronScale: number
}

export const ORB_QUALITY_PROFILES: Record<OrbQuality, OrbQualityProfile> = {
  // Aparelho fraco ou bateria baixa: prioriza fluidez.
  LOW: {
    pixelRatioCap: 1.5,
    particleScale: 0.6,
    sizeScale: 1.25,
    electronScale: 0.7,
  },
  // Padrão: nítido em tela retina, sem exagero de custo.
  BALANCED: {
    pixelRatioCap: 2,
    particleScale: 1,
    sizeScale: 1.35,
    electronScale: 1,
  },
  // Telas grandes ou aparelho recente.
  HIGH: {
    pixelRatioCap: 3,
    particleScale: 1.35,
    sizeScale: 1.45,
    electronScale: 1.3,
  },
}

export function isOrbQuality(value: unknown): value is OrbQuality {
  return typeof value === 'string'
    && ORB_QUALITY_LEVELS.includes(value as OrbQuality)
}

export function orbQualityProfile(quality: OrbQuality): OrbQualityProfile {
  return ORB_QUALITY_PROFILES[quality]
}
