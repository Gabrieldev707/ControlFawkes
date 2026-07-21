import type { ServerMessage } from './types';

export function isServerMessage(data: unknown): data is ServerMessage {
  if (typeof data !== 'object' || data === null) return false;

  const msg = data as Record<string, unknown>;
  const type = msg.type;

  if (type === 'STATE_UPDATE') {
    return ['disconnected', 'connecting', 'connected', 'error'].includes(msg.state as string);
  }

  if (type === 'COMMAND_RESULT') {
    return typeof msg.requestId === 'string' &&
           typeof msg.success === 'boolean' &&
           typeof msg.message === 'string';
  }

  if (type === 'ERROR') {
    return typeof msg.requestId === 'string' &&
           typeof msg.code === 'string' &&
           typeof msg.message === 'string';
  }

  if (type === 'AUTH_REQUIRED') {
    return true;
  }

  if (type === 'AUTH_RESULT') {
    return typeof msg.requestId === 'string' &&
           typeof msg.success === 'boolean' &&
           typeof msg.message === 'string';
  }

  if (type === 'PAIR_RESULT') {
    return typeof msg.requestId === 'string' &&
           typeof msg.success === 'boolean' &&
           typeof msg.message === 'string';
  }

  if (type === 'VOLUME_STATE') {
    return typeof msg.requestId === 'string' &&
           typeof msg.level === 'number' &&
           typeof msg.muted === 'boolean';
  }

  return false;
}

export function parseServerMessage(raw: string): ServerMessage | null {
  if (raw.length > 8192) return null; // 8KB limit

  try {
    const data = JSON.parse(raw);
    if (isServerMessage(data)) {
      return data;
    }
    return null;
  } catch {
    return null;
  }
}
