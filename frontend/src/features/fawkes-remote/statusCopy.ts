import type { AuthState, ConnectionState, OrbState, Platform } from './types';

const PLATFORM_NAMES: Record<Platform, string> = {
  NETFLIX: 'Netflix',
  MAX: 'HBO Max',
  PRIME_VIDEO: 'Prime Video',
  DISNEY_PLUS: 'Disney+',
  YOUTUBE: 'YouTube',
  SPOTIFY: 'Spotify',
};

interface RemoteStatusInput {
  connectionState: ConnectionState;
  authState: AuthState;
  orbState: OrbState;
  selectedPlatform: Platform | null;
}

export function getRemoteStatusCopy({
  connectionState,
  authState,
  orbState,
  selectedPlatform,
}: RemoteStatusInput): string {
  if (connectionState === 'disconnected' || connectionState === 'error') {
    return 'Computador desconectado';
  }
  if (connectionState === 'connecting') return 'Conectando ao computador…';

  if (authState === 'pairing_required' || authState === 'rejected') {
    return 'Pareamento necessário';
  }
  if (authState === 'checking') return 'Autenticando…';
  if (authState === 'pairing') return 'Pareando dispositivo…';

  const platformName = selectedPlatform ? PLATFORM_NAMES[selectedPlatform] : null;
  if (orbState === 'executing') {
    return platformName ? `Selecionando ${platformName}…` : 'Executando comando…';
  }
  if (orbState === 'success') {
    return platformName ? `${platformName} selecionada` : 'Comando concluído';
  }
  if (orbState === 'error') {
    return platformName ? `Não foi possível selecionar ${platformName}` : 'Não foi possível concluir o comando';
  }
  if (orbState === 'listening') return 'Ouvindo…';
  if (orbState === 'transcribing') return 'Transcrevendo…';
  if (orbState === 'needs_selection') return 'Escolha uma opção';
  return 'Aguardando um comando';
}
