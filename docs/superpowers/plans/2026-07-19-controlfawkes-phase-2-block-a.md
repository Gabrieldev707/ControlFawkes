# ControlFawkes Phase 2 — Block A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the approved mobile control surface with the final home/control/touchpad navigation, real Windows volume step and mute commands, truthful disabled controls, platform-card magnetic energy, and a bounded Fawkes orb.

**Architecture:** Keep `FawkesRemotePage` as the authenticated WebSocket controller and split presentational behavior into focused components. Phase 2 features that depend on later blocks are rendered as truthful disabled previews; the real actions in this block are the existing Windows master-volume slider/mute plus the new typed `−5/+5` steps and local view navigation. Platform selection remains selection only—it does not claim to open Chrome. Orb attraction is converted from viewport coordinates to normalized canvas-local coordinates before reaching Three.js.

**Tech Stack:** React 19, TypeScript 6, Vite 8, Vitest 4, Testing Library, Three.js, lucide-react, CSS with mobile safe-area support.

## Global Constraints

- Implement only Block A; do not implement native pointer input, Chrome automation, platform adapters, or voice capture.
- Never show success until a correlated backend result confirms the action.
- Keep Windows volume and player volume as separate controls; player volume remains disabled until a real capability is reported in Block D/E.
- Preserve the real, draggable Windows volume slider, its `VOLUME_STATE` synchronization, feedback, and mute. Every slider `onChange` reaches the page; the sole 20 Hz rate limit with trailing delivery lives in `FawkesRemotePage`.
- Platform selection copy must say `Selecionando <plataforma>…` and `<plataforma> selecionada`; it must not claim Chrome or TV control.
- Voice is a disabled `HoldToTalkButton` shell; typed search is a locally openable `SearchSheet` with disabled submission.
- No emoji production icons; use local SVG or `lucide-react` SVG components.
- Keep the orb inside its own canvas area and derive attraction from canvas-local coordinates.
- Respect `prefers-reduced-motion` for card and orb-adjacent motion.
- Preserve the existing dirty worktree and do not overwrite unrelated user changes.
- Stop after Block A and report automated and browser evidence; physical iPhone validation remains a named manual gate.
- Do not commit or push; await authorization after the physical smoke test.

---

### Task 1: Restore the frontend baseline and lock the approved shell contract

**Files:**
- Modify: `frontend/src/features/fawkes-remote/FawkesRemotePage.test.tsx`
- Test: `frontend/src/features/fawkes-remote/FawkesRemotePage.test.tsx`

**Interfaces:**
- Consumes: current `FawkesRemotePage` and barrel exports from `components/fawkes-remote`.
- Produces: a complete test double for every component imported by the page, including `CommandBar` and `WindowsVolumeControl`.

- [ ] **Step 1: Reproduce the existing suite failure**

Run: `cd frontend; npm run test:run`

Expected: record the actual file/test pass and failure counts, identify the first root cause, and keep this output as the baseline. Do not hard-code an expected number of failures.

- [ ] **Step 2: Complete the page component mock**

Add test doubles with observable props:

```tsx
CommandBar: ({ disabled }: { disabled?: boolean }) => (
  <div data-testid="command-bar" aria-disabled={disabled}>Command bar</div>
),
WindowsVolumeControl: ({ disabled }: { disabled?: boolean }) => (
  <div data-testid="windows-volume" aria-disabled={disabled}>Windows volume</div>
),
```

Mock `WindowsVolumeControl` at its direct import path if Vitest does not reuse the barrel mock.

- [ ] **Step 3: Verify that legacy controller tests are green before new behavior**

Run: `cd frontend; npm run test:run -- src/features/fawkes-remote/FawkesRemotePage.test.tsx`

Expected: PASS for the existing 13 controller tests.

### Task 2: Add a truthful status model and final home hierarchy

**Files:**
- Create: `frontend/src/features/fawkes-remote/statusCopy.ts`
- Create: `frontend/src/features/fawkes-remote/statusCopy.test.ts`
- Create: `frontend/src/components/fawkes-remote/RemoteStatusText.tsx`
- Modify: `frontend/src/components/fawkes-remote/index.ts`
- Modify: `frontend/src/features/fawkes-remote/FawkesRemotePage.tsx`
- Modify: `frontend/src/features/fawkes-remote/FawkesRemotePage.test.tsx`

**Interfaces:**
- Produces: `getRemoteStatusCopy(input: { connectionState: ConnectionState; authState: AuthState; orbState: OrbState; selectedPlatform: Platform | null }): string`.
- Produces: `RemoteStatusText({ text, state }: { text: string; state: OrbState })` using an `aria-live="polite"` status region.

