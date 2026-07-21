# ControlFawkes Phase 1.6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a versioned, authenticated, reconnecting local WebSocket foundation with deterministic text commands, honest UI feedback, CI, and independent-project documentation.

**Architecture:** FastAPI delegates strict protocol frames to an authentication-aware dispatcher backed by focused pairing and device-store services. React separates connection, server, authentication, and orb state; runtime protocol guards protect the UI from malformed frames, while one WebSocket hook owns URL resolution and reconnection lifecycle.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, pytest, React 19, TypeScript 6, Vite 8, Vitest 4, Testing Library, GitHub Actions.

## Global Constraints

- Work only on `feat/fase-1-6-foundation`, based on `4a58c1c267b44c694ccd718d4ba2ffe744c9519d`.
- Preserve `feat/windows-controls-phase-2` at `1160ded9d460b76cdf4374439084355592ab337a`.
- Do not merge, cherry-pick Phase 2, force-push, or modify `C:\Dev\OrcTech\OrcTech_v1`.
- Every protocol message contains `protocolVersion: 1`.
- No Windows, browser, voice, mouse, keyboard, volume, monitor, shutdown, restart, arbitrary URL, or shell action.
- Every `OPEN_PLATFORM` result contains `executed: false`.
- Stop a slice after three unsuccessful implement-test-correct cycles and report evidence.
- Never report a manual device test as passing without user validation.

---

### Task 1: Versioned authenticated backend protocol

**Files:**
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/security/device_store.py`
- Create: `backend/app/security/pairing.py`
- Create: `backend/app/protocol/__init__.py`
- Create: `backend/app/protocol/dispatcher.py`
- Create: `backend/scripts/manage_devices.py`
- Create: `backend/tests/test_pairing.py`
- Modify: `backend/app/schemas/ws.py`
- Modify: `backend/app/api/websocket.py`
- Modify: `backend/app/main.py`
- Modify: `backend/requirements.txt`
- Modify: `.gitignore`
- Test: `backend/tests/test_ws.py`

**Interfaces:**
- Produces: `ProtocolVersion = Literal[1]`, `ErrorCode`, strict Pydantic client/server message models, `DeviceStore`, `PairingService`, and `Dispatcher`.
- Produces: connection flow `AUTH_REQUIRED -> PAIR_DEVICE/AUTH -> READY`.
- Persists: hashed device entries in ignored `backend/data/paired_devices.json`.

- [ ] **Step 1: Write failing pairing and device-store tests**

```python
def test_pairing_issues_one_time_token(pairing):
    pin = pairing.current_pin
    result = pairing.attempt(pin, "iPhone")
    assert result.success is True
    assert pairing.attempt(pin, "other").code == "PIN_INVALID"
    assert pairing.device_store.authenticate(result.device_id, result.token)

def test_revoked_token_is_rejected(store):
    store.add("device-1", "iPhone", "raw-token")
    assert store.revoke("device-1") is True
    assert store.authenticate("device-1", "raw-token") is False
```

- [ ] **Step 2: Write failing WebSocket authentication tests**

```python
def test_connection_requires_authentication(ws):
    message = ws.receive_json()
    assert message == {
        "protocolVersion": 1,
        "type": "STATE_UPDATE",
        "state": "AUTH_REQUIRED",
        "message": "Autenticação necessária.",
    }

def test_unauthenticated_command_is_rejected(ws):
    ws.receive_json()
    ws.send_json({
        "protocolVersion": 1,
        "type": "TEXT_COMMAND",
        "requestId": "req-1",
        "payload": {"query": "ajuda"},
    })
    assert ws.receive_json()["code"] == "UNAUTHORIZED"
```

- [ ] **Step 3: Run RED tests**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_pairing.py tests/test_ws.py -q`

Expected: failures because the pairing services, protocol version, and dispatcher do not exist.

- [ ] **Step 4: Implement strict protocol and authentication services**

Use the closed `ProtocolVersion` and `ErrorCode` declarations below:

