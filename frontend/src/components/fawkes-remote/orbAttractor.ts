export interface RectLike {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface NormalizedAttractor {
  x: number;
  y: number;
}

const clamp = (value: number) => {
  const clamped = Math.max(-1, Math.min(1, value));
  return Object.is(clamped, -0) ? 0 : clamped;
};

export function toCanvasAttractor(cardRect: RectLike, canvasRect: RectLike): NormalizedAttractor {
  if (canvasRect.width <= 0 || canvasRect.height <= 0) return { x: 0, y: 0 };

  const cardCenterX = cardRect.left + cardRect.width / 2;
  const cardCenterY = cardRect.top + cardRect.height / 2;
  const canvasCenterX = canvasRect.left + canvasRect.width / 2;
  const canvasCenterY = canvasRect.top + canvasRect.height / 2;

  return {
    x: clamp((cardCenterX - canvasCenterX) / (canvasRect.width / 2)),
    y: clamp(-(cardCenterY - canvasCenterY) / (canvasRect.height / 2)),
  };
}
