import { describe, expect, it } from 'vitest'

import { isErrorCode, isServerMessage, parseServerMessage } from './protocol'


describe('protocol v1 runtime validation', () => {
  it('accepts a complete state update', () => {
    expect(isServerMessage({
      protocolVersion: 1,
      type: 'STATE_UPDATE',
      state: 'AUTH_REQUIRED',
      message: 'Autenticação necessária.',
    })).toBe(true)
  })

  it('rejects a protocol version mismatch', () => {
    expect(isServerMessage({
      protocolVersion: 2,
      type: 'STATE_UPDATE',
      state: 'AUTH_REQUIRED',
      message: 'Autenticação necessária.',
    })).toBe(false)
  })

  it('rejects a boolean protocol version and accepts numeric one', () => {
    expect(isServerMessage({
      protocolVersion: true,
      type: 'AUTH_RESULT',
      requestId: 'auth-1',
      success: true,
      message: 'Autenticado.',
    })).toBe(false)
    expect(isServerMessage({
      protocolVersion: 1.0,
      type: 'AUTH_RESULT',
      requestId: 'auth-1',
      success: true,
      message: 'Autenticado.',
    })).toBe(true)
  })

  it('accepts pairing and authentication results', () => {
    expect(isServerMessage({
      protocolVersion: 1,
      type: 'PAIR_RESULT',
      requestId: 'pair-1',
      success: true,
      message: 'Pareamento concluído.',
      deviceId: 'device-1',
      token: 'a-secure-token-value',
    })).toBe(true)
    expect(isServerMessage({
      protocolVersion: 1,
      type: 'AUTH_RESULT',
      requestId: 'auth-1',
      success: true,
      message: 'Autenticação concluída.',
    })).toBe(true)
  })

  it('accepts typed help command data', () => {
    expect(isServerMessage({
      protocolVersion: 1,
      type: 'COMMAND_RESULT',
      requestId: 'text-1',
      success: true,
      message: 'Estes são os comandos disponíveis.',
      data: {
        intent: 'SHOW_HELP',
        commands: ['abre netflix'],
        executed: false,
      },
    })).toBe(true)
  })

  it('accepts a platform result that confirms real execution', () => {
    expect(isServerMessage({
      protocolVersion: 1,
      type: 'COMMAND_RESULT',
      requestId: 'platform-1',
      success: true,
      message: 'Spotify aberto.',
      data: {
        intent: 'OPEN_PLATFORM',
        platform: 'SPOTIFY',
        executed: true,
        strategy: 'SPOTIFY_APP',
      },
    })).toBe(true)
  })

  it('rejects platform success without a known launch strategy', () => {
    const base = {
      protocolVersion: 1,
      type: 'COMMAND_RESULT',
      requestId: 'platform-1',
      success: true,
      message: 'Spotify aberto.',
    }

    expect(isServerMessage({
      ...base,
      data: { intent: 'OPEN_PLATFORM', platform: 'SPOTIFY', executed: true },
    })).toBe(false)
    expect(isServerMessage({
      ...base,
      data: {
        intent: 'OPEN_PLATFORM',
        platform: 'SPOTIFY',
        executed: true,
        strategy: 'DEFAULT_BROWSER',
      },
    })).toBe(false)
  })

  it('accepts a structured media-search result for supported platforms', () => {
    expect(isServerMessage({
      protocolVersion: 1,
      type: 'COMMAND_RESULT',
      requestId: 'search-1',
      success: true,
      message: 'Pesquisa aberta no YouTube.',
      data: {
        intent: 'SEARCH_MEDIA',
        platform: 'YOUTUBE',
        executed: true,
        strategy: 'CHROME',
      },
    })).toBe(true)
  })

  it('accepts an allowlisted media-control result', () => {
    expect(isServerMessage({
      protocolVersion: 1,
      type: 'COMMAND_RESULT',
      requestId: 'media-1',
      success: true,
      message: 'Play/pause executado.',
      data: {
        intent: 'MEDIA_CONTROL',
        action: 'MEDIA_PLAY_PAUSE',
        platform: 'YOUTUBE',
        session: 'WEB',
        executed: true,
      },
    })).toBe(true)
    expect(isServerMessage({
      protocolVersion: 1,
      type: 'COMMAND_RESULT',
      requestId: 'media-2',
      success: true,
      message: 'Tecla enviada.',
      data: {
        intent: 'MEDIA_CONTROL',
        action: 'PRESS_ARBITRARY_KEY',
        platform: 'YOUTUBE',
        session: 'WEB',
        executed: true,
      },
    })).toBe(false)
    expect(isErrorCode('MEDIA_CONTROL_FAILED')).toBe(true)
    expect(isErrorCode('MEDIA_SESSION_NOT_FOUND')).toBe(true)
    expect(isErrorCode('MEDIA_ACTION_UNSUPPORTED')).toBe(true)
  })

  it('accepts the rate limiting codes sent by the backend', () => {
    // Um código conhecido só pelo backend seria descartado no parser e o
    // usuário não veria erro nenhum.
    expect(isErrorCode('RATE_LIMITED')).toBe(true)
    expect(isErrorCode('POINTER_RATE_LIMITED')).toBe(true)
    expect(isServerMessage({
      protocolVersion: 1,
      type: 'ERROR',
      requestId: 'unknown',
      code: 'RATE_LIMITED',
      message: 'Mensagens demais. Tente novamente.',
    })).toBe(true)
  })

  it('accepts only bounded real Windows volume state', () => {
    const message = {
      protocolVersion: 1,
      type: 'COMMAND_RESULT',
      requestId: 'volume-1',
      success: true,
      message: 'Volume: 42%.',
      data: {
        intent: 'SYSTEM_VOLUME',
        action: 'SYSTEM_VOLUME_GET',
        level: 42,
        muted: false,
        scope: 'GLOBAL',
        target: null,
        executed: true,
      },
    }

    expect(isServerMessage(message)).toBe(true)
    expect(isServerMessage({
      ...message,
      data: { ...message.data, level: 101 },
    })).toBe(false)
    expect(isServerMessage({
      ...message,
      data: { ...message.data, action: 'SYSTEM_VOLUME_RAW' },
    })).toBe(false)
    expect(isErrorCode('SYSTEM_VOLUME_FAILED')).toBe(true)
  })

  it('accepts only allowlisted pointer-control confirmations', () => {
    const message = {
      protocolVersion: 1,
      type: 'COMMAND_RESULT',
      requestId: 'pointer-1',
      success: true,
      message: 'Comando do touchpad executado.',
      data: {
        intent: 'POINTER_CONTROL',
        action: 'POINTER_CLICK',
        executed: true,
      },
    }

    expect(isServerMessage(message)).toBe(true)
    expect(isServerMessage({
      ...message,
      data: { ...message.data, action: 'POINTER_ABSOLUTE_MOVE' },
    })).toBe(false)
    expect(isErrorCode('POINTER_CONTROL_FAILED')).toBe(true)
    expect(isErrorCode('POINTER_RATE_LIMITED')).toBe(true)
  })

  it('accepts keyboard confirmations without text or key echoes', () => {
    const message = {
      protocolVersion: 1,
      type: 'COMMAND_RESULT',
      requestId: 'keyboard-1',
      success: true,
      message: 'Texto enviado.',
      data: {
        intent: 'KEYBOARD_CONTROL',
        action: 'KEYBOARD_TEXT',
        executed: true,
      },
    }

    expect(isServerMessage(message)).toBe(true)
    expect(isServerMessage({
      ...message,
      data: { ...message.data, text: 'não pode ecoar' },
    })).toBe(false)
    expect(isServerMessage({
      ...message,
      data: { ...message.data, action: 'KEYBOARD_SHORTCUT' },
    })).toBe(false)
    expect(isErrorCode('KEYBOARD_CONTROL_FAILED')).toBe(true)
  })

  it('accepts only the closed error-code set', () => {
    expect(isErrorCode('PIN_EXPIRED')).toBe(true)
    expect(isErrorCode('PLATFORM_OPEN_FAILED')).toBe(true)
    expect(isErrorCode('ANY_STRING')).toBe(false)
  })

  it('rejects malformed and oversized serialized messages', () => {
    expect(parseServerMessage('{broken')).toBeNull()
    expect(parseServerMessage('x'.repeat(8193))).toBeNull()
  })

  it('rejects unexpected fields', () => {
    expect(isServerMessage({
      protocolVersion: 1,
      type: 'AUTH_RESULT',
      requestId: 'auth-1',
      success: true,
      message: 'Autenticado.',
      token: 'must-not-be-here',
    })).toBe(false)
  })
})

