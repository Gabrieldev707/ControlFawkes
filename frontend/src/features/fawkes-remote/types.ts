export type RemoteState = 
  | 'DISCONNECTED'
  | 'CONNECTING'
  | 'CONNECTED'
  | 'LISTENING'
  | 'TRANSCRIBING'
  | 'NEEDS_SELECTION'
  | 'THINKING'
  | 'EXECUTING'
  | 'ERROR'
  | 'SUCCESS';

export interface RemoteCommand {
  type: 'REMOTE_COMMAND';
  requestId: string;
  payload: {
    action: string;
    platform?: string;
    query?: string;
    value?: number;
  };
}
