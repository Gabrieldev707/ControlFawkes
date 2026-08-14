import React from 'react';
import type { ConnectionState } from '../../features/fawkes-remote/types';

/**
 * Estado da conexão sem crachá.
 *
 * O selo "Conectado" ocupava o canto o tempo todo para dizer a coisa menos
 * interessante que existe: que está tudo normal. Aqui o normal é um ponto
 * discreto, e o texto só aparece quando há algo a resolver — que é quando
 * alguém realmente olha para esse canto.
 */

const LABELS: Record<ConnectionState, string> = {
  connected: 'Conectado',
  connecting: 'Conectando',
  reconnecting: 'Reconectando',
  disconnected: 'Sem conexão',
  error: 'Falha na conexão',
};

/** Segundos até a próxima tentativa, arredondados para cima. */
function segundosAte(instante: number | null): number | null {
  if (instante === null) return null;
  const restante = Math.ceil((instante - Date.now()) / 1000);
  return restante > 0 ? restante : null;
}

export const ConnectionStatus: React.FC<{
  state: ConnectionState;
  /** Quando a próxima tentativa acontece, para a espera não ser um mistério. */
  nextRetryAt?: number | null;
}> = ({ state, nextRetryAt = null }) => {
  const [restante, setRestante] = React.useState(() => segundosAte(nextRetryAt));

  React.useEffect(() => {
    setRestante(segundosAte(nextRetryAt));
    if (nextRetryAt === null) return;
    const timer = window.setInterval(() => setRestante(segundosAte(nextRetryAt)), 500);
    return () => window.clearInterval(timer);
  }, [nextRetryAt]);

  // "Sem conexão" sozinho não diz se algo ainda vai acontecer. Com a contagem,
  // dá para esperar sabendo que há uma tentativa a caminho — ou desistir.
  const rotulo = restante !== null && state !== 'connected'
    ? `${LABELS[state]} · ${restante}s`
    : LABELS[state];

  return (
    <div className="connection-mark" data-state={state}>
      <span className="connection-mark__dot" aria-hidden="true" />
      {/* O rótulo continua no acessível mesmo quando não está desenhado: quem
          usa leitor de tela não pode depender de perceber a cor de um ponto. */}
      <span className={state === 'connected' ? 'visually-hidden' : 'connection-mark__label'}>
        {rotulo}
      </span>
    </div>
  );
};