describe('protocol v1 phase 2 additions', () => {
  it('accepts search results from every searchable platform', () => {
    for (const platform of ['NETFLIX', 'PRIME_VIDEO', 'YOUTUBE', 'SPOTIFY']) {
      expect(isServerMessage({
        protocolVersion: 1,
        type: 'COMMAND_RESULT',
        requestId: 'search-1',
        success: true,
        message: 'Pesquisa aberta.',
        data: { intent: 'SEARCH_MEDIA', platform, executed: true, strategy: 'CHROME' },
      })).toBe(true)
    }
  })

  it('rejects a search result from a platform without search', () => {
    for (const platform of ['MAX', 'DISNEY_PLUS']) {
      expect(isServerMessage({
        protocolVersion: 1,
        type: 'COMMAND_RESULT',
        requestId: 'search-1',
        success: true,
        message: 'Pesquisa aberta.',
        data: { intent: 'SEARCH_MEDIA', platform, executed: true, strategy: 'CHROME' },
      })).toBe(false)
    }
  })

  it('accepts a platform choice and rejects a malformed one', () => {
    expect(isServerMessage({
      protocolVersion: 1,
      type: 'NEEDS_PLATFORM',
      requestId: 'text-1',
      query: 'Interestelar',
      suggestedPlatforms: ['NETFLIX', 'YOUTUBE'],
    })).toBe(true)

    // Plataforma sem busca não pode ser sugerida.
    expect(isServerMessage({
      protocolVersion: 1,
      type: 'NEEDS_PLATFORM',
      requestId: 'text-1',
      query: 'Interestelar',
      suggestedPlatforms: ['MAX'],
    })).toBe(false)

    expect(isServerMessage({
      protocolVersion: 1,
      type: 'NEEDS_PLATFORM',
      requestId: 'text-1',
      query: '',
      suggestedPlatforms: ['NETFLIX'],
    })).toBe(false)
  })

  it('accepts directional results and rejects an unknown action', () => {
    expect(isServerMessage({
      protocolVersion: 1,
      type: 'COMMAND_RESULT',
      requestId: 'nav-1',
      success: true,
      message: 'Cima enviado.',
      data: { intent: 'NAVIGATION', action: 'NAVIGATE_UP', executed: true },
    })).toBe(true)

    expect(isServerMessage({
      protocolVersion: 1,
      type: 'COMMAND_RESULT',
      requestId: 'nav-1',
      success: true,
      message: 'Home enviado.',
      data: { intent: 'NAVIGATION', action: 'NAVIGATE_HOME', executed: true },
    })).toBe(false)
  })

  it('accepts the media link result', () => {
    expect(isServerMessage({
      protocolVersion: 1,
      type: 'COMMAND_RESULT',
      requestId: 'link-1',
      success: true,
      message: 'Link aberto no YouTube.',
      data: {
        intent: 'OPEN_ALLOWED_MEDIA_LINK',
        platform: 'YOUTUBE',
        executed: true,
        strategy: 'CHROME',
      },
    })).toBe(true)
  })
})