```python
ProtocolVersion = Literal[1]
ErrorCode = Literal[
    "INVALID_JSON", "INVALID_PAYLOAD", "UNSUPPORTED_MESSAGE", "NOT_IMPLEMENTED",
    "UNKNOWN_COMMAND", "UNAUTHORIZED", "INVALID_TOKEN", "PAIRING_REQUIRED",
    "PIN_INVALID", "PIN_EXPIRED", "TOO_MANY_ATTEMPTS",
    "PROTOCOL_VERSION_MISMATCH", "INTERNAL_ERROR",
]

```

Implement these exact public interfaces:

- `DeviceStore.add(device_id: str, device_name: str, token: str) -> bool` hashes and atomically stores the token.
- `DeviceStore.authenticate(device_id: str, token: str) -> bool` performs a constant-time hash comparison.
- `DeviceStore.revoke(device_id: str) -> bool` removes one device atomically.
- `DeviceStore.list_devices() -> dict[str, dict[str, str]]` omits token hashes.
- `PairingService.initialize() -> str` creates or returns the active PIN.
- `PairingService.attempt(pin: str, device_name: str) -> PairingAttempt` returns a typed success or closed failure code.
- `Dispatcher.connect(websocket: WebSocket) -> None` accepts and announces `AUTH_REQUIRED`.
- `Dispatcher.disconnect(websocket: WebSocket) -> None` removes connection authentication state.
- `Dispatcher.dispatch(websocket: WebSocket, raw: str) -> None` validates and routes one frame.

All Pydantic models use `ConfigDict(extra="forbid")`. `requestId` is 1–128 characters, PIN matches `^\d{6}$`, device name is 1–80 characters, and raw frames are limited to 8192 bytes. Device writes use `FileLock`, `tempfile.mkstemp`, `os.replace`, SHA-256, and `hmac.compare_digest`.

- [ ] **Step 5: Add local device management and ignore runtime data**

`backend/scripts/manage_devices.py` accepts `list` and `revoke DEVICE_ID`, prints no token hash, and exits nonzero when revocation misses. Add `backend/data/` to `.gitignore` and `filelock>=3.0` to requirements.

- [ ] **Step 6: Run GREEN tests and full backend regression**

Run: `cd backend && .venv\Scripts\python.exe -m pytest -q`

Expected: all authentication, protocol, and existing health/WebSocket tests pass.

- [ ] **Step 7: Review, record, and commit slice 1**

Run: `git diff --check && git diff --stat && git status --short`

Update `docs/LOOP_PROGRESS.md`, stage only Task 1 files, then commit:

```bash
git commit -m "feat: add versioned local pairing protocol"
```

### Task 2: Frontend pairing and runtime protocol

**Files:**
- Create: `frontend/vitest.config.ts`
- Create: `frontend/src/features/fawkes-remote/protocol.ts`
- Create: `frontend/src/features/fawkes-remote/protocol.test.ts`
- Create: `frontend/src/components/fawkes-remote/PairingScreen.tsx`
- Create: `frontend/src/components/fawkes-remote/PairingScreen.test.tsx`
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/tsconfig.app.json`
- Modify: `frontend/src/features/fawkes-remote/types.ts`
- Modify: `frontend/src/features/fawkes-remote/FawkesRemotePage.tsx`
- Modify: `frontend/src/components/fawkes-remote/index.ts`
- Modify: `frontend/src/styles/fawkes-remote.css`

**Interfaces:**
- Consumes: Task 1 protocol messages and state names.
- Produces: `isServerMessage(value): value is ServerMessage`, `AuthState`, pairing form, credential persistence under `controlfawkes.deviceId` and `controlfawkes.token`.

- [ ] **Step 1: Write failing closed-protocol and pairing component tests**

```tsx
expect(isServerMessage({ protocolVersion: 2, type: 'AUTH_REQUIRED' })).toBe(false)
expect(isErrorCode('PIN_EXPIRED')).toBe(true)
expect(isErrorCode('ANY_STRING')).toBe(false)

