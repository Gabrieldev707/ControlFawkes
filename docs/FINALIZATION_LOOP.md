# ControlFawkes finalization ledger

Updated: 2026-08-09

Current branch: `feat/controlfawkes-final`

Current status: `CODE COMPLETE — PHYSICAL IPHONE APPROVAL PENDING`

This ledger records commands actually run in the current checkout. Historical
claims in other documents are not treated as evidence.

## Git baseline

- `main` and `origin/main`: `2c14c80`
- Phase 2A and `origin/feat/controlfawkes-phase-2-intelligence`: `92a980b`
- The initial worktree was clean on Phase 2A.
- Local ignored artifacts under `.playwright-mcp/` and `backend/data/` were
  preserved.
- `feat/controlfawkes-final` was created from `main` and fast-forwarded to the
  audited Phase 2A tip, preserving its history.

## Main baseline

| Gate | Result | Evidence |
| --- | --- | --- |
| Frontend tests | PASS after cold-start retry | 3 files, 18 tests. The first post-`npm ci` run timed out while starting three fork workers; the exact command passed after caches were warm. |
| Frontend lint | PASS | `npm run lint` exited 0. |
| Frontend build | PASS with warnings | Vite exited 0; main bundle 728.73 kB, plus plugin timing and >500 kB warnings. |
| Backend tests | PASS with warnings | 9 tests; TestClient deprecation and an unwritable pytest cache warning. |
| Python compile | PASS | `python -m compileall -q app tests`. |
| Diff check | PASS | `git diff --check`. |

### Main functional matrix

| Capability | Status | Evidence |
| --- | --- | --- |
| WebSocket envelope validation | PASS | Closed Pydantic messages, invalid JSON/payload/type tests. |
| Response/request correlation | PASS | Frontend controller tests reject stale `requestId`. |
| Reconnect lifecycle | PARTIAL | Unit-tested backoff, but no authentication or token lifecycle. |
| Platform selection | PARTIAL | Returns success without opening a platform. |
| Pairing, token, revocation, origin validation, rate limiting | FAIL | Not implemented on `main`. |
| Deterministic parser | FAIL | Function body is `pass`. |
| Platform launch/search | FAIL | No adapters. |
| Media, volume, touchpad, keyboard | FAIL | No handlers or adapters. |
| Control/Touchpad/Keyboard/Volume screens | FAIL | Not present. |
| Text and voice controls | FAIL | Visible controls have no behavior. |

## Phase 2A audit

Phase 2A adds 117 changed paths and approximately 15,863 inserted lines.

| Gate | Result | Evidence |
| --- | --- | --- |
| Frontend tests | PASS | 19 files, 154 tests pass twice through the exact `npm run test -- --run` command after applying a Windows-only persistent single-thread pool. Linux/CI keeps the default isolated parallel pool. |
| Backend tests | PASS with environment constraint | 369 tests pass with workspace-local `--basetemp` and cache disabled. The default temp directory is not writable in this sandbox. |
| Frontend lint | PASS | `npm run lint` exited 0. |
| Frontend build | PASS with warnings | Vite exited 0; bundle 774.80 kB, plus plugin timing and >500 kB warnings. |
| Python compile | PASS | `python -m compileall -q app tests`. |
| Diff check | PASS | `git diff --check`. |

### Phase 2A classification

| Area | Decision | Reason |
| --- | --- | --- |
| Protocol, schemas and request limits | KEEP | Versioned, closed, size-bounded and covered by adversarial tests. |
| Pairing, token store and revocation | KEEP | High-entropy token, hash-only persistence, constant-time comparison, PIN expiration and progressive lockout. |
| Origin and connection controls | KEEP | WebSocket origin policy, pre-auth rate limit and connection ceiling are tested. |
| Platform launch/search/link adapters | KEEP | Backend constructs allowlisted URLs; process launch uses argument arrays with no shell. |
| Media, app/global volume, pointer and keyboard adapters | KEEP | Closed action sets, real adapter return values and safe failure paths. |
| Existing screens and input state machines | KEEP | Functional coverage is broad and pointer/keyboard failsafes are present. |
| Vitest configuration | ADAPT | Standard command is not stable under concurrent workers in this Windows environment. |
| Documentation | ADAPT | `PROTOCOL.md` still says search is YouTube/Spotify-only despite Netflix/Prime support. |
| Control screen | ADAPT | It reads as stacked feature sections; directional navigation is duplicated in a separate screen and bottom nav. |
| `FawkesRemotePage.tsx` and `Dispatcher` | ADAPT | At 811 and 816 lines, respectively, they mix several responsibilities. Only focused extractions are justified. |
| Local intelligence and device context | ADAPT/ADD | Not implemented. It must remain optional, local-only and less privileged than the dispatcher. |
| Separate Navigation destination | DROP after absorption | Its D-pad behavior will move into Control; keeping the duplicate destination would add navigation without capability. |

## Finalization results

1. Control is now the primary remote surface; the duplicate Navigation route
   and screen were removed after D-pad behavior moved into a tested component.
2. Common media and volume phrases use the deterministic parser and existing
   protocol handlers before any optional inference.
3. Local inference is loopback-only, schema-closed, grounded against text or
   same-device context, bounded to 32 devices/10 minutes and fails closed.
4. Vertical authenticated tests cover deterministic bypass and local fallback
   through the existing adapter/result path.
5. Credential storage, command feedback and rate-limit construction were
   extracted into focused boundaries without changing the public protocol.
6. Documentation, security, architecture, dependency consistency and UX states
   were reconciled. No known blocking code defect remains.

## Integrated baseline after Task 1

- Frontend tests: 19 files, 154 tests, PASS twice via the standard command.
- Frontend lint: PASS.
- Frontend build: PASS; 774.80 kB main bundle, >500 kB warning remains.
- Backend tests: 369 PASS with one TestClient deprecation warning. The sandbox
  command explicitly collects `tests/` and uses a unique workspace-local temp
  directory because historical `backend/data/pytest-*` ACLs are unreadable.
- Python compile: PASS.
- Git diff check: PASS.

## Visual validation status

The local frontend and an isolated protocol mock were started successfully, but
no browser runtime was connected to the automation environment. No screenshot
or physical iPhone claim has been made. Component behavior and responsive CSS
remain automatable; final real-device review remains external.

## Fresh final gates

| Gate | Result | Evidence |
| --- | --- | --- |
| Frontend tests | PASS | 21 files, 163 tests. |
| Frontend lint | PASS | `oxlint` exited 0. |
| Frontend build | PASS with known warning | Main JS 775.34 kB; Vite reports the existing >500 kB chunk warning. |
| Backend tests | PASS with known warning | 429 tests; one Starlette TestClient deprecation warning. |
| Python compile | PASS | `python -m compileall -q app tests`. |
| Dependency consistency | PASS | `pip check`; `npm audit --offline` found 0 in local cache. |
| Online npm advisory refresh | NOT RUN | Approval gate blocked sending dependency metadata to the public registry. |
| Local Ollama | PASS / optional | Ollama health and a strict contextual resolution were exercised with installed `qwen2.5:3b`; timeout/ungrounded paths returned safe fallback. |
| Browser screenshots | UNAVAILABLE | No browser runtime is connected to the automation environment. |
| Physical iPhone | PENDING EXTERNAL | Only unavoidable remaining approval item. |
