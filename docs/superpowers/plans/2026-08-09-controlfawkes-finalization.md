# ControlFawkes Finalization Implementation Plan

Execution status (2026-08-09): Tasks 1–7 and Task 8 steps 1–3 are complete.
Fresh gates are recorded in `docs/FINAL_VALIDATION.md`. Delivery commits were
explicitly authorized; push and PR status are recorded in the final handoff.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish ControlFawkes as a deterministic-first, secure, mobile-first Windows remote with a premium Control screen and optional local intent resolution.

**Architecture:** Keep the audited Phase 2A protocol and adapters as the only execution authority. Absorb directional navigation into the Control screen, add deterministic common-command intents, and place a strict local-only resolver behind the deterministic parser with bounded per-device volatile context.

**Tech Stack:** React 19, TypeScript 6, Vite 8, Vitest 4, FastAPI, Pydantic 2, pytest, Windows Core Audio/Input adapters, optional Ollama HTTP API.

## Global Constraints

- No paid or required cloud AI provider.
- No shell, PowerShell, arbitrary URL, arbitrary key or arbitrary system call.
- Local AI is optional progressive enhancement and runs only after deterministic parsing returns unknown.
- All model output uses closed enums, forbids extra fields and reuses existing handlers.
- Context is volatile, keyed by `deviceId`, capped at 32 devices and expires after 600 seconds.
- Existing functional behavior and honest adapter feedback must be preserved.
- UI is mobile-first, one-hand usable, safe-area aware and has at least 44px targets.

---

### Task 1: Stabilize and record the integrated baseline

**Files:**
- Modify: `frontend/vitest.config.ts`
- Modify: `docs/FINALIZATION_LOOP.md`

**Interfaces:**
- Consumes: existing Vitest configuration.
- Produces: the unchanged `npm run test -- --run` command with a Windows-only single-thread worker policy.

- [x] **Step 1: Reproduce the baseline failure**

Run `npm run test -- --run` after `npm ci` and retain the worker timeout output.

- [x] **Step 2: Apply the minimal runner fix**

Add a platform conditional to the Vitest test config:

```ts
const windowsTestPool = process.platform === 'win32'
  ? { pool: 'threads' as const, maxWorkers: 1 }
  : {}
```

Spread it into `test` without changing `testTimeout` or assertions.

- [x] **Step 3: Verify the exact gates**

Run `npm run test -- --run`, `npm run lint`, `npm run build`, backend pytest
with a workspace-local `--basetemp`, `python -m compileall -q app tests`, and
`git diff --check`.

- [x] **Step 4: Update the ledger and commit**

Fresh counts were recorded, and the delivery commits were explicitly
authorized after the validation gates completed.

### Task 2: Make directional control the visual nucleus

**Files:**
- Create: `frontend/src/components/remote-control/DPadControl.tsx`
- Create: `frontend/src/components/remote-control/DPadControl.test.tsx`
- Modify: `frontend/src/pages/remote/RemoteControlScreen.tsx`
- Modify: `frontend/src/pages/remote/RemoteControlScreen.test.tsx`
- Modify: `frontend/src/features/fawkes-remote/FawkesRemotePage.tsx`
- Modify: `frontend/src/features/fawkes-remote/FawkesRemotePage.test.tsx`
- Modify: `frontend/src/components/navigation/RemoteNavigation.tsx`
- Modify: `frontend/src/state/currentScreen.ts`
- Delete: `frontend/src/pages/remote/NavigationScreen.tsx`
- Delete: `frontend/src/pages/remote/NavigationScreen.test.tsx`
- Modify: `frontend/src/styles/fawkes-remote.css`

**Interfaces:**
- Consumes: `NavigationAction`, `REPEATABLE_NAVIGATION_ACTIONS`, the existing
  `handleNavigationAction(action)` callback and `NavigableScreen`.
- Produces: `DPadControl({ disabled, currentAction, onAction })` and a Control
  screen that accepts `onNavigationAction(action: NavigationAction)`.

- [ ] **Step 1: Write failing D-pad behavior tests**

Assert the six allowlisted actions, disabled state, arrow hold repetition after
400ms/every 120ms, no repetition for confirm/back, and cleanup on release,
blur and unmount.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run `npx vitest run src/components/remote-control/DPadControl.test.tsx` and
confirm failure because the component does not exist.

- [ ] **Step 3: Implement the focused D-pad**

Move the proven repetition logic from `NavigationScreen` into `DPadControl`.
Keep messages closed: callbacks receive only `NavigationAction` values.

- [ ] **Step 4: Write failing Control screen tests**

Assert compact status, D-pad, previous/play/next, volume down/mute/up, secondary
seek/fullscreen, Touchpad and Keyboard callbacks, active state and disabled
state. Assert there is no separate “Navegar” primary destination.

- [ ] **Step 5: Implement the Control hierarchy and styles**

