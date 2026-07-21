import { describe, expect, it } from 'vitest';
import { getRemoteStatusCopy } from './statusCopy';

const base = {
  connectionState: 'connected' as const,
  authState: 'authenticated' as const,
  orbState: 'idle' as const,
  selectedPlatform: null,
};

describe('getRemoteStatusCopy', () => {
  it('prioriza conexão e autenticação antes do estado da orb', () => {
    expect(getRemoteStatusCopy({ ...base, connectionState: 'disconnected', orbState: 'success' })).toBe('Computador desconectado');
    expect(getRemoteStatusCopy({ ...base, connectionState: 'connecting' })).toBe('Conectando ao computador…');
    expect(getRemoteStatusCopy({ ...base, authState: 'pairing_required' })).toBe('Pareamento necessário');
    expect(getRemoteStatusCopy({ ...base, authState: 'checking' })).toBe('Autenticando…');
  });

  it('usa linguagem verdadeira ao selecionar uma plataforma', () => {
    expect(getRemoteStatusCopy({ ...base, orbState: 'executing', selectedPlatform: 'NETFLIX' })).toBe('Selecionando Netflix…');
    expect(getRemoteStatusCopy({ ...base, orbState: 'success', selectedPlatform: 'NETFLIX' })).toBe('Netflix selecionada');
    expect(getRemoteStatusCopy({ ...base, orbState: 'error', selectedPlatform: 'NETFLIX' })).toBe('Não foi possível selecionar Netflix');
  });

  it('descreve estados operacionais sem sugerir sucesso antecipado', () => {
    expect(getRemoteStatusCopy(base)).toBe('Aguardando um comando');
    expect(getRemoteStatusCopy({ ...base, orbState: 'listening' })).toBe('Ouvindo…');
    expect(getRemoteStatusCopy({ ...base, orbState: 'transcribing' })).toBe('Transcrevendo…');
    expect(getRemoteStatusCopy({ ...base, orbState: 'needs_selection' })).toBe('Escolha uma opção');
  });
});
