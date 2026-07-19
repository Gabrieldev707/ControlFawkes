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
}

export const ORB_THEMES: Record<OrbState, OrbTheme> = {
  idle: {
    colors: [
      new THREE.Color('#4c1d95'), // roxo profundo
      new THREE.Color('#7c3aed'), // violeta
      new THREE.Color('#1e1b4b'), // azul noturno
      new THREE.Color('#312e81'), // azul cósmico
      new THREE.Color('#4a044e'), // lilás escuro
      new THREE.Color('#831843'), // magenta discreto
      new THREE.Color('#fcd34d'), // pontos dourados
    ],
    radius: 28,
    speed: 0.20,
    brightness: 0.65,
    size: 0.35,
    lineAmount: 0.08,
    electronRate: 0,
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
    brightness: 0.85,
    size: 0.40,
    lineAmount: 0.20,
    electronRate: 0,
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
    brightness: 0.90,
    size: 0.30,
    lineAmount: 0.35,
    electronRate: 0.015,
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
    brightness: 0.85,
    size: 0.40,
    lineAmount: 0.22,
    electronRate: 0,
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
    brightness: 0.95,
    size: 0.35,
    lineAmount: 0.35,
    electronRate: 0.02,
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
    brightness: 0.90,
    size: 0.50,
    lineAmount: 0.15,
    electronRate: 0.05,
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
    brightness: 0.60,
    size: 0.25,
    lineAmount: 0.10,
    electronRate: 0,
  }
};
