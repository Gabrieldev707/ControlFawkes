import { describe, expect, it } from 'vitest';
import { toCanvasAttractor } from './orbAttractor';

const canvas = { left: 100, top: 100, width: 200, height: 200 };

describe('toCanvasAttractor', () => {
  it('usa o centro relativo do canvas, não coordenadas absolutas da viewport', () => {
    expect(toCanvasAttractor({ left: 180, top: 180, width: 40, height: 40 }, canvas)).toEqual({ x: 0, y: 0 });
    expect(toCanvasAttractor({ left: 230, top: 130, width: 20, height: 20 }, canvas)).toEqual({ x: 0.4, y: 0.6 });
  });

  it('inverte o eixo Y para Three.js e limita os eixos ao canvas', () => {
    expect(toCanvasAttractor({ left: 900, top: 900, width: 20, height: 20 }, canvas)).toEqual({ x: 1, y: -1 });
    expect(toCanvasAttractor({ left: -900, top: -900, width: 20, height: 20 }, canvas)).toEqual({ x: -1, y: 1 });
  });

  it('retorna o centro quando o canvas ainda não possui tamanho', () => {
    expect(toCanvasAttractor({ left: 20, top: 20, width: 10, height: 10 }, { left: 0, top: 0, width: 0, height: 0 })).toEqual({ x: 0, y: 0 });
  });
});
