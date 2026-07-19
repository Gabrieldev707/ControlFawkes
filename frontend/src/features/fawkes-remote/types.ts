// Connection State
export type ConnectionState =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'error';

// Orb Visual State
export type OrbState =
  | 'idle'
  | 'listening'
  | 'transcribing'
  | 'needs_selection'
  | 'executing'
  | 'success'
  | 'error';

// Platforms
export const PLATFORMS = [
  'NETFLIX',
  'MAX',
  'PRIME_VIDEO',
  'DISNEY_PLUS',
  'YOUTUBE',
  'SPOTIFY',
] as const;

export type Platform = (typeof PLATFORMS)[number];

export function isPlatform(value: unknown): value is Platform {
  return (
    typeof value === 'string' &&
    PLATFORMS.includes(value as Platform)
  );
}

// -----------------------------------------------------------------------------
// Client Protocol (Sent by Frontend)
// -----------------------------------------------------------------------------
export interface AuthMessage {
  type: 'AUTH';
  requestId: string;
  payload: {
    token: string;
  };
}

export interface PlatformSelectedMessage {
  type: 'PLATFORM_SELECTED';
  requestId: string;
  payload: {
    platform: Platform;
  };
}

export interface TextCommandMessage {
  type: 'TEXT_COMMAND';
  requestId: string;
  payload: {
    query: string;
  };
}

export type ClientMessage =
  | AuthMessage
  | PlatformSelectedMessage
  | TextCommandMessage;

// -----------------------------------------------------------------------------
// Server Protocol (Sent by Backend)
// -----------------------------------------------------------------------------
export interface StateUpdateMessage {
  type: 'STATE_UPDATE';
  state: ConnectionState; // Ou outro estado interno do servidor
}

export interface CommandResultMessage {
  type: 'COMMAND_RESULT';
  requestId: string;
  success: boolean;
  message: string;
  data?: any;
}

export interface ErrorMessage {
  type: 'ERROR';
  requestId: string;
  code: string;
  message: string;
}

export type ServerMessage =
  | StateUpdateMessage
  | CommandResultMessage
  | ErrorMessage;