render(<PairingScreen connected onPair={onPair} pending={false} message="" />)
await user.type(screen.getByLabelText(/pin/i), '123456')
await user.click(screen.getByRole('button', { name: /parear/i }))
expect(onPair).toHaveBeenCalledWith('123456')
```

- [ ] **Step 2: Run RED frontend tests**

Run: `cd frontend && npm run test -- --run src/features/fawkes-remote/protocol.test.ts src/components/fawkes-remote/PairingScreen.test.tsx`

Expected: failure because the test script, runtime guards, and pairing component are absent.

- [ ] **Step 3: Implement closed TypeScript unions and pairing UI**

```typescript
export type ProtocolVersion = 1
export type ServerState = 'AUTH_REQUIRED' | 'PAIRING' | 'READY' | 'BUSY'
export type AuthState = 'checking' | 'pairing_required' | 'pairing' | 'authenticated' | 'rejected'
export const PROTOCOL_VERSION: ProtocolVersion = 1
```

The page sends `AUTH` once per connection when stored credentials exist, otherwise shows pairing. A successful `PAIR_RESULT` stores both values; failed authentication removes them. UI controls stay disabled until `connectionState === 'connected'`, `serverState === 'READY'`, and `authState === 'authenticated'`.

- [ ] **Step 4: Run GREEN tests, lint, and build**

Run: `cd frontend && npm run test -- --run && npm run lint && npm run build`

Expected: all frontend tests, lint, and build pass.

- [ ] **Step 5: Review, record, and commit slice 2**

Commit: `feat: add frontend pairing flow`

### Task 3: Authenticated text-command vertical slice

**Files:**
- Create: `backend/tests/test_parser.py`
- Create: `frontend/src/components/fawkes-remote/TextInput.test.tsx`
- Create: `frontend/src/components/fawkes-remote/RemoteStatusText.tsx`
- Create: `frontend/src/components/fawkes-remote/RemoteStatusText.test.tsx`
- Create: `frontend/src/features/fawkes-remote/FawkesRemotePage.test.tsx`
- Modify: `backend/app/commands/parser.py`
- Modify: `backend/app/protocol/dispatcher.py`
- Modify: `backend/app/schemas/ws.py`
- Modify: `backend/tests/test_ws.py`
- Modify: `frontend/src/components/fawkes-remote/TextInput.tsx`
- Modify: `frontend/src/components/fawkes-remote/VoiceButton.tsx`
- Modify: `frontend/src/features/fawkes-remote/FawkesRemotePage.tsx`
- Modify: `frontend/src/styles/fawkes-remote.css`

**Interfaces:**
- Produces: `parse_command(text: str) -> ParsedIntent` and authenticated `TEXT_COMMAND` results.
- Produces: `TextInput({ disabled, executing, maxLength, onSubmit })` where `onSubmit(query)` returns a boolean.

- [ ] **Step 1: Write failing parser and authenticated command tests**

```python
@pytest.mark.parametrize((text, platform), [
    ("abre netflix", "NETFLIX"), ("abre hbo max", "MAX"),
    ("abre amazon prime", "PRIME_VIDEO"), ("abre disney+", "DISNEY_PLUS"),
    ("vai pro youtube", "YOUTUBE"), ("coloca spotify", "SPOTIFY"),
])
def test_known_platform_aliases(text, platform):
    assert parse_command(text) == ParsedIntent(type="OPEN_PLATFORM", platform=platform)
```

The WebSocket test pairs first, sends `TEXT_COMMAND`, and asserts the matching request ID, user-facing message, intent, platform, and `executed is False`. Unknown commands assert `UNKNOWN_COMMAND`.

- [ ] **Step 2: Run RED backend tests**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_parser.py tests/test_ws.py -q`

Expected: parser and command result failures.

- [ ] **Step 3: Implement exact normalization and dispatch**

```python
def normalize_command(text: str) -> str:
    lowered = " ".join(text.strip().lower().split())
    return "".join(c for c in unicodedata.normalize("NFKD", lowered) if not unicodedata.combining(c))
```

Match only documented action phrases, help phrases, and aliases. Return `UNKNOWN` for all other input. Keep command length at 500 characters.

- [ ] **Step 4: Write and run RED frontend interaction tests**

Tests assert trimmed Enter submission, empty blocking, disconnected blocking, duplicate blocking, clear-on-accepted only, backend success text, backend error alert, and disabled “Em breve” microphone.

Run: `cd frontend && npm run test -- --run src/components/fawkes-remote/TextInput.test.tsx src/components/fawkes-remote/RemoteStatusText.test.tsx src/features/fawkes-remote/FawkesRemotePage.test.tsx`