- [ ] **Step 1: Write failing status-copy tests**

Cover the exact priorities:

```ts
expect(getRemoteStatusCopy({ connectionState: 'disconnected', authState: 'authenticated', orbState: 'success', selectedPlatform: 'NETFLIX' }))
  .toBe('Computador desconectado');
expect(getRemoteStatusCopy({ connectionState: 'connected', authState: 'authenticated', orbState: 'executing', selectedPlatform: 'NETFLIX' }))
  .toBe('Selecionando Netflix…');
expect(getRemoteStatusCopy({ connectionState: 'connected', authState: 'authenticated', orbState: 'success', selectedPlatform: 'NETFLIX' }))
  .toBe('Netflix selecionada');
expect(getRemoteStatusCopy({ connectionState: 'connected', authState: 'authenticated', orbState: 'idle', selectedPlatform: null }))
  .toBe('Aguardando um comando');
```

- [ ] **Step 2: Run the status test and verify RED**

Run: `cd frontend; npm run test:run -- src/features/fawkes-remote/statusCopy.test.ts`

Expected: FAIL because `statusCopy.ts` does not exist.

- [ ] **Step 3: Implement the minimal deterministic mapping**

Use this exact priority: disconnected → connecting → pairing required → authenticating → ready → executing → success/error. Only authenticated idle state may say `Aguardando um comando`. Then map `listening`, `transcribing`, `needs_selection`, `executing`, `success`, and `error`. Use a local `Record<Platform, string>` for display names; never infer labels from protocol literals.

- [ ] **Step 4: Add a failing page-order test**

Render the authenticated page and assert DOM order with `compareDocumentPosition`: connection status, orb, live status text, platform grid, primary voice/search access, then navigation access. Also assert the old title does not sit between connection and orb.

- [ ] **Step 5: Run the page-order test and verify RED**

Run: `cd frontend; npm run test:run -- src/features/fawkes-remote/FawkesRemotePage.test.tsx`

Expected: FAIL because volume currently precedes the orb and the live status component is absent.

- [ ] **Step 6: Implement the final home hierarchy**

Structure the authenticated surface as:

```tsx
<ConnectionStatus state={connectionState} />
<section className="orb-section"><RemoteOrb ... /></section>
<RemoteStatusText text={statusText} state={orbState} />
<PlatformGrid ... />
<HoldToTalkButton disabled unavailableReason="Disponível no Bloco F — Voz" />
<SearchSheet ... />
<RemoteNavigation ... />
```

Pairing remains an overlay/screen and no command control is interactive until authentication succeeds.

- [ ] **Step 7: Verify status and hierarchy tests**

Run: `cd frontend; npm run test:run -- src/features/fawkes-remote/statusCopy.test.ts src/features/fawkes-remote/FawkesRemotePage.test.tsx`

Expected: PASS.

### Task 3: Make Windows volume step controls real and player volume explicitly unavailable

**Files:**
- Create: `frontend/src/components/fawkes-remote/WindowsVolumeControl.test.tsx`
- Modify: `frontend/src/components/fawkes-remote/WindowsVolumeControl.tsx`
- Modify: `frontend/src/components/fawkes-remote/WindowsVolumeControl.css`
- Create: `frontend/src/components/fawkes-remote/PlayerVolumeControl.tsx`
- Create: `frontend/src/components/fawkes-remote/PlayerVolumeControl.test.tsx`
- Modify: `frontend/src/features/fawkes-remote/FawkesRemotePage.tsx`
- Modify: `frontend/src/features/fawkes-remote/FawkesRemotePage.test.tsx`

**Interfaces:**
- `WindowsVolumeControl` consumes `{ volume, isMuted, onSetVolume(level: number), onStep(delta: -5 | 5), onToggleMute, disabled }` and preserves its real draggable range input.
- `PlayerVolumeControl` consumes `{ available: false, reason: string }` in Block A and exposes disabled `−`, `+`, and mute buttons with the explanation attached via `aria-describedby`.
- The page sends `{ type: 'VOLUME_STEP', requestId, payload: { delta } }` and waits for `VOLUME_STATE`; it never predicts success locally.

- [ ] **Step 1: Write failing volume-control tests**

Assert that clicking the labelled buttons calls `onStep(-5)`, `onStep(5)`, and `onToggleMute`; assert all controls are disabled when `disabled` is true; assert the mute icon is SVG and no emoji text is present.

- [ ] **Step 2: Verify volume component RED**

Run: `cd frontend; npm run test:run -- src/components/fawkes-remote/WindowsVolumeControl.test.tsx`

