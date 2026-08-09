# ControlFawkes final validation

Date: 2026-08-09

Branch: `feat/controlfawkes-final`

## Outcome

All code-realizable finalization work is complete. The Phase 2A history was
preserved, its capabilities were audited, and the final branch adds a unified
Control experience, a deterministic media/volume fast path, optional local
intent interpretation and focused orchestration boundaries. No known blocking
code defect remains.

The only product approval still external is use on a physical iPhone and the
real Windows applications/hardware it controls.

## Verified product path

```text
iPhone UI
  -> authenticated WebSocket protocol
    -> deterministic parser
      -> closed policy/schema
        -> existing Windows adapter

unknown text only
  -> short same-device context
    -> optional loopback Ollama resolver
      -> strict and grounded intent
        -> the same closed policy/handler/adapter
```

There is no cloud AI, shell, PowerShell, arbitrary URL, arbitrary key or model
executor. Missing model, offline Ollama, timeout, malformed JSON, extra fields,
hallucinated enum, ungrounded platform and unexpected resolver exceptions all
preserve `UNKNOWN_COMMAND` without affecting closed controls.

## Fresh evidence

- Frontend: 21 test files and 163 tests passed.
- Frontend lint: passed.
- Frontend production build: passed.
- Production bundle: 775.34 kB JS (208.98 kB gzip); known >500 kB warning.
- Backend: 429 tests passed.
- Python compileall: passed.
- Python dependency consistency: `pip check` passed.
- npm advisory cache: `npm audit --omit=dev --offline` reported 0.
- Backend warning: one upstream Starlette TestClient deprecation.
- Diff whitespace check: passed after final documentation.

The online npm advisory refresh was not run: the approval gate rejected sending
the project's dependency metadata to the public npm registry without specific
authorization. The offline result is not presented as a current online audit.

## Local AI validation

Ollama was reachable on loopback. Installed models included `qwen2.5:3b`,
`qwen2.5:7b`, `llama3.2:3b` and others; no model was downloaded. Health passed
for `qwen2.5:3b`. A contextual phrase produced a strict `SEARCH_MEDIA` intent
when the warm model completed within the configured timeout. Cold/slow and
ungrounded runs returned `None`, which is the designed safe fallback.

CI uses mocks and does not require Ollama or a model.

## Audit conclusions

- Security: authentication, origin checks, size/schema validation, rate limits,
  token hashing/revocation, URL construction and input failsafes remain intact.
- Local AI: loopback-only, no credentials, no telemetry, strict output, bounded
  volatile context and deterministic bypass are covered by tests.
- UX: Control now makes the D-pad dominant, play/pause prominent, volume a
  one-tap action, secondary controls subordinate and tools directly reachable.
- Accessibility: native keyboard click, focus-visible, 44px targets, live/error
  honesty, safe areas and reduced motion are represented in code/tests.
- Architecture: credential lifecycle, request feedback and limiter construction
  have focused owners; duplicate Navigation code and styles were removed.

## External physical approval checklist

Run the 20 steps in `docs/TESTING.md` on the actual iPhone/Windows setup. Pay
particular attention to 390–430 px layouts, safe areas, press-and-hold arrows,
virtual keyboard behavior, real app focus, Core Audio scope/fallback, Wi-Fi
reconnect and honest adapter errors. No screenshot or physical-device success
is claimed by this document.