describe('NEEDS_PLATFORM com plataformas que só abrem', () => {
  const base = {
    protocolVersion: 1,
    type: 'NEEDS_PLATFORM',
    requestId: 'req-1',
    query: 'Harry Potter',
    suggestedPlatforms: ['NETFLIX', 'PRIME_VIDEO'],
  }

  it('aceita a lista de plataformas que só podem ser abertas', () => {
    const message = { ...base, openOnlyPlatforms: ['MAX', 'DISNEY_PLUS'] }

    expect(isServerMessage(message)).toBe(true)
  })

  it('continua aceitando a mensagem sem o campo novo', () => {
    // A validação recusa a mensagem inteira ao ver uma chave desconhecida;
    // exigir o campo travaria o controle contra um backend anterior.
    expect(isServerMessage(base)).toBe(true)
  })

  it('recusa uma plataforma inventada na lista de abrir', () => {
    const message = { ...base, openOnlyPlatforms: ['MAX', 'PIRATE_TV'] }

    expect(isServerMessage(message)).toBe(false)
  })

  it('continua recusando qualquer outra chave desconhecida', () => {
    const message = { ...base, redirectUrl: 'http://exemplo.com' }

    expect(isServerMessage(message)).toBe(false)
  })
})

describe('NEEDS_PLATFORM com filme e série ao mesmo tempo', () => {
  const base = {
    protocolVersion: 1,
    type: 'NEEDS_PLATFORM',
    requestId: 'req-2',
    query: 'o justiceiro',
    suggestedPlatforms: ['NETFLIX'],
  }
  const filme = {
    title: 'O Justiceiro',
    year: 2004,
    posterUrl: 'https://image.tmdb.org/t/p/w185/a.jpg',
    platforms: ['MAX'],
    kind: 'MOVIE',
  }

  it('aceita as duas leituras do mesmo nome', () => {
    const message = {
      ...base,
      availability: filme,
      availabilityAlternative: {
        title: 'Marvel - O Justiceiro',
        year: 2017,
        posterUrl: null,
        platforms: ['DISNEY_PLUS'],
        kind: 'TV',
      },
    }

    expect(isServerMessage(message)).toBe(true)
  })

  it('continua aceitando um catálogo sem o tipo', () => {
    const { kind: _kind, ...semTipo } = filme

    expect(isServerMessage({ ...base, availability: semTipo })).toBe(true)
  })

  it('recusa um tipo que a tela não sabe mostrar', () => {
    const message = { ...base, availability: { ...filme, kind: 'PODCAST' } }

    expect(isServerMessage(message)).toBe(false)
  })

  it('recusa um pôster que não é https na alternativa', () => {
    // A URL vira o `src` de uma imagem; a alternativa passa pela mesma porta.
    const message = {
      ...base,
      availability: filme,
      availabilityAlternative: { ...filme, posterUrl: 'javascript:alert(1)' },
    }

    expect(isServerMessage(message)).toBe(false)
  })
})