Expected: FAIL because `onStep` and the decrement/increment buttons do not exist.

- [ ] **Step 3: Implement accessible `−/+5` and mute controls**

Use `Volume2`/`VolumeX` from `lucide-react`, keep the range fully interactive (`aria-label="Volume do computador"`) with its current local drag state and final send, and call `onSetVolume` for every `onChange`. Apply the single 20 Hz rate limit with trailing delivery in `FawkesRemotePage`. Label controls `Diminuir volume do computador`, `Aumentar volume do computador`, and `Ativar/Desativar mudo do computador`. Repeated presses are clamped to `0–100`; visual/tactile feedback uses CSS active state plus optional `navigator.vibrate` when available.

- [ ] **Step 4: Write and verify the player-volume RED test**

Assert the heading `Volume do player`, disabled buttons, and the explanation `Disponível após conexão com o navegador`.

Run: `cd frontend; npm run test:run -- src/components/fawkes-remote/PlayerVolumeControl.test.tsx`

Expected: FAIL because the component does not exist.

- [ ] **Step 5: Implement the disabled player-volume preview**

Render a separate component and never route it to Windows volume callbacks.

- [ ] **Step 6: Write failing page protocol tests for volume step**

Click both Windows buttons and assert the exact typed messages:

```ts
expect(mockSendMessage).toHaveBeenCalledWith(expect.objectContaining({
  type: 'VOLUME_STEP',
  payload: { delta: -5 },
}));
```

Also assert disconnected/auth-required states prevent sends.

- [ ] **Step 7: Implement page wiring and verify GREEN**

Run: `cd frontend; npm run test:run -- src/components/fawkes-remote/WindowsVolumeControl.test.tsx src/components/fawkes-remote/PlayerVolumeControl.test.tsx src/features/fawkes-remote/FawkesRemotePage.test.tsx`

Expected: PASS.

### Task 4: Implement platform card state semantics and magnetic energy

**Files:**
- Create: `frontend/src/components/fawkes-remote/PlatformGrid.test.tsx`
- Modify: `frontend/src/components/fawkes-remote/PlatformGrid.tsx`
- Modify: `frontend/src/styles/fawkes-remote.css`

**Interfaces:**
- `PlatformGrid` consumes `{ selectedPlatform, activeState: 'idle' | 'executing' | 'success' | 'error', disabled, onSelect }`.
- Each card exposes its state through `data-state` and CSS custom properties `--brand-rgb` and `--brand-color` defined from a local trusted platform registry.

- [ ] **Step 1: Write failing card-state tests**

Assert six local-logo cards in a 3×2 grid; `data-state="idle"` initially; selected platform receives `selected`, `executing`, `success`, or `error`; unrelated cards remain idle; all receive `disabled` when disconnected.

- [ ] **Step 2: Verify platform test RED**

Run: `cd frontend; npm run test:run -- src/components/fawkes-remote/PlatformGrid.test.tsx`

Expected: FAIL because cards only expose the legacy `active` class.

- [ ] **Step 3: Implement explicit state derivation and trusted brand metadata**

Keep logo paths local under `/platforms/`; add no network asset. Pass the button `DOMRect` only from the selected known card.

- [ ] **Step 4: Implement magnetic-energy CSS**

Use `:active` for compression, `::before` for bounded halo, logo translate/scale, a finite success/error pulse, and an executing breath. Add:

```css
@media (prefers-reduced-motion: reduce) {
  .platform-card,
  .platform-card::before,
  .platform-card__logo { animation: none !important; transition-duration: 0.01ms !important; }
}
```

No idle animation and no particles outside the card.

- [ ] **Step 5: Verify card tests**

Run: `cd frontend; npm run test:run -- src/components/fawkes-remote/PlatformGrid.test.tsx`

Expected: PASS.

### Task 5: Bound orb attraction to canvas-local normalized coordinates

**Files:**
- Create: `frontend/src/components/fawkes-remote/orbAttractor.ts`
- Create: `frontend/src/components/fawkes-remote/orbAttractor.test.ts`
- Modify: `frontend/src/components/fawkes-remote/RemoteOrb.tsx`
- Modify: `frontend/src/components/fawkes-remote/FawkesOrb.ts`
- Modify: `frontend/src/features/fawkes-remote/FawkesRemotePage.tsx`

**Interfaces:**
- Produces `toCanvasAttractor(cardRect: RectLike, canvasRect: RectLike): { x: number; y: number }` with both axes clamped to `[-1, 1]` and Y inverted for Three.js convention.
- `RemoteOrb` consumes `targetRect?: DOMRect | null` plus brand color/intensity and performs conversion using its own mount rectangle.
- `FawkesOrb.setAttractorTarget` accepts only normalized coordinates and clamps again defensively.