Use the approved Void/Obsidian/Violet/Cyan/Ember/Red tokens. Preserve callbacks
and server-confirmed status. Add `prefers-reduced-motion`, focus-visible and
safe-area behavior without a new dependency.

- [ ] **Step 6: Remove the duplicate destination**

Remove `NAVIGATION` from `NavigableScreen`, route branching and bottom nav only
after Control tests prove every directional action remains accessible.

- [ ] **Step 7: Verify and commit**

Run focused tests, full frontend tests, lint and build. Commit as
`refactor: make Control the primary remote experience`.

### Task 3: Complete deterministic common-command parsing

**Files:**
- Modify: `backend/app/commands/parser.py`
- Modify: `backend/app/protocol/dispatcher.py`
- Modify: `backend/tests/test_parser.py`
- Modify: `backend/tests/test_ws.py`

**Interfaces:**
- Produces: `MediaControlIntent(action: MediaAction)` and
  `VolumeControlIntent(action: VolumeAction, level: int | None = None,
  delta: Literal[-5, 5] | None = None)` as members of `ParsedIntent`.
- Dispatcher routes these intent objects into the same adapter methods used by
  closed WebSocket messages.

- [ ] **Step 1: Add failing parser tests**

Cover play, pause, previous, next, seek back/forward, fullscreen/exit,
volume up/down, mute and bounded set-volume phrases. Also assert shell/URL text
remains unknown.

- [ ] **Step 2: Confirm RED**

Run `pytest tests/test_parser.py -q` and confirm the new phrases return
`UnknownIntent` before implementation.

- [ ] **Step 3: Implement minimal closed mappings**

Use normalized exact phrase sets and bounded regex capture. Do not introduce
open-ended action strings.

- [ ] **Step 4: Add vertical WebSocket tests and implement routing**

Authenticate, send deterministic `TEXT_COMMAND`, assert adapter mock call and
typed `COMMAND_RESULT`. Assert no local resolver hook is invoked.

- [ ] **Step 5: Verify and commit**

Run parser, WebSocket and full backend suites. Commit as
`feat: complete deterministic remote command fast path`.

### Task 4: Add bounded device context and strict local intent schemas

**Files:**
- Create: `backend/app/intelligence/__init__.py`
- Create: `backend/app/intelligence/context.py`
- Create: `backend/app/intelligence/intents.py`
- Create: `backend/tests/test_device_context.py`
- Create: `backend/tests/test_local_intents.py`

**Interfaces:**
- Produces: `DeviceContextStore(ttl_seconds=600, max_devices=32)` with
  `get(device_id)`, `update(device_id, *, platform, query, action)` and
  `clear(device_id)`.
- Produces: strict Pydantic discriminated results for `OPEN_PLATFORM`,
  `SEARCH_MEDIA`, `MEDIA_CONTROL` and `SYSTEM_VOLUME`; every model sets
  `extra='forbid'`.

- [ ] **Step 1: Write RED context tests**

Test device isolation, reconnect-style retrieval by the same device ID,
expiration, maximum-device eviction and bounded field lengths.

- [ ] **Step 2: Implement the volatile store and verify GREEN**

Use `time.monotonic`, an ordered mapping and immutable context snapshots. Do
not persist to disk.

- [ ] **Step 3: Write RED schema tests**

Accept valid closed results; reject hallucinated intent, unknown platform,
arbitrary URL/key, extra fields, wrong scalar types and overlong query.

- [ ] **Step 4: Implement strict schemas and policy conversion**

Convert only to existing parser intent classes. Apply the same dangerous URI
and query policy used by deterministic search.

- [ ] **Step 5: Verify and commit**

Run both new test modules and the backend suite. Commit as
`feat: add bounded local intent context and policy`.

### Task 5: Add optional localhost-only Ollama resolution

**Files:**
- Create: `backend/app/intelligence/resolver.py`
- Create: `backend/app/intelligence/ollama.py`
- Create: `backend/app/intelligence/service.py`
- Create: `backend/tests/test_ollama_resolver.py`
- Create: `backend/tests/test_intent_service.py`
- Modify: `backend/app/protocol/dispatcher.py`
- Modify: `backend/app/main.py`
- Modify: `.env.example`

**Interfaces:**
- Produces: `LocalIntentResolver.resolve(text, context) -> LocalIntent | None`.
- Produces: `OllamaIntentResolver(base_url, model, timeout_seconds)` that only
  accepts loopback HTTP URLs and POSTs to `/api/chat` with JSON output.
- Produces: `IntentFallbackService.resolve_unknown(device_id, text)` returning
  an existing deterministic intent or `None`.

- [ ] **Step 1: Write RED resolver failure tests**

Use `httpx.MockTransport` for valid JSON, malformed JSON, extra fields,
hallucinated intent, timeout, connection error, offline health, empty model and
non-loopback URL rejection. No real model is required in CI.

- [ ] **Step 2: Implement the Ollama adapter**

Use a two-second default timeout, no API key, no telemetry and no retry on the
interactive path. Return `None` on transport or validation failure.

