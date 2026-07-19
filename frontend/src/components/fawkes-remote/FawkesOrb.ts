/**
 * FAWKES Orb — port fiel do jarvis (github.com/ethanplusai/jarvis)
 * com identidade visual FAWKES (violet / cyan).
 *
 * Arquitetura:
 *   - 2000 partículas com física CPU (velocity + drift)
 *   - Linhas de conexão entre partículas próximas (additive blending)
 *   - Electrons: pontos brancos que percorrem as conexões (no estado thinking)
 *   - THREE.Clock para tempo em segundos (mesma base do original)
 *   - Rotação aplicada em points + lines + electrons (sync visual)
 *
 * Paleta FAWKES:
 *   idle       → #7c3aed  violet
 *   listening  → #06b6d4  cyan
 *   thinking   → #4c1d95  deep violet
 *   responding → #a78bfa  light violet
 *   error      → #ef4444  red
 */

import * as THREE from 'three';
export type OrbState = 'idle' | 'listening' | 'thinking' | 'responding' | 'error' | 'success';

// ── Constants ─────────────────────────────────────────────────────────────────

const N             = 2000;
const MAX_LINES     = 3000;
const MAX_ELECTRONS = 200;

// ── FawkesOrb ─────────────────────────────────────────────────────────────────

export class FawkesOrb {
  private renderer:    THREE.WebGLRenderer;
  private scene:       THREE.Scene;
  private camera:      THREE.PerspectiveCamera;
  private clock:       THREE.Clock;

  // Particles
  private geo:   THREE.BufferGeometry;
  private mat:   THREE.PointsMaterial;
  private pts:   THREE.Points;
  private pos:   Float32Array;
  private vel:   Float32Array;
  private phase: Float32Array;

  // Connection lines
  private lineGeo: THREE.BufferGeometry;
  private lineMat: THREE.LineBasicMaterial;
  private lineObj: THREE.LineSegments;
  private linePos: Float32Array;

  // Electrons
  private electronGeo: THREE.BufferGeometry;
  private electronMat: THREE.PointsMaterial;
  private electronObj: THREE.Points;
  private electronPos: Float32Array;
  private activeElectrons: Array<{
    sx: number; sy: number; sz: number;
    ex: number; ey: number; ez: number;
    t: number; speed: number;
  }> = [];
  private lastElectronSpawn = 0;

  // State + lerp targets
  private _state: OrbState = 'idle';
  private audioLevel = 0;
  private bass = 0;
  private mid  = 0;

  private targetRadius     = 28;
  private targetSpeed      = 0.2;
  private targetBright     = 0.5;
  private targetSize       = 0.35;
  private targetLineAmount = 0.15;
  private targetElectronRate = 0;

  private currentRadius     = 28;
  private currentSpeed      = 0.2;
  private currentBright     = 0.5;
  private currentSize       = 0.35;
  private lineAmount        = 0.15;
  private electronSpawnRate = 0;

  // Transition tumble
  private spinX = 0;
  private spinY = 0;
  private spinZ = 0;
  private transitionEnergy = 0;
  private lastStateForTumble: OrbState = 'idle';

  // Camera breathing
  private cloudZ    = 0;
  private cloudZVel = 0;

  private rafId = 0;
  private destroyed = false;