- [ ] **Step 1: Write failing coordinate tests**

Cover centered card `(0,0)`, right/below direction, Y inversion, and a card far outside the canvas clamped to `[-1,1]`.

- [ ] **Step 2: Verify attractor RED**

Run: `cd frontend; npm run test:run -- src/components/fawkes-remote/orbAttractor.test.ts`

Expected: FAIL because the helper does not exist.

- [ ] **Step 3: Implement pure coordinate conversion**

Use centers and half extents only:

```ts
const x = clamp((cardCenterX - canvasCenterX) / (canvasRect.width / 2), -1, 1);
const y = clamp(-(cardCenterY - canvasCenterY) / (canvasRect.height / 2), -1, 1);
```

Return `(0,0)` when canvas width or height is zero.

- [ ] **Step 4: Wire normalized attraction into the orb**

Keep viewport `DOMRect` out of `FawkesOrb`. Map normalized X/Y to bounded world offsets inside the orb implementation; never pass `rect.left` or `rect.top` directly to Three.js.

- [ ] **Step 5: Verify helper and existing orb tests/build**

Run: `cd frontend; npm run test:run -- src/components/fawkes-remote/orbAttractor.test.ts`

Expected: PASS.

Run: `cd frontend; npm run build`

Expected: exit 0 with no TypeScript error.

### Task 6: Add home/control/touchpad navigation with truthful previews

**Files:**
- Create: `frontend/src/components/fawkes-remote/RemoteNavigation.tsx`
- Create: `frontend/src/components/fawkes-remote/RemoteNavigation.test.tsx`
- Create: `frontend/src/components/fawkes-remote/HoldToTalkButton.tsx`
- Create: `frontend/src/components/fawkes-remote/HoldToTalkButton.test.tsx`
- Create: `frontend/src/components/fawkes-remote/SearchSheet.tsx`
- Create: `frontend/src/components/fawkes-remote/SearchSheet.test.tsx`
- Create: `frontend/src/components/fawkes-remote/MediaControlPanel.tsx`
- Create: `frontend/src/components/fawkes-remote/TouchpadPreview.tsx`
- Modify: `frontend/src/components/fawkes-remote/index.ts`
- Modify: `frontend/src/features/fawkes-remote/FawkesRemotePage.tsx`
- Modify: `frontend/src/features/fawkes-remote/FawkesRemotePage.test.tsx`
- Modify: `frontend/src/styles/fawkes-remote.css`

**Interfaces:**
- Page-local view type: `type RemoteView = 'home' | 'control' | 'touchpad'`.
- `RemoteNavigation` consumes `{ currentView, onNavigate }` and is always available because it changes only local UI state.
- `HoldToTalkButton` is a disabled SVG-microphone preview and never requests microphone permission.
- `SearchSheet` consumes `{ open, onClose }`, opens/closes locally, preserves safe-area spacing, and keeps `Pesquisar` disabled with an explicit reason.
- `MediaControlPanel` renders separate player/Windows volume and disabled future media actions with reasons.
- `TouchpadPreview` renders the near-full-screen visual target with disabled interaction and copy `Touchpad disponível no Bloco B`.

- [ ] **Step 1: Write failing navigation tests**

Assert `Controle` opens the media panel, `Touchpad` opens the preview, and `Início` returns home even while disconnected, connecting, or authenticating. Command-sending controls remain disabled in those states. Add focused tests that the voice shell uses an SVG microphone, stays disabled with `Disponível no Bloco F — Voz`, and never touches `navigator.mediaDevices`; test that `Teclado/Pesquisa` opens a bottom sheet, `Cancelar` closes it, the text field is not permanently present on home, and `Pesquisar` remains disabled with `Pesquisa disponível após conexão com o navegador`.

- [ ] **Step 2: Verify navigation RED**

Run: `cd frontend; npm run test:run -- src/components/fawkes-remote/RemoteNavigation.test.tsx src/features/fawkes-remote/FawkesRemotePage.test.tsx`

Expected: FAIL because view navigation does not exist.

- [ ] **Step 3: Implement page-local view navigation**

Do not add a router dependency. Preserve connection/auth state across view changes. Render SVG icons from `lucide-react`; render no emoji.

- [ ] **Step 4: Implement the approved voice and typed-search shells**