- [ ] **Step 3: Write RED service/dispatcher tests**

Prove known commands bypass the resolver; unknown commands may call it once;
valid output reaches an existing adapter; invalid/offline output returns
`UNKNOWN_COMMAND`; device A never receives device B context.

- [ ] **Step 4: Implement fallback-only integration**

Read `CONTROLFAWKES_LOCAL_AI=off|auto|on`, loopback URL, model and timeout.
In `auto`, an empty model disables calls. Keep all media/pointer/keyboard
message handlers independent of the resolver.

- [ ] **Step 5: Verify Ollama-offline product behavior**

Run the full backend and frontend suites with no Ollama process. Verify pairing,
closed commands and UI tests remain green and deterministic tests assert zero
resolver calls.

- [ ] **Step 6: Commit**

Commit as `feat: add optional local Ollama intent resolver`.

### Task 6: Focus orchestration boundaries without a rewrite

**Files:**
- Create: `frontend/src/hooks/useCommandFeedback.ts`
- Create: `frontend/src/hooks/useCommandFeedback.test.ts`
- Create: `frontend/src/hooks/useStoredDevice.ts`
- Create: `frontend/src/hooks/useStoredDevice.test.ts`
- Modify: `frontend/src/features/fawkes-remote/FawkesRemotePage.tsx`
- Modify: `frontend/src/features/fawkes-remote/FawkesRemotePage.test.tsx`
- Create: `backend/app/protocol/rate_limits.py`
- Modify: `backend/app/protocol/dispatcher.py`
- Modify: `backend/tests/test_ws.py`

**Interfaces:**
- `useStoredDevice` owns only credential load/save/clear.
- `useCommandFeedback` owns current request correlation, active action and
  honest success/error reset timers.
- `rate_limits.py` owns the existing fixed message/navigation limiter setup;
  dispatcher behavior and public protocol remain unchanged.

- [ ] **Step 1: Write characterization tests**

Capture existing credential lifecycle, stale request rejection, timeout cleanup
and reset-input behavior before extraction.

- [ ] **Step 2: Extract one responsibility at a time**

Move credentials, run tests, then move feedback, run tests, then move limiter
construction, run tests. Do not combine with behavior changes.

- [ ] **Step 3: Verify and commit**

Run full suites/lint/build/compile and commit as
`refactor: isolate remote session responsibilities`.

### Task 7: Integration, security and UX audit loop

**Files:**
- Modify tests adjacent to any finding.
- Modify implementation only after a reproducing test.
- Modify: `docs/FINALIZATION_LOOP.md`

**Interfaces:**
- Produces no new public capability; closes audit findings.

- [ ] **Step 1: Add/strengthen vertical integration tests**

Cover PAIR -> AUTH -> platform/media/volume/navigation/input -> RESULT, rate
limit, reconnect-level context continuity and local resolver fake -> existing
adapter -> RESULT.

- [ ] **Step 2: Security review and fixes**

Audit request IDs, auth transitions, origin behavior, rate-limit separation,
input release, context isolation, prompt injection, URL construction, token/PIN
logging and exception boundaries. Every fix starts with RED.

- [ ] **Step 3: UX review and fixes**

Review 390x844, 393x852, 430x932 and narrow desktop through automated browser
screenshots when a browser runtime is available. Otherwise validate CSS media
queries and component DOM, and leave screenshot/iPhone approval explicitly
external.

- [ ] **Step 4: Scope/dead-code review**

Remove the absorbed Navigation screen, stale docs/comments, unused imports,
resolved work markers and incomplete exposed experiments without removing compatibility.

- [ ] **Step 5: Full regression**

Run frontend tests/lint/build, backend tests/compile, `git diff --check` and
`git status --short`. Update the ledger and commit audit fixes coherently.

### Task 8: Truthful final documentation and delivery

**Files:**
- Modify: `README.md`
- Modify: `docs/TESTING.md`
- Modify: `docs/PROTOCOL.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/SECURITY.md`
- Modify: `docs/FINALIZATION_LOOP.md`
- Create: `docs/FINAL_VALIDATION.md`

**Interfaces:**
- Produces setup, Ollama configuration/fallback, exact test commands/counts,
  known warnings and physical validation checklist matching the code.

- [ ] **Step 1: Reconcile documentation with implementation**

Document Netflix/Prime search, integrated D-pad, deterministic fast path,
optional Ollama, offline behavior, context TTL and all real limitations.

- [ ] **Step 2: Execute fresh final gates**

Run every command again in the final working tree. Do not reuse earlier output.

- [ ] **Step 3: Write `FINAL_VALIDATION.md` from evidence**

Include base/branch, architecture, functions, local AI/model status, counts,
warnings, security review, automated visual status and physical tests pending.

- [ ] **Step 4: Commit, push and open PR without merging**

Commit as `docs: record final ControlFawkes validation`, push
`feat/controlfawkes-final`, and open a PR to `main` containing actual results
and only the unavoidable physical approval item.
