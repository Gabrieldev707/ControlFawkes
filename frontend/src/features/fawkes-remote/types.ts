// Connection State
export type ConnectionState =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'error';

export type AuthState =
  | 'checking'
  | 'pairing_required'
  | 'pairing'
  | 'authenticated'
  | 'rejected';

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
    deviceId: string;
    token: string;
  };
}

export interface PairDeviceMessage {
  type: 'PAIR_DEVICE';
  requestId: string;
  payload: {
    pin: string;
    deviceName: string;
  };
}

export interface VolumeGetMessage {
  type: 'VOLUME_GET';
  requestId: string;
  payload: Record<string, never>;
}

export interface VolumeSetMessage {
  type: 'VOLUME_SET';
  requestId: string;
  payload: {
    level: number;
  };
}

export interface VolumeStepMessage {
  type: 'VOLUME_STEP';
  requestId: string;
  payload: {
    delta: -5 | 5;
  };
}

export interface VolumeToggleMuteMessage {
  type: 'VOLUME_TOGGLE_MUTE';
  requestId: string;
  payload: Record<string, never>;
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
  | PairDeviceMessage
  | VolumeGetMessage
  | VolumeSetMessage
  | VolumeStepMessage
  | VolumeToggleMuteMessage
  | PlatformSelectedMessage
  | TextCommandMessage;

// -----------------------------------------------------------------------------
// Server Protocol (Sent by Backend)
// -----------------------------------------------------------------------------
export interface AuthRequiredMessage {
  type: 'AUTH_REQUIRED';
}

export interface AuthResultMessage {
  type: 'AUTH_RESULT';
  requestId: string;
  success: boolean;
  deviceId?: string;
  message: string;
}

export interface PairResultMessage {
  type: 'PAIR_RESULT';
  requestId: string;
  success: boolean;
  deviceId?: string;
  token?: string;
  message: string;
}

export interface VolumeStateMessage {
  type: 'VOLUME_STATE';
  requestId: string;
  level: number;
  muted: boolean;
}

export interface StateUpdateMessage {
  type: 'STATE_UPDATE';
  state: ConnectionState;
}

export interface CommandResultMessage {
  type: 'COMMAND_RESULT';
  requestId: string;
  success: boolean;
  message: string;
  data?: unknown;
}

export interface ErrorMessage {
  type: 'ERROR';
  requestId: string;
  code: string;
  message: string;
}

export type ServerMessage =
  | AuthRequiredMessage
  | AuthResultMessage
  | PairResultMessage
  | VolumeStateMessage
  | StateUpdateMessage
  | CommandResultMessage
  | ErrorMessage;
