import * as THREE from 'three';
import type { OrbState } from '../../features/fawkes-remote/types';
import { ORB_THEMES } from './orbTheme';

// ── Constants ─────────────────────────────────────────────────────────────────
const N             = 2000;
const MAX_LINES     = 3000;
const MAX_ELECTRONS = 200;

function _makeCircleSprite() {
  const size = 64;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  
  const gradient = ctx.createRadialGradient(size/2, size/2, 0, size/2, size/2, size/2);
  gradient.addColorStop(0, 'rgba(255,255,255,1)');
  gradient.addColorStop(0.2, 'rgba(255,255,255,1)');
  gradient.addColorStop(0.5, 'rgba(255,255,255,0.2)');
  gradient.addColorStop(1, 'rgba(255,255,255,0)');
  
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);
  return new THREE.CanvasTexture(canvas);
}

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
  
  // Colors (Vertex Colors)
  private colors: Float32Array;
  private targetColors: Float32Array;

  // Connection lines
  private lineGeo: THREE.BufferGeometry;
  private lineMat: THREE.LineBasicMaterial;
  private lineObj: THREE.LineSegments;
  private linePos: Float32Array;
  private lineColors: Float32Array;

  // Electrons
  private electronGeo: THREE.BufferGeometry;
  private electronMat: THREE.PointsMaterial;
  private electronObj: THREE.Points;
  private electronPos: Float32Array;
  private electronColors: Float32Array;
  private activeElectrons: Array<{
    sx: number; sy: number; sz: number;
    ex: number; ey: number; ez: number;
    t: number; speed: number;
    color: THREE.Color;
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
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    
    const parent = canvas.parentElement;
    const w = parent ? parent.clientWidth : window.innerWidth;
    const h = parent ? parent.clientHeight : window.innerHeight;
    this.renderer.setSize(w, h);
    this.renderer.setClearColor(0x050508, 1);

    const sprite = _makeCircleSprite();

    this.scene  = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(45, w / h, 1, 1000);
    this.camera.position.z = 70; // Voltar um pouco, mas ainda mais perto que 80
    this.clock  = new THREE.Clock();

    // ── Particle data ─────────────────────────────────────────────────────────
    this.pos   = new Float32Array(N * 3);
    this.vel   = new Float32Array(N * 3);
    this.phase = new Float32Array(N);
    this.colors = new Float32Array(N * 3);
    this.targetColors = new Float32Array(N * 3);

    for (let i = 0; i < N; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi   = Math.acos(2 * Math.random() - 1);
      const r     = Math.pow(Math.random(), 0.5) * 25;
      this.pos[i * 3]     = r * Math.sin(phi) * Math.cos(theta);
      this.pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      this.pos[i * 3 + 2] = r * Math.cos(phi);
      this.phase[i] = Math.random() * 1000;
      
      // Init with idle colors
      const color = ORB_THEMES['idle'].colors[Math.floor(Math.random() * ORB_THEMES['idle'].colors.length)];
      this.colors[i*3] = color.r;
      this.colors[i*3+1] = color.g;
      this.colors[i*3+2] = color.b;
      this.targetColors[i*3] = color.r;
      this.targetColors[i*3+1] = color.g;
      this.targetColors[i*3+2] = color.b;
    }

    this.geo = new THREE.BufferGeometry();
    this.geo.setAttribute('position', new THREE.BufferAttribute(this.pos, 3));
    this.geo.setAttribute('color', new THREE.BufferAttribute(this.colors, 3));

    this.mat = new THREE.PointsMaterial({
      size:            0.6, // Voltar ao normal
      map:             sprite,
      alphaMap:        sprite,
      transparent:     true,
      opacity:         1.0, // Mas manter intenso
      sizeAttenuation: true,
      blending:        THREE.AdditiveBlending,
      depthWrite:      false,
      alphaTest:       0.01,
      vertexColors:    true,
    });

    this.pts = new THREE.Points(this.geo, this.mat);
    this.scene.add(this.pts);

    // ── Connection lines ──────────────────────────────────────────────────────
    this.linePos = new Float32Array(MAX_LINES * 6);
    this.lineColors = new Float32Array(MAX_LINES * 6);
    this.lineGeo = new THREE.BufferGeometry();
    this.lineGeo.setAttribute('position', new THREE.BufferAttribute(this.linePos, 3));
    this.lineGeo.setAttribute('color', new THREE.BufferAttribute(this.lineColors, 3));
    this.lineGeo.setDrawRange(0, 0);

    this.lineMat = new THREE.LineBasicMaterial({
      transparent: true,
      opacity:    0.15, // Suave
      blending:   THREE.AdditiveBlending,
      depthWrite: false,
      vertexColors: true,
    });

    this.lineObj = new THREE.LineSegments(this.lineGeo, this.lineMat);
    this.scene.add(this.lineObj);

    // ── Electrons ─────────────────────────────────────────────────────────────
    this.electronPos = new Float32Array(MAX_ELECTRONS * 3);
    this.electronColors = new Float32Array(MAX_ELECTRONS * 3);
    this.electronGeo = new THREE.BufferGeometry();
    this.electronGeo.setAttribute('position', new THREE.BufferAttribute(this.electronPos, 3));
    this.electronGeo.setAttribute('color', new THREE.BufferAttribute(this.electronColors, 3));
    this.electronGeo.setDrawRange(0, 0);

    this.electronMat = new THREE.PointsMaterial({
      size:            0.9, // Pouco maior
      map:             sprite,
      alphaMap:        sprite,
      transparent:     true,
      opacity:         0.9, // Mais visível
      sizeAttenuation: true,
      blending:        THREE.AdditiveBlending,
      depthWrite:      false,
      alphaTest:       0.01,
      vertexColors:    true,
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
    
    this._onResizeFallback();
    this._loop();
  }

  // ── Public API ────────────────────────────────────────────────────────────────

  set state(s: OrbState) { 
    if (this._state !== s) {
      this._state = s;
      this._assignTargetColors(s);
    }
  }
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

  private _assignTargetColors(state: OrbState) {
    const theme = ORB_THEMES[state];
    const palette = theme.colors;
    for (let i = 0; i < N; i++) {
      // Procedural pick based on phase or just random to ensure even distribution
      const colorIndex = Math.floor(Math.random() * palette.length);
      const color = palette[colorIndex];
      this.targetColors[i * 3]     = color.r;
      this.targetColors[i * 3 + 1] = color.g;
      this.targetColors[i * 3 + 2] = color.b;
    }
  }

  private _update(): void {
    const t = this.clock.getElapsedTime();

    // ── Apply Theme Targets ───────────────────────────────────────────────────
    const theme = ORB_THEMES[this._state];
    this.targetRadius = theme.radius;
    this.targetSpeed = theme.speed;
    this.targetBright = theme.brightness;
    this.targetSize = theme.size;
    this.targetLineAmount = theme.lineAmount;
    this.targetElectronRate = theme.electronRate;

    // ── Lerp Configuration ───────────────────────────────────────────────────
    const lr = 0.02;
    this.currentRadius     += (this.targetRadius     - this.currentRadius)     * lr;
    this.currentSpeed      += (this.targetSpeed      - this.currentSpeed)      * lr;
    this.currentBright     += (this.targetBright     - this.currentBright)     * lr;
    this.currentSize       += (this.targetSize       - this.currentSize)       * lr;
    this.lineAmount        += (this.targetLineAmount - this.lineAmount)        * lr;
    this.electronSpawnRate += (this.targetElectronRate - this.electronSpawnRate) * lr;

    this.mat.size = this.currentSize;
    this.mat.opacity = this.currentBright;

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

    // ── Depth breathing ───────────────────────────────────────────────────────
    let zTarget = Math.sin(t * 0.12) * 8;
    if (this._state === 'transcribing') zTarget = Math.sin(t * 0.3) * 15 + Math.sin(t * 0.9) * 6;
    else if (this._state === 'executing') zTarget = Math.sin(t * 0.15) * 6 - this.bass * 10;
    
    this.cloudZVel += (zTarget - this.cloudZ) * 0.008;
    this.cloudZVel *= 0.94;
    this.cloudZ    += this.cloudZVel;

    // ── Apply rotation + z ───────────────────────────────────────────────────
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

    // ── Particle physics & Colors ─────────────────────────────────────────────
    const p = this.geo.getAttribute('position') as THREE.BufferAttribute;
    const pColor = this.geo.getAttribute('color') as THREE.BufferAttribute;
    const a = p.array as Float32Array;
    const c = pColor.array as Float32Array;

    for (let i = 0; i < N; i++) {
      const i3 = i * 3;
      const x = a[i3], y = a[i3 + 1], z = a[i3 + 2];
      const px = this.phase[i];

      // Lerp colors
      c[i3]     += (this.targetColors[i3]     - c[i3])     * lr;
      c[i3 + 1] += (this.targetColors[i3 + 1] - c[i3 + 1]) * lr;
      c[i3 + 2] += (this.targetColors[i3 + 2] - c[i3 + 2]) * lr;

      // Oscillatory drift
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

      // Mid pulse
      if (this._state === 'executing' && this.mid > 0.1) {
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
    pColor.needsUpdate = true;

    // ── Connection lines ──────────────────────────────────────────────────────
    const activeConnections: Array<{ x1: number; y1: number; z1: number; x2: number; y2: number; z2: number; r: number; g: number; b: number }> = [];

    if (this.lineAmount > 0.01) {
      const lp = this.lineGeo.getAttribute('position') as THREE.BufferAttribute;
      const lc = this.lineGeo.getAttribute('color') as THREE.BufferAttribute;
      const la = lp.array as Float32Array;
      const lca = lc.array as Float32Array;
      
      let lineCount = 0;
      const maxDist  = 5.0 * (1 + this.bass * 0.2); // Voltar perto do original
      const maxDist2 = maxDist * maxDist;
      const step     = Math.max(1, Math.floor(N / 450));

      for (let i = 0; i < N && lineCount < MAX_LINES; i += step) {
        const i3 = i * 3;
        const x1 = a[i3], y1 = a[i3 + 1], z1 = a[i3 + 2];
        const r1 = c[i3], g1 = c[i3 + 1], b1 = c[i3 + 2];
        
        for (let j = i + step; j < N && lineCount < MAX_LINES; j += step) {
          const j3 = j * 3;
          const dx = a[j3] - x1, dy = a[j3 + 1] - y1, dz = a[j3 + 2] - z1;
          if (dx * dx + dy * dy + dz * dz < maxDist2) {
            const idx = lineCount * 6;
            
            // Positions
            la[idx]     = x1;    la[idx + 1] = y1;    la[idx + 2] = z1;
            la[idx + 3] = a[j3]; la[idx + 4] = a[j3 + 1]; la[idx + 5] = a[j3 + 2];
            
            // Colors (interpolate between the two points for line ends)
            lca[idx]     = r1;      lca[idx + 1] = g1;      lca[idx + 2] = b1;
            lca[idx + 3] = c[j3]; lca[idx + 4] = c[j3 + 1]; lca[idx + 5] = c[j3 + 2];
            
            lineCount++;
          }
        }
      }

      this.lineGeo.setDrawRange(0, lineCount * 2);
      lp.needsUpdate = true;
      lc.needsUpdate = true;
      this.lineMat.opacity = this.lineAmount * 0.04;

      // Store connections for electron spawning
      for (let k = 0; k < Math.min(lineCount, 500); k++) {
        const ci = k * 6;
        activeConnections.push({ 
          x1: la[ci], y1: la[ci + 1], z1: la[ci + 2], 
          x2: la[ci + 3], y2: la[ci + 4], z2: la[ci + 5],
          r: lca[ci], g: lca[ci + 1], b: lca[ci + 2] // Electron inherits color
        });
      }
    } else {
      this.lineGeo.setDrawRange(0, 0);
    }

    // ── Electrons ─────────────────────────────────────────────────────────────
    if (this.electronSpawnRate > 0 && activeConnections.length > 0) {
      if (t - this.lastElectronSpawn > (1.0 - this.electronSpawnRate)) {
        if (this.activeElectrons.length < MAX_ELECTRONS) {
          const conn = activeConnections[Math.floor(Math.random() * activeConnections.length)];
          this.activeElectrons.push({
            sx: conn.x1, sy: conn.y1, sz: conn.z1,
            ex: conn.x2, ey: conn.y2, ez: conn.z2,
            t: 0,
            speed: 0.02 + Math.random() * 0.04,
            color: new THREE.Color(conn.r, conn.g, conn.b)
          });
        }
        this.lastElectronSpawn = t;
      }
    }

    let aliveCount = 0;
    const ep = this.electronGeo.getAttribute('position') as THREE.BufferAttribute;
    const ec = this.electronGeo.getAttribute('color') as THREE.BufferAttribute;
    const ea = ep.array as Float32Array;
    const eca = ec.array as Float32Array;

    for (let i = this.activeElectrons.length - 1; i >= 0; i--) {
      const el = this.activeElectrons[i];
      el.t += el.speed;
      if (el.t >= 1.0) {
        this.activeElectrons.splice(i, 1);
        continue;
      }
      const ei = aliveCount * 3;
      ea[ei]     = el.sx + (el.ex - el.sx) * el.t;
      ea[ei + 1] = el.sy + (el.ey - el.sy) * el.t;
      ea[ei + 2] = el.sz + (el.ez - el.sz) * el.t;
      
      eca[ei]     = el.color.r;
      eca[ei + 1] = el.color.g;
      eca[ei + 2] = el.color.b;
      
      aliveCount++;
    }

    this.electronGeo.setDrawRange(0, aliveCount);
    ep.needsUpdate = true;
    ec.needsUpdate = true;
  }
}