Place `HoldToTalkButton` immediately below the platform grid, then a discreet `Teclado/Pesquisa` button. Render `SearchSheet` as a bottom sheet with `role="dialog"`, safe-area bottom padding, local editable input, working close/cancel, and disabled submit. Do not retain the legacy permanent `CommandBar` input.

- [ ] **Step 5: Add media-control preview**

Show the player volume separately, then Windows volume, then disabled seek/play/fullscreen/escape/back/navigation actions. Every disabled group has visible human copy explaining that a later companion/input capability is required.

- [ ] **Step 6: Add touchpad preview**

Apply `touch-action: none` and `overscroll-behavior: none` to the visual pad now, but attach no pointer transport until Block B.

- [ ] **Step 7: Verify navigation, voice-shell, and search-sheet tests**

Run: `cd frontend; npm run test:run -- src/components/fawkes-remote/RemoteNavigation.test.tsx src/components/fawkes-remote/HoldToTalkButton.test.tsx src/components/fawkes-remote/SearchSheet.test.tsx src/features/fawkes-remote/FawkesRemotePage.test.tsx`

Expected: PASS.

### Task 7: Finish responsive styling, accessibility, and Block A evidence

**Files:**
- Modify: `frontend/src/index.css`
- Modify: `frontend/src/styles/fawkes-remote.css`
- Modify: `frontend/src/components/fawkes-remote/WindowsVolumeControl.css`
- Modify: `frontend/src/features/fawkes-remote/FawkesRemotePage.test.tsx`

**Interfaces:**
- No new protocol interface.
- Produces a single-column mobile shell sized with `100dvh`, safe-area padding, isolated orb canvas, 44px minimum interactive targets, and no template Vite width/border constraints.

- [ ] **Step 1: Write failing structural accessibility assertions**

Assert visible headings/labels for platform selection and both volume types, `aria-live` status, disabled reasons, and distinct labels for all icon-only buttons.

- [ ] **Step 2: Verify accessibility RED**

Run: `cd frontend; npm run test:run -- src/features/fawkes-remote/FawkesRemotePage.test.tsx`

Expected: FAIL on the missing accessible labels or descriptions identified by the assertions.

- [ ] **Step 3: Replace template-global styling with app-safe globals**

Set `html`, `body`, and `#root` to full size; remove the 1126px template frame and light/dark template tokens that override the remote. Style `.fawkes-remote-container` (the class actually emitted by the page), not the unused `.remote-container` selector.

- [ ] **Step 4: Complete responsive and reduced-motion CSS**

Use `clamp()` for orb and spacing, `env(safe-area-inset-*)`, a `3×2` platform grid down to 320px, and no card/canvas overlap. Ensure focus-visible rings meet contrast requirements.

- [ ] **Step 5: Run full automated verification**

Run: `cd frontend; npm run test:run`

Expected: all test files and tests PASS.

Run: `cd frontend; npm run lint`

Expected: exit 0, no lint errors.

Run: `cd frontend; npm run build`

Expected: exit 0 and production assets emitted.

Run: `cd backend; .venv\Scripts\python.exe -m pytest`

Expected: exit 0, with pairing, WebSocket, rate-limit, and Windows-volume tests passing.

Run: `git diff --check`

Expected: exit 0 with no whitespace errors.

Record the hash and modification time of `backend/data/paired_devices.json` before and after tests. Expected: unchanged. Confirm `git status --short -- OrcTech_v1` is empty.

- [ ] **Step 6: Run mobile browser smoke evidence**

Start the app with the existing backend and Vite scripts, open a 390×844 iPhone-class viewport, and capture evidence for:

1. connection → orb → status → 3×2 cards → voice/search → navigation order;
2. authenticated/disconnected disabled states;
3. control view with player and computer volume separated;
4. touchpad preview and return navigation;
5. no horizontal overflow and no particles crossing cards;
6. reduced-motion emulation with no idle card animation.

Expected: screenshots and DOM assertions support each item. If physical iPhone access is unavailable, report that limitation explicitly and do not call the physical smoke test complete.

## Plan Self-Review

- Spec coverage: every Block A bullet maps to Tasks 2–7; later-block behavior is explicitly preview-only.
- Safety: no new free-form command, URL, selector, shell, pointer transport, or false capability is introduced.
- Type consistency: `VOLUME_STEP` already exists as a typed client message with `delta: -5 | 5`; `RemoteView` is local UI state; orb coordinates are normalized before Three.js.
- Dirty-worktree protection: all edits are scoped to frontend files already involved in the approved surface, and unrelated backend changes remain untouched.
- Manual gate: browser smoke can be automated; the required physical iPhone smoke remains unverified unless the user provides the device/session.