  constructor(canvas: HTMLCanvasElement) {
    // ── Renderer ─────────────────────────────────────────────────────────────
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5)); // Capped for mobile
    
    // Size based on parent element, fallback to window
    const parent = canvas.parentElement;
    const w = parent ? parent.clientWidth : window.innerWidth;
    const h = parent ? parent.clientHeight : window.innerHeight;
    this.renderer.setSize(w, h);
    this.renderer.setClearColor(0x050508, 1); // Fundo escuro fixo para que o AdditiveBlending brilhe forte

    // ── Circular sprite texture (evita quadrados) ─────────────────────────────
    const sprite = _makeCircleSprite();

    // ── Scene / Camera ────────────────────────────────────────────────────────
    this.scene  = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(45, w / h, 1, 1000);
    this.camera.position.z = 80;
    this.clock  = new THREE.Clock();

    // ── Particle data ─────────────────────────────────────────────────────────
    this.pos   = new Float32Array(N * 3);
    this.vel   = new Float32Array(N * 3);
    this.phase = new Float32Array(N);

    for (let i = 0; i < N; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi   = Math.acos(2 * Math.random() - 1);
      const r     = Math.pow(Math.random(), 0.5) * 25;
      this.pos[i * 3]     = r * Math.sin(phi) * Math.cos(theta);
      this.pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      this.pos[i * 3 + 2] = r * Math.cos(phi);
      this.phase[i] = Math.random() * 1000;
    }

    this.geo = new THREE.BufferGeometry();
    this.geo.setAttribute('position', new THREE.BufferAttribute(this.pos, 3));

    this.mat = new THREE.PointsMaterial({
      color:           0x7c3aed,
      size:            0.6,
      map:             sprite,
      alphaMap:        sprite,
      transparent:     true,
      opacity:         0.6,
      sizeAttenuation: true,
      blending:        THREE.AdditiveBlending,
      depthWrite:      false,
      alphaTest:       0.01,
    });

    this.pts = new THREE.Points(this.geo, this.mat);
    this.scene.add(this.pts);

    // ── Connection lines ──────────────────────────────────────────────────────
    this.linePos = new Float32Array(MAX_LINES * 6);
    this.lineGeo = new THREE.BufferGeometry();
    this.lineGeo.setAttribute('position', new THREE.BufferAttribute(this.linePos, 3));
    this.lineGeo.setDrawRange(0, 0);

    this.lineMat = new THREE.LineBasicMaterial({
      color:      0x7c3aed,
      transparent: true,
      opacity:    0.0,
      blending:   THREE.AdditiveBlending,
      depthWrite: false,
    });

    this.lineObj = new THREE.LineSegments(this.lineGeo, this.lineMat);
    this.scene.add(this.lineObj);

    // ── Electrons ─────────────────────────────────────────────────────────────
    this.electronPos = new Float32Array(MAX_ELECTRONS * 3);
    this.electronGeo = new THREE.BufferGeometry();
    this.electronGeo.setAttribute('position', new THREE.BufferAttribute(this.electronPos, 3));
    this.electronGeo.setDrawRange(0, 0);

    this.electronMat = new THREE.PointsMaterial({
      color:           0xc4b5fd,   // violet tint
      size:            0.8,
      map:             sprite,
      alphaMap:        sprite,
      transparent:     true,
      opacity:         0.7,
      sizeAttenuation: true,
      blending:        THREE.AdditiveBlending,
      depthWrite:      false,
      alphaTest:       0.01,
    });

    this.electronObj = new THREE.Points(this.electronGeo, this.electronMat);
    this.scene.add(this.electronObj);

    // ── Resize ────────────────────────────────────────────────────────────────
    this.resizeObserver = new ResizeObserver(this._onResize);
    if (canvas.parentElement) {
      this.resizeObserver.observe(canvas.parentElement);
    } else {
      window.addEventListener('resize', this._onResizeFallback);
    }
    
    // Initial resize to ensure correct aspect
    this._onResizeFallback();
    
    this._loop();
  }

  // ── Public API ────────────────────────────────────────────────────────────────

  set state(s: OrbState) { this._state = s; }
  get state(): OrbState  { return this._state; }

  setAudioLevel(v: number): void {
    this.audioLevel = Math.max(0, Math.min(1, v));
    this.bass = this.audioLevel * 0.8;
    this.mid  = this.audioLevel * 0.5;
  }

  destroy(): void {
    this.destroyed = true;
    cancelAnimationFrame(this.rafId);
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
    }
    window.removeEventListener('resize', this._onResizeFallback);
    
    // Dispose resources properly
    this.geo.dispose();
    this.mat.dispose();
    this.lineGeo.dispose();
    this.lineMat.dispose();
    this.electronGeo.dispose();
    this.electronMat.dispose();
    
    this.renderer.dispose();
  }

  // ── Internal ──────────────────────────────────────────────────────────────────

  private resizeObserver: ResizeObserver | null = null;

  private _onResize = (entries: ResizeObserverEntry[]): void => {
    for (let entry of entries) {
      const w = entry.contentRect.width;
      const h = entry.contentRect.height;
      if (w > 0 && h > 0) {
        this.camera.aspect = w / h;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(w, h);
      }
    }
  };

  private _onResizeFallback = (): void => {
    const parent = this.renderer.domElement.parentElement;
    const w = parent ? parent.clientWidth : window.innerWidth;
    const h = parent ? parent.clientHeight : window.innerHeight;
    if (w > 0 && h > 0) {
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(w, h);
    }
  };

  private _loop = (): void => {
    if (this.destroyed) return;
    this.rafId = requestAnimationFrame(this._loop);
    this._update();
    this.renderer.render(this.scene, this.camera);
  };

  private _update(): void {
    const t = this.clock.getElapsedTime();   // seconds — mesma base do jarvis

    // ── State targets ─────────────────────────────────────────────────────────
    switch (this._state) {
      case 'idle':
        this.targetRadius = 28; this.targetSpeed = 0.20; this.targetBright = 0.65;
        this.targetSize = 0.35; this.targetLineAmount = 0.08; this.targetElectronRate = 0;
        break;
      case 'listening':
        this.targetRadius = 22; this.targetSpeed = 0.30; this.targetBright = 0.85;
        this.targetSize = 0.40; this.targetLineAmount = 0.20; this.targetElectronRate = 0;
        break;
      case 'thinking':
        this.targetRadius = 16; this.targetSpeed = 0.50; this.targetBright = 0.90;
        this.targetSize = 0.30; this.targetLineAmount = 0.35; this.targetElectronRate = 0.015;
        break;
      case 'responding':
        this.targetRadius = 18; this.targetSpeed = 0.20; this.targetBright = 0.85;
        this.targetSize = 0.40; this.targetLineAmount = 0.22; this.targetElectronRate = 0;
        break;
      case 'error':
        this.targetRadius = 20; this.targetSpeed = 0.40; this.targetBright = 0.60;
        this.targetSize = 0.25; this.targetLineAmount = 0.10; this.targetElectronRate = 0;
        break;
      case 'success':
        this.targetRadius = 30; this.targetSpeed = 0.60; this.targetBright = 0.90;
        this.targetSize = 0.50; this.targetLineAmount = 0.15; this.targetElectronRate = 0.05;
        break;
    }

    // ── Lerp ─────────────────────────────────────────────────────────────────
    const lr = 0.02;
    this.currentRadius     += (this.targetRadius     - this.currentRadius)     * lr;
    this.currentSpeed      += (this.targetSpeed      - this.currentSpeed)      * lr;
    this.currentBright     += (this.targetBright     - this.currentBright)     * lr;
    this.currentSize       += (this.targetSize       - this.currentSize)       * lr;
    this.lineAmount        += (this.targetLineAmount - this.lineAmount)        * lr;
    this.electronSpawnRate += (this.targetElectronRate - this.electronSpawnRate) * lr;

    // ── Transition tumble ─────────────────────────────────────────────────────
    if (this._state !== this.lastStateForTumble) {
      this.transitionEnergy      = 1.0;
      this.lastStateForTumble    = this._state;
    }
    this.transitionEnergy *= 0.985;
    if (this.transitionEnergy > 0.05) {
      this.spinX += this.transitionEnergy * 0.012 * Math.sin(t * 1.7);
      this.spinY += this.transitionEnergy * 0.015;
      this.spinZ += this.transitionEnergy * 0.008 * Math.cos(t * 1.3);
    }

    // ── Audio (bass/mid set externally via setAudioLevel) ────────────────────

    // ── Depth breathing ───────────────────────────────────────────────────────
    let zTarget = Math.sin(t * 0.12) * 8;
    if (this._state === 'thinking')   zTarget = Math.sin(t * 0.3) * 15 + Math.sin(t * 0.9) * 6;
    else if (this._state === 'responding') zTarget = Math.sin(t * 0.15) * 6 - this.bass * 10;
    this.cloudZVel += (zTarget - this.cloudZ) * 0.008;
    this.cloudZVel *= 0.94;
    this.cloudZ    += this.cloudZVel;

    // ── Apply rotation + z to ALL objects (jarvis pattern) ───────────────────
    this.pts.rotation.x     = this.spinX;
    this.pts.rotation.y     = this.spinY;
    this.pts.rotation.z     = this.spinZ;
    this.pts.position.z     = this.cloudZ;
    this.lineObj.rotation.x = this.spinX;
    this.lineObj.rotation.y = this.spinY;
    this.lineObj.rotation.z = this.spinZ;
    this.lineObj.position.z = this.cloudZ;
    this.electronObj.rotation.x = this.spinX;
    this.electronObj.rotation.y = this.spinY;
    this.electronObj.rotation.z = this.spinZ;
    this.electronObj.position.z = this.cloudZ;

    // ── Particle physics ──────────────────────────────────────────────────────
    const p = this.geo.getAttribute('position') as THREE.BufferAttribute;
    const a = p.array as Float32Array;

    for (let i = 0; i < N; i++) {
      const i3 = i * 3;
      const x = a[i3], y = a[i3 + 1], z = a[i3 + 2];
      const px = this.phase[i];

      // Oscillatory drift (time in seconds → frequências low, motion suave)
      this.vel[i3]     += Math.sin(t * 0.05 + px)           * 0.001 * this.currentSpeed;
      this.vel[i3 + 1] += Math.cos(t * 0.06 + px * 1.3)     * 0.001 * this.currentSpeed;
      this.vel[i3 + 2] += Math.sin(t * 0.055 + px * 0.7)    * 0.001 * this.currentSpeed;
      this.vel[i3]     += Math.sin(t * 0.02 + px * 2.1 + y * 0.1) * 0.0008 * this.currentSpeed;
      this.vel[i3 + 1] += Math.cos(t * 0.025 + px * 1.7 + z * 0.1) * 0.0008 * this.currentSpeed;
      this.vel[i3 + 2] += Math.sin(t * 0.022 + px * 0.9 + x * 0.1) * 0.0008 * this.currentSpeed;

      // Centering pull
      const dist = Math.sqrt(x * x + y * y + z * z) || 0.01;
      const pull = Math.max(0, dist - this.currentRadius) * 0.002 + 0.0003;
      this.vel[i3]     -= (x / dist) * pull;
      this.vel[i3 + 1] -= (y / dist) * pull;
      this.vel[i3 + 2] -= (z / dist) * pull;

      // Bass push
      if (this.bass > 0.05) {
        this.vel[i3]     += (x / dist) * this.bass * 0.02;
        this.vel[i3 + 1] += (y / dist) * this.bass * 0.02;
        this.vel[i3 + 2] += (z / dist) * this.bass * 0.02;
      }

      // Mid pulse (responding)
      if (this._state === 'responding' && this.mid > 0.1) {
        const pulse = Math.sin(t * 8 + px);
        this.vel[i3]     += (x / dist) * this.mid * 0.012 * pulse;
        this.vel[i3 + 1] += (y / dist) * this.mid * 0.012 * pulse;
      }

      // Damping + integrate
      this.vel[i3]     *= 0.992;
      this.vel[i3 + 1] *= 0.992;
      this.vel[i3 + 2] *= 0.992;
      a[i3]     += this.vel[i3];
      a[i3 + 1] += this.vel[i3 + 1];
      a[i3 + 2] += this.vel[i3 + 2];
    }
    p.needsUpdate = true;

    // ── Connection lines ──────────────────────────────────────────────────────
    const activeConnections: Array<{ x1: number; y1: number; z1: number; x2: number; y2: number; z2: number }> = [];

    if (this.lineAmount > 0.01) {
      const lp = this.lineGeo.getAttribute('position') as THREE.BufferAttribute;
      const la = lp.array as Float32Array;
      let lineCount = 0;
      const maxDist  = 4.0 * (1 + this.bass * 0.2);   // Reduzido de 5.5 para 4.0 para evitar sabre de luz
      const maxDist2 = maxDist * maxDist;
      const step     = Math.max(1, Math.floor(N / 450)); // menos partículas verificadas

      for (let i = 0; i < N && lineCount < MAX_LINES; i += step) {
        const i3 = i * 3;
        const x1 = a[i3], y1 = a[i3 + 1], z1 = a[i3 + 2];
        for (let j = i + step; j < N && lineCount < MAX_LINES; j += step) {
          const j3 = j * 3;
          const dx = a[j3] - x1, dy = a[j3 + 1] - y1, dz = a[j3 + 2] - z1;
          if (dx * dx + dy * dy + dz * dz < maxDist2) {
            const idx = lineCount * 6;
            la[idx]     = x1;    la[idx + 1] = y1;    la[idx + 2] = z1;
            la[idx + 3] = a[j3]; la[idx + 4] = a[j3 + 1]; la[idx + 5] = a[j3 + 2];
            lineCount++;
          }
        }
      }

      this.lineGeo.setDrawRange(0, lineCount * 2);
      lp.needsUpdate = true;
      this.lineMat.opacity = this.lineAmount * 0.04;  // Reduzido para não estourar brilhante demais

      // Store connections for electron spawning
      for (let c = 0; c < Math.min(lineCount, 500); c++) {
        const ci = c * 6;
        activeConnections.push({ x1: la[ci], y1: la[ci + 1], z1: la[ci + 2], x2: la[ci + 3], y2: la[ci + 4], z2: la[ci + 5] });
      }
    } else {
      this.lineGeo.setDrawRange(0, 0);
    }

    // ── Electrons ─────────────────────────────────────────────────────────────
    if (activeConnections.length > 0 && this.electronSpawnRate > 0.005) {
      if (this.activeElectrons.length < 3 && (t - this.lastElectronSpawn) > 1.0) {
        const conn = activeConnections[Math.floor(Math.random() * activeConnections.length)];
        this.activeElectrons.push({
          sx: conn.x1, sy: conn.y1, sz: conn.z1,
          ex: conn.x2, ey: conn.y2, ez: conn.z2,
          t:  0,
          speed: 0.003 + Math.random() * 0.003,
        });
        this.lastElectronSpawn = t;
      }
    }

    const ep = this.electronGeo.getAttribute('position') as THREE.BufferAttribute;
    const ea = ep.array as Float32Array;
    let aliveCount = 0;

    for (let e = this.activeElectrons.length - 1; e >= 0; e--) {
      const el = this.activeElectrons[e];
      el.t += el.speed;
      if (el.t >= 1) { this.activeElectrons.splice(e, 1); continue; }
      const ei = aliveCount * 3;
      ea[ei]     = el.sx + (el.ex - el.sx) * el.t;
      ea[ei + 1] = el.sy + (el.ey - el.sy) * el.t;
      ea[ei + 2] = el.sz + (el.ez - el.sz) * el.t;
      aliveCount++;
    }

    this.electronGeo.setDrawRange(0, aliveCount);
    ep.needsUpdate = true;

    // ── Material updates ──────────────────────────────────────────────────────
    this.mat.opacity = this.currentBright + this.bass * 0.08;
    this.mat.size    = this.currentSize   + this.bass * 0.05;

    // Color lerp per state (FAWKES palette)
    const targetColor = this._stateColor();
    this.mat.color.lerp(targetColor, 0.015);
    this.lineMat.color.lerp(targetColor, 0.015);

    // ── Camera ────────────────────────────────────────────────────────────────
    this.camera.position.x = Math.sin(t * 0.02) * 5;
    this.camera.position.y = Math.cos(t * 0.03) * 3;
    this.camera.lookAt(0, 0, this.cloudZ * 0.2);
  }

  private _stateColor(): THREE.Color {
    switch (this._state) {
      case 'listening':  return new THREE.Color(0x06b6d4);
      case 'thinking':   return new THREE.Color(0x4c1d95);
      case 'responding': return new THREE.Color(0xa78bfa);
      case 'error':      return new THREE.Color(0xef4444);
      case 'success':    return new THREE.Color(0x4ade80);
      default:           return new THREE.Color(0x7c3aed);
    }
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Gera textura circular suave para evitar partículas quadradas. */
function _makeCircleSprite(): THREE.Texture {
  const size = 64;
  const c    = document.createElement('canvas');
  c.width = c.height = size;
  const ctx = c.getContext('2d')!;
  const r   = size / 2;
  const grd = ctx.createRadialGradient(r, r, 0, r, r, r);
  grd.addColorStop(0,   'rgba(255,255,255,1)');
  grd.addColorStop(0.4, 'rgba(255,255,255,0.8)');
  grd.addColorStop(1,   'rgba(255,255,255,0)');
  ctx.fillStyle = grd;
  ctx.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(c);
  tex.needsUpdate = true;
  return tex;
}
