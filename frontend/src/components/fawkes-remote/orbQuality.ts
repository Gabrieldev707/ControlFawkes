export interface OrbQuality {
  particleCount: number;
  maxLines: number;
  pixelRatioCap: number;
  pointSizeScale: number;
  antialias: boolean;
}

export function getOrbQuality(isMobile: boolean): OrbQuality {
  return isMobile
    ? { particleCount: 1400, maxLines: 1400, pixelRatioCap: 1.5, pointSizeScale: 1.35, antialias: false }
    : { particleCount: 2000, maxLines: 3000, pixelRatioCap: 2, pointSizeScale: 1, antialias: true };
}
