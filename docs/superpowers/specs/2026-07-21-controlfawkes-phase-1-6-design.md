# ControlFawkes Phase 1.6 Design

## Context

Phase 1.6 starts from commit `4a58c1c267b44c694ccd718d4ba2ffe744c9519d` on branch `feat/fase-1-6-foundation`. The independent `feat/windows-controls-phase-2` branch remains untouched. This phase consolidates the local-network, protocol, authentication, text-command, reconnect, CI, and documentation foundations. It deliberately does not control Windows, browsers, media playback, pointer input, keyboard input, volume, monitors, or voice.

## Architecture

The frontend remains a React/Vite mobile-first client. It owns four separate state domains: WebSocket connection, server readiness, authentication, and orb presentation. A small protocol module validates server messages at runtime and exports closed TypeScript unions. The WebSocket hook owns exactly one socket, continuous capped backoff, lifecycle listeners, and manual reconnect. The page coordinates pairing and command requests but does not infer successful execution.

The FastAPI backend delegates WebSocket frames to a dispatcher. Pydantic discriminated unions enforce protocol version, message type, request ID, payload limits, platform allowlists, and rejection of extra fields. Pairing and token persistence live outside the route. A deterministic parser recognizes only the documented aliases and never performs an operating-system or browser action.

## Protocol version 1

Every client and server message contains `protocolVersion: 1`.

Client messages:

- `PAIR_DEVICE`: `{ pin, deviceName }`
- `AUTH`: `{ deviceId, token }`
- `PLATFORM_SELECTED`: `{ platform }`
- `TEXT_COMMAND`: `{ query }`

Server messages:

- `STATE_UPDATE`: server state and a short user-facing message
- `PAIR_RESULT`: pairing result and, only on success, the new device ID and raw token
- `AUTH_RESULT`: token validation result
- `COMMAND_RESULT`: successful recognition with typed data
- `ERROR`: closed error code and user-facing message

Server states are `AUTH_REQUIRED`, `PAIRING`, `READY`, and `BUSY`. Errors use the closed set `INVALID_JSON`, `INVALID_PAYLOAD`, `UNSUPPORTED_MESSAGE`, `NOT_IMPLEMENTED`, `UNKNOWN_COMMAND`, `UNAUTHORIZED`, `INVALID_TOKEN`, `PAIRING_REQUIRED`, `PIN_INVALID`, `PIN_EXPIRED`, `TOO_MANY_ATTEMPTS`, `PROTOCOL_VERSION_MISMATCH`, and `INTERNAL_ERROR`.

An `OPEN_PLATFORM` result always contains `executed: false` in this phase. `SHOW_HELP` returns the supported command examples. Unknown input returns `UNKNOWN_COMMAND` and no success result.

## Authentication and pairing

At backend startup, the pairing service creates a cryptographically random six-digit PIN and prints it locally. The PIN expires after 300 seconds, is consumed after a successful pairing, and is invalidated after five failed attempts. A replacement PIN is generated after expiration, consumption, or exhaustion.

On connection, the server emits `AUTH_REQUIRED`. Before authentication, only `AUTH` and `PAIR_DEVICE` are accepted. Successful pairing creates a random device ID and 256-bit-equivalent URL-safe token. The raw token is returned once and stored by the frontend with its device ID. The backend stores only a SHA-256 token hash and compares hashes in constant time.

Device records are stored in `backend/data/paired_devices.json`, which is ignored by Git. Writes use a temporary file followed by atomic replacement and a file lock. A local CLI lists devices without hashes and revokes a device by ID. Revocation makes later authentication fail.

## Local network and reconnect

The default WebSocket URL is derived from `window.location.hostname`, the configured port (default `8100`), and `ws`/`wss` based on the page protocol. `VITE_WS_URL` is an optional explicit override. `window.location.host` and a default `localhost` URL are not used.

The hook reconnects indefinitely with delays `min(1000 * 1.5^attempt, 15000)`. A successful open resets the attempt count. Manual reconnect, the browser `online` event, and a transition to visible reconnect immediately when disconnected. Timers, sockets, and listeners are cleaned up on unmount. Socket identity checks prevent stale callbacks and duplicate connections.

## Frontend interaction

When pairing is required, the page presents a six-digit PIN form. Successful pairing stores credentials locally and transitions to ready. Invalid or expired PINs show the backend message. Commands remain disabled unless the socket is connected, authentication succeeded, the server is ready, and the orb is not executing.

`TextInput` submits trimmed text with Enter or its submit control, rejects empty values, enforces the shared maximum length, prevents duplicate submissions, and clears only after `sendMessage` accepts the frame. The microphone button stays visible, disabled, and labelled “Em breve”.

`RemoteStatusText` reserves vertical space, uses `aria-live="polite"`, and applies `role="alert"` for errors. It displays the last relevant backend message; local connection copy is used only for transport states such as connecting or reconnecting. Orb transitions mirror actual request lifecycle and return to idle after a short result display.

## Deterministic parser

Normalization lowercases, trims, collapses whitespace, removes accents, preserves recognition of `disney+`, and compares against explicit help phrases, action phrases, and platform aliases. It returns only `OPEN_PLATFORM`, `SHOW_HELP`, or `UNKNOWN`. It cannot accept URLs, shell commands, arbitrary platform names, or dangerous actions.

## Testing and CI

Frontend Vitest tests cover URL construction, override behavior, continuous reconnect, network/visibility recovery, unmount cleanup, protocol validation, pairing states, text submission, disabled states, and real status messages. Backend pytest tests cover strict schema validation, protocol mismatch, parser behavior, pairing expiry and attempts, token authentication and revocation, and protected WebSocket routes.

GitHub Actions runs frontend `npm ci`, lint, build, and tests, followed by backend dependency installation and pytest, on pushes and pull requests.

## Delivery slices

1. Versioned authentication protocol: strict schemas, PIN lifecycle, hashed device store, revocation CLI, authenticated WebSocket states.
2. Text command vertical slice: parser, authenticated `TEXT_COMMAND`, typed results, frontend input, and status feedback.
3. Network resilience: dynamic URL and continuous lifecycle-aware reconnection.
4. Consolidation: full test matrix, CI, README, loop record, and local manual-validation guide.

Each slice follows red-green-refactor, permits at most three correction cycles, reviews the diff, updates `docs/LOOP_PROGRESS.md`, and ends in a coherent commit. Manual iPhone checks remain explicitly pending until performed by the user.

## Risks and controls

- Fake-timer WebSocket tests can hide lifecycle races; tests assert socket counts and cleanup explicitly.
- The JSON device store can be corrupted by interrupted writes; locking and atomic replacement prevent partial writes, and malformed storage fails closed.
- Browser storage exposes the raw token to same-origin scripts; this is accepted for the local MVP, while the backend never logs or persists it in raw form.
- LAN behavior depends on the user’s firewall and Wi-Fi isolation settings; automated tests verify URL construction, while final device validation remains manual.
- Untracked artifacts from the Phase 2 checkout are not removed, staged, or used.

## Completion boundary

Phase 1.6 is complete only when all automated frontend and backend checks pass, CI and documentation exist, unauthenticated commands are rejected, pairing and revocation work, text commands return honest results, local-network URL construction avoids `localhost`, and no Phase 2 capability is present. No merge to `main` and no creation of the later MVP branch occurs until Phase 1.6 is reviewed and approved.
