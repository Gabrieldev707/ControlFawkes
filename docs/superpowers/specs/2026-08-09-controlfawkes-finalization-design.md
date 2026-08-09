# ControlFawkes finalization design

Date: 2026-08-09

Status: approved by the attached finalization directive

## Product thesis

ControlFawkes is a local, iPhone-first remote for a Windows computer. The main
surface must look and behave like a premium remote, not like a dashboard or a
chatbot. Deterministic commands remain the product; local AI is an optional
interpreter used only after deterministic parsing fails.

## Architecture

The existing Phase 2A protocol, dispatcher and Windows adapters remain the
authority. A command follows one of two paths:

```text
known input -> deterministic parser -> policy/schema -> existing handler -> adapter

unknown input -> device context -> optional local resolver -> strict intent schema
              -> policy/schema -> existing handler -> adapter
```

The local resolver cannot emit URLs, keys, pointer deltas, shell text or an
open-ended action. It selects only existing protocol intents. Invalid JSON,
extra fields, unsupported values, timeout, disabled AI, missing model and an
offline Ollama all resolve to the existing honest `UNKNOWN_COMMAND` error.

Short-lived context is keyed by authenticated `deviceId`, never by WebSocket.
It stores only the last platform, query, action and timestamp in memory, with a
10-minute TTL and a 32-device bound. Reconnect therefore preserves useful
context while restart and expiry clear it predictably.

## Control screen

The separate Navigation destination is absorbed into Control. Its tested
press-and-hold behavior is preserved in a focused `DPadControl` component.

```text
+--------------------------------------+
| <  CONTROLFAWKES       ready / device|
|      Player/platform status          |
|                                      |
|              [  UP  ]                |
|          [ L ][  OK  ][ R ]          |
|              [ DOWN ]                |
|           [back]       [menu]*       |
|                                      |
|       [previous] [ PLAY ] [next]     |
|                                      |
|         [ - ] [ mute ] [ + ]  42%   |
|                                      |
|     -10s  +10s  fullscreen  exit     |
|                                      |
|        [ Touchpad ] [ Keyboard ]      |
+--------------------------------------+

* No unsupported HOME/menu action is added; the slot remains absent.
```

The status/header stays compact. The D-pad is the visual nucleus, play/pause is
the strongest action, volume is one tap away, and tools are accessible without
competing with the core. There is no optimistic success: active/loading state
tracks the request and server response already used by the controller.

## Visual system

Subject: a handheld Windows media remote with Fawkes' cosmic/ember identity.
Audience: one person using an iPhone, often one-handed and in a dark room.
Single job: control the active computer/player quickly and confidently.

Palette:

- Void `#050508`: app background.
- Obsidian `#101018`: hardware surface.
- Plasma violet `#7C3AED`: focus and primary action.
- Ion cyan `#22D3EE`: live/connected state.
- Ember gold `#F6C85F`: D-pad center signature and confirmed emphasis.
- Signal red `#F87171`: honest failure/destructive warning.

Typography:

- Syncopate: restrained product mark only.
- system UI (`-apple-system`, Segoe UI): controls and readable copy.
- UI monospace: compact live values such as volume and latency.

Signature: an ember-lit OK key inside a quiet concentric D-pad, echoing the
orb without placing a heavy WebGL canvas in the hot control path. The aesthetic
risk is physical-control geometry instead of card-based sections; surrounding
elements remain restrained.

The UI preserves visible focus, at least 44px tap targets, safe-area insets and
`prefers-reduced-motion`. No new font, animation or component dependency is
introduced.

## Component boundaries

- `DPadControl`: pointer/keyboard accessible directional actions and safe hold
  repetition. It has no transport or socket knowledge.
- `RemoteControlScreen`: presentation and callbacks for navigation, media,
  volume and tools. It does not build protocol messages.
- `FawkesRemotePage`: session orchestration until focused hooks are extracted;
  it maps callbacks to the existing closed client protocol.
- `DeviceContextStore`: bounded volatile context keyed by device.
- `LocalIntentResolver`: small async interface.
- `OllamaIntentResolver`: localhost-only HTTP implementation with a short
  timeout and strict response parsing.
- `IntentFallbackService`: calls the resolver only for `UnknownIntent`, applies
  policy, and returns existing deterministic intent types.

## Failure behavior

- Socket unavailable: existing disconnected/disabled UI and reconnect path.
- Adapter failure: existing typed `ERROR`, no success state.
- Local model unavailable/slow/invalid: `UNKNOWN_COMMAND` without a crash or a
  long control-path delay.
- Hallucinated or injected action: schema/policy rejection before dispatcher.
- Device context expired: resolve without context or return `UNKNOWN_COMMAND`.
- Held input interrupted: existing reset/release paths remain authoritative.

## Test strategy

TDD is required for each behavior change. Frontend coverage exercises groups,
callbacks, disabled/active/error states, D-pad repeat cancellation, mute,
play/pause and tool navigation without asserting fragile CSS. Backend coverage
proves deterministic bypass, strict local intent parsing, forbidden extra
fields/actions, timeout/offline/malformed fallback, device isolation/expiry and
the vertical authenticated result path. Final gates are frontend tests/lint/
build, backend tests/compile, diff check and responsive review.

## Scope exclusions

No cloud AI, shell, arbitrary URL, generic browser automation, accounts,
remote database, RAG, embeddings, plugins, login automation or TV control is
added. A local model is not downloaded automatically.
