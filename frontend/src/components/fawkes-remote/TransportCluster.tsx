import React from 'react';
import { ArrowLeft, Expand, Minimize2, Play, RotateCcw, RotateCw } from 'lucide-react';

const MAIN_CONTROLS = [
  { label: 'Voltar 15 segundos', Icon: RotateCcw, text: '15s' },
  { label: 'Play ou pausa', Icon: Play, primary: true },
  { label: 'Avançar 15 segundos', Icon: RotateCw, text: '15s' },
];

const UTILITY_CONTROLS = [
  { label: 'Tela cheia', Icon: Expand, text: 'Tela cheia' },
  { label: 'Sair da tela cheia', Icon: Minimize2, text: 'Sair' },
  { label: 'Voltar', Icon: ArrowLeft, text: 'Voltar' },
];

export const TransportCluster: React.FC = () => (
  <section className="transport-cluster" aria-label="Controles do player">
    <div className="transport-cluster__main-row">
      {MAIN_CONTROLS.map(({ label, Icon, primary, text }) => (
        <button
          key={label}
          className={primary ? 'transport-cluster__primary' : 'transport-cluster__side'}
          type="button"
          aria-label={label}
          aria-disabled="true"
          disabled
        >
          <Icon aria-hidden="true" />
          {text && <span>{text}</span>}
        </button>
      ))}
    </div>
    <div className="transport-cluster__utility-row">
      {UTILITY_CONTROLS.map(({ label, Icon, text }) => (
        <button key={label} type="button" aria-label={label} aria-disabled="true" disabled>
          <Icon aria-hidden="true" />
          <span>{text}</span>
        </button>
      ))}
    </div>
    <p className="transport-cluster__availability">
      Player disponível após conexão com o navegador
    </p>
  </section>
);
