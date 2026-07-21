export function getRadialSpring(distance: number, restRadius: number): number {
  const rawForce = (distance - restRadius) * 0.0012;
  return Math.max(-0.03, Math.min(0.03, rawForce));
}
