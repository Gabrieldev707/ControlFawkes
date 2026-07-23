# Protocolo WebSocket v1

## Envelope

Toda mensagem do cliente possui `protocolVersion: 1`, `type` e `requestId` de
1 a 128 caracteres. `payload` só aparece nos tipos que o exigem. Campos extras
são rejeitados. O limite serializado é 8192 bytes.

Antes de qualquer ação funcional, a conexão precisa concluir `PAIR_DEVICE` ou
`AUTH`. Estados do servidor: `AUTH_REQUIRED`, `PAIRING`, `READY` e `BUSY`.

## Mensagens do cliente

| Grupo | Tipos e payloads |
| --- | --- |
| Autenticação | `PAIR_DEVICE {pin, deviceName}`, `AUTH {deviceId, token}` |
| Comandos | `TEXT_COMMAND {query}`, `PLATFORM_SELECTED {platform}` |
| Mídia | `MEDIA_PLAY_PAUSE`, `MEDIA_PREVIOUS`, `MEDIA_NEXT`, `MEDIA_SEEK_BACK`, `MEDIA_SEEK_FORWARD`, `MEDIA_FULLSCREEN`, `MEDIA_EXIT_FULLSCREEN` |
| Volume | `SYSTEM_VOLUME_GET`, `SYSTEM_VOLUME_SET {level: 0..100}`, `SYSTEM_VOLUME_DELTA {delta: -5 ou 5}`, `SYSTEM_MUTE_TOGGLE` |
| Touchpad | `POINTER_MOVE {dx,dy: -160..160}`, `POINTER_CLICK`, `POINTER_DOUBLE_CLICK`, `POINTER_RIGHT_CLICK`, `POINTER_SCROLL {delta: -120 ou 120}`, `POINTER_DOWN`, `POINTER_UP` |
| Teclado | `KEYBOARD_TEXT {text: 1..256}`, `KEYBOARD_KEY {key}` |

Plataformas permitidas: `NETFLIX`, `MAX`, `PRIME_VIDEO`, `DISNEY_PLUS`,
`YOUTUBE` e `SPOTIFY`.

Teclas permitidas: `ENTER`, `BACKSPACE`, `ESCAPE`, `ARROW_UP`, `ARROW_DOWN`,
`ARROW_LEFT`, `ARROW_RIGHT`, `TAB` e `SPACE`.

## Respostas

- `STATE_UPDATE`: estado e mensagem do servidor.
- `AUTH_RESULT` e `PAIR_RESULT`: confirmação autenticada.
- `COMMAND_RESULT`: `success: true` e `data.executed` coerente com a ação.
- `ERROR`: código fechado e mensagem legível.

Intents de resultado: `OPEN_PLATFORM`, `SEARCH_MEDIA`, `SHOW_HELP`, `MEDIA_CONTROL`,
`SYSTEM_VOLUME`, `POINTER_CONTROL` e `KEYBOARD_CONTROL`. Resultados de teclado
não ecoam texto ou tecla.

`OPEN_PLATFORM` executado inclui `strategy`: `CHROME`, `SPOTIFY_APP` ou
`SPOTIFY_WEB_CHROME`. Ausência do aplicativo e falha do fallback retornam erro,
nunca um resultado de sucesso presumido.
`SEARCH_MEDIA` é limitado a YouTube e Spotify, inclui plataforma, execução e
estratégia, mas não devolve nem persiste o texto pesquisado.
`MEDIA_CONTROL` executado inclui `action`, a `platform` identificada e
`session: WEB | APP`. Sem plataforma ativa conhecida ou sem mapeamento para a
ação solicitada, o servidor retorna erro e não emite tecla.

## Erros funcionais

Além dos erros de JSON, autenticação, versão e payload, cada integração possui
falha própria: `PLATFORM_OPEN_FAILED`, `MEDIA_SEARCH_FAILED`, `MEDIA_CONTROL_FAILED`,
`MEDIA_SESSION_NOT_FOUND`, `MEDIA_ACTION_UNSUPPORTED`, `SYSTEM_VOLUME_FAILED`,
`POINTER_CONTROL_FAILED`, `POINTER_RATE_LIMITED` e `KEYBOARD_CONTROL_FAILED`.