- [ ] **Step 5: Implement text form and honest status lifecycle**

Use a semantic `<form onSubmit>`, labelled input, `maxLength={500}`, and submit button. Status reserves a fixed minimum height, uses `aria-live="polite"`, and uses `role="alert"` only when its `error` prop is true. The page displays backend `message` values and never replaces a failed send with success.

- [ ] **Step 6: Run all GREEN checks and commit slice 3**

Run frontend test/lint/build and backend pytest. Review diff, update loop record, and commit: `feat: add authenticated text commands`.

### Task 4: Local-network URL and continuous WebSocket reconnect

**Files:**
- Create: `frontend/src/hooks/useWebSocket.test.ts`
- Modify: `.env.example`
- Modify: `frontend/src/hooks/useWebSocket.ts`

**Interfaces:**
- Produces: `buildWebSocketUrl(configuredUrl, hostname, pageProtocol, port): string`.
- Produces: `useWebSocket({ onMessage })` with `connectionState`, `sendMessage`, and `reconnect`.

- [ ] **Step 1: Write failing URL and lifecycle tests**

```typescript
expect(buildWebSocketUrl(undefined, '192.168.0.20', 'http:', '8100'))
  .toBe('ws://192.168.0.20:8100/ws')
expect(buildWebSocketUrl('ws://10.0.0.5:9000/ws', 'ignored', 'https:', '8100'))
  .toBe('ws://10.0.0.5:9000/ws')
```

Fake-socket tests assert delays of 1000, 1500, 2250, and a 15000 cap; continued retries beyond ten attempts; immediate online/visible/manual reconnect; a single connecting socket; reset after open; and no timers, listeners, or reconnect after unmount.

- [ ] **Step 2: Run RED hook tests**

Run: `cd frontend && npm run test -- --run src/hooks/useWebSocket.test.ts`

- [ ] **Step 3: Implement URL builder and socket lifecycle**

Use `configuredUrl || generatedUrl`, an `activeRef`, identity checks for every callback, one timer ref, and removal of `maxRetries`. Immediate triggers clear pending timers before connecting.

- [ ] **Step 4: Run GREEN frontend checks and commit slice 4**

Commit: `fix: harden local websocket reconnect`.

### Task 5: CI, project documentation, and final Phase 1.6 evidence

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `docs/LOOP_PROGRESS.md`
- Modify: `README.md`
- Modify: `.gitignore`

**Interfaces:**
- Documents: setup, LAN access, pairing, commands, tests, limitations, roadmap, and manual validation.
- Automates: frontend lint/build/test and backend pytest on push and pull request.

- [ ] **Step 1: Add CI with exact required commands**

Use separate `frontend` and `backend` jobs on `ubuntu-latest`. Frontend uses `actions/checkout@v4`, `actions/setup-node@v4` with Node 22 and npm cache, then `npm ci`, lint, build, and test. Backend uses `actions/setup-python@v5` with Python 3.12, installs `backend/requirements.txt`, and runs `pytest` from `backend`.

- [ ] **Step 2: Rewrite independent-project documentation**

README sections: overview, goal, status, stack, requirements, frontend/backend installation, environment, startup, Windows IP discovery, iPhone URL, pairing, supported commands, tests, limitations, roadmap, troubleshooting, and an explicit warning that real Windows control is absent.

- [ ] **Step 3: Run fresh full verification**

```powershell
Set-Location frontend
npm run lint
npm run build
npm run test -- --run
Set-Location ..\backend
.\.venv\Scripts\python.exe -m pytest
```

Run a local FastAPI test-client check for `GET /health` and the authenticated WebSocket flow. Record LAN/iPhone validation as `MANUAL TESTS: PENDING USER VALIDATION`.

- [ ] **Step 4: Audit repository boundaries and secrets**

Run `git status`, branch/log checks, `git diff main...HEAD --stat`, a tracked-file scan for token/PIN/device-store artifacts, and confirm `git diff -- C:\Dev\OrcTech\OrcTech_v1` has no applicable path because it is outside this repository.

- [ ] **Step 5: Update loop record and commit consolidation**

Commit: `feat: complete secure phase 1.6 foundation`.

Do not create `feat/controlfawkes-loop-mvp` until the user approves the completed Phase 1.6.
