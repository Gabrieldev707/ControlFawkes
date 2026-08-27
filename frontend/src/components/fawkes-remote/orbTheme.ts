import * as THREE from 'three';
import type { OrbState } from '../../features/fawkes-remote/types';

export interface OrbTheme {
  colors: THREE.Color[];
  radius: number;
  speed: number;
  brightness: number;
  size: number;
  lineAmount: number;
  electronRate: number;
  /**
   * Órbita: velocidade tangencial em torno do eixo Y.
   *
   * É o que faz a nuvem girar como uma eletrosfera em vez de só flutuar. Antes
   * o único movimento perceptível era a respiração de profundidade, e em
   * repouso o orb parecia parado.
   */
  swirl: number;
  /**
   * Onda de energia: força do anel que sai do centro e atravessa a nuvem.
   *
   * Dá um pulso com direção — dá para ver a energia viajando —, diferente da
   * respiração, que move tudo junto. Zero desliga.
   */
  waveStrength: number;
  /** Segundos entre uma onda e a seguinte. */
  wavePeriod: number;
}

export const ORB_VISUAL_TUNING = {
  spriteMidHaloOpacity: 0.55,
  // Em repouso isto dava 0,014 de opacidade: as ligações existiam no buffer e
  // não apareciam na tela. Sem elas o orb vira poeira, e é justamente a malha
  // que faz a nuvem parecer um átomo.
  lineOpacityMultiplier: 0.3,
  electronOpacity: 1,
  initialPointOpacity: 1,
} as const;

export const ORB_THEMES: Record<OrbState, OrbTheme> = {
  idle: {
    // Contraste medido contra o fundo #050508. A paleta anterior tinha cinco
    // destas sete cores abaixo de 2,2:1 e sumia no OLED; os valores entre
    // parênteses são o contraste novo.
    colors: [
      new THREE.Color('#7c3aed'), // violeta (3.6:1)
      new THREE.Color('#a78bfa'), // violeta claro (7.5:1)
      new THREE.Color('#4338ca'), // índigo (2.6:1)
      new THREE.Color('#6366f1'), // índigo claro (4.6:1)
      new THREE.Color('#a21caf'), // fúcsia (3.2:1)
      new THREE.Color('#db2777'), // rosa (4.4:1)
      new THREE.Color('#fcd34d'), // dourado (14.1:1)
    ],
    radius: 28,
    speed: 0.20,
    brightness: 1.08,
    // Repouso é a primeira tela que alguém vê e era a mais apagada de todas:
    // poucos elétrons, poucas ligações. Subiu o bastante para a nuvem ter
    // presença sem competir com os estados que precisam se destacar dela.
    size: 0.62,
    lineAmount: 0.3,
    electronRate: 0.045,
    swirl: 0.055,
    waveStrength: 0.01,
    wavePeriod: 6.5,
  },
  listening: {
    colors: [
      new THREE.Color('#fdfbf7'), // marfim
      new THREE.Color('#fdf8ed'), // perolado
      new THREE.Color('#f6e8c3'), // champagne
      new THREE.Color('#fef3c7'), // creme
      new THREE.Color('#fde68a'), // dourado claro
    ],
    radius: 22,
    speed: 0.30,
    brightness: 1.10,
    size: 0.40,
    lineAmount: 0.20,
    electronRate: 0.018,
    swirl: 0.085,
    waveStrength: 0.016,
    wavePeriod: 3.2,
  },
  transcribing: {
    colors: [
      new THREE.Color('#d97706'), // mel
      new THREE.Color('#b45309'), // âmbar
      new THREE.Color('#92400e'), // amarelo queimado
      new THREE.Color('#f59e0b'), // ouro envelhecido
      new THREE.Color('#fbbf24'), // dourado quente
    ],
    radius: 16,
    speed: 0.50,
    brightness: 1.08,
    size: 0.30,
    lineAmount: 0.35,
    electronRate: 0.015,
    swirl: 0.13,
    waveStrength: 0.02,
    wavePeriod: 2.1,
  },
  needs_selection: {
    colors: [
      new THREE.Color('#b45309'), // cobre
      new THREE.Color('#9a3412'), // bronze
      new THREE.Color('#c2410c'), // terracota
      new THREE.Color('#ea580c'), // âmbar avermelhado
      new THREE.Color('#9f1239'), // rosa queimado
    ],
    radius: 18,
    speed: 0.20,
    brightness: 1.06,
    size: 0.40,
    lineAmount: 0.22,
    electronRate: 0.015,
    swirl: 0.07,
    waveStrength: 0.014,
    wavePeriod: 4.0,
  },
  executing: {
    colors: [
      new THREE.Color('#0f766e'), // azul petróleo
      new THREE.Color('#1d4ed8'), // azul profundo
      new THREE.Color('#6d28d9'), // violeta elétrico
      new THREE.Color('#4338ca'), // índigo
      new THREE.Color('#38bdf8'), // pulsos
    ],
    radius: 16,
    speed: 0.60,
    brightness: 1.10,
    size: 0.35,
    lineAmount: 0.35,
    electronRate: 0.02,
    swirl: 0.16,
    waveStrength: 0.026,
    wavePeriod: 1.6,
  },
  success: {
    colors: [
      new THREE.Color('#99f6e4'), // turquesa pálido
      new THREE.Color('#a3e635'), // sálvia
      new THREE.Color('#f6e8c3'), // champagne
      new THREE.Color('#fef08a'), // dourado claro
      new THREE.Color('#5eead4'), // azul esverdeado
    ],
    radius: 30,
    speed: 0.60,
    brightness: 1.10,
    size: 0.50,
    lineAmount: 0.15,
    electronRate: 0.05,
    swirl: 0.11,
    waveStrength: 0.034,
    wavePeriod: 2.4,
  },
  error: {
    colors: [
      new THREE.Color('#9f1239'), // rubi
      new THREE.Color('#831843'), // vinho
      new THREE.Color('#7f1d1d'), // vermelho escuro
      new THREE.Color('#4c0519'), // bordô
      new THREE.Color('#f43f5e'), // vermelho seco
    ],
    radius: 20,
    speed: 0.40,
    brightness: 1.02,
    size: 0.25,
    lineAmount: 0.10,
    electronRate: 0.02,
    swirl: 0.03,
    waveStrength: 0.022,
    wavePeriod: 1.2,
  }
};