describe('NOW_PLAYING — o cartão de tocando agora', () => {
  const sessao = {
    title: 'Batman: Caped Crusader',
    episode: null,
    artist: null,
    app: null,
    platform: 'PRIME_VIDEO',
    playing: true,
    positionSeconds: null,
    durationSeconds: null,
    thumbnailId: null,
    posterUrl: 'https://image.tmdb.org/t/p/w342/batman.jpg',
  }

  function mensagem(overrides: Record<string, unknown> = {}) {
    return {
      protocolVersion: 1,
      type: 'NOW_PLAYING',
      session: { ...sessao, ...overrides },
    }
  }

  it('aceita a mensagem exatamente como o servidor a envia hoje', () => {
    // `hasOnlyKeys` fecha a lista de campos: um campo novo no backend que não
    // passe pelo validador derruba a mensagem INTEIRA, e o cartão fica preso
    // em "nada tocando" para sempre — sem erro na tela nem no log. Foi o que
    // aconteceu quando `episode` nasceu só do lado do servidor.
    expect(isServerMessage(mensagem())).toBe(true)
  })

  it('aceita o episódio preenchido, que é o caso de série', () => {
    expect(isServerMessage(mensagem({ episode: 'Campo dos Sonhos' }))).toBe(true)
  })

  it('aceita a sessão sem episódio nenhum, que é o caso de filme', () => {
    const { episode: _ignorado, ...semEpisodio } = sessao
    expect(isServerMessage({
      protocolVersion: 1, type: 'NOW_PLAYING', session: semEpisodio,
    })).toBe(true)
  })

  it('continua recusando campo desconhecido', () => {
    expect(isServerMessage(mensagem({ inesperado: 'x' }))).toBe(false)
  })

  it('recusa um episódio que não é texto', () => {
    expect(isServerMessage(mensagem({ episode: 42 }))).toBe(false)
  })

  it('aceita o aviso de posição travada', () => {
    expect(isServerMessage(mensagem({
      positionSeconds: 600, positionStale: true,
    }))).toBe(true)
  })

  it('aceita a sessão sem o aviso, que é como um servidor anterior responde', () => {
    const { positionStale: _ignorado, ...semAviso } = { ...sessao, positionStale: true }
    expect(isServerMessage({
      protocolVersion: 1, type: 'NOW_PLAYING', session: semAviso,
    })).toBe(true)
  })

  it('recusa um aviso de posição travada que não é booleano', () => {
    expect(isServerMessage(mensagem({ positionStale: 'sim' }))).toBe(false)
  })

  // ── A revisão do histórico ──────────────────────────────────────────────
  //
  // Um contador que o servidor incrementa a cada gravação. O celular não usa o
  // valor: quando ele MUDA, a tela de "continuar assistindo" recarrega. Antes
  // ela dependia de um relógio de sessenta segundos e de o título mudar — e
  // quem começa a assistir não muda o título, então a linha nova levava até
  // dois minutos e meio para aparecer.

  it('aceita a revisão do histórico', () => {
    expect(isServerMessage(mensagem({ historyRevision: 7 }))).toBe(true)
  })

  it('aceita zero, que é o servidor recém-iniciado', () => {
    expect(isServerMessage(mensagem({ historyRevision: 0 }))).toBe(true)
  })

  it('aceita a sessão SEM a revisão, que é como um servidor anterior responde', () => {
    expect(isServerMessage(mensagem({}))).toBe(true)
  })

  it.each([['texto', 'sim'], ['fracionado', 1.5], ['negativo', -1], ['NaN', Number.NaN]])(
    'recusa uma revisão %s',
    (_nome, valor) => {
      // Um NaN passaria por qualquer comparação e a tela pararia de recarregar
      // para sempre, sem nada acusar.
      expect(isServerMessage(mensagem({ historyRevision: valor }))).toBe(false)
    },
  )

  it('aceita "nada tocando", que precisa chegar para o cartão sumir', () => {
    expect(isServerMessage({
      protocolVersion: 1, type: 'NOW_PLAYING', session: null,
    })).toBe(true)
  })
})
