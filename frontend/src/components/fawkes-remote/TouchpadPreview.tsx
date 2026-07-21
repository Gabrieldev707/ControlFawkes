import React from 'react';
import { CornerDownLeft, Keyboard, X } from 'lucide-react';
import './TouchpadPreview.css';

export const TouchpadPreview: React.FC = () => (
  <div className="touchpad-view">
    <header className="view-heading touchpad-view__heading">
      <span className="control-eyebrow">Entrada remota</span>
      <h1>Touchpad</h1>
      <p className="control-availability">Disponível no Bloco B — Input e touchpad</p>
    </header>
    <section
      className="touchpad-surface"
      data-testid="touchpad-surface"
      aria-disabled="true"
      aria-label="Área de gesto do touchpad — preview sem envio"
    >
      <div
        className="touchpad-orientation-lines"
        data-testid="touchpad-orientation-lines"
        aria-hidden="true"
      />

      {(['top-left', 'top-right', 'bottom-left', 'bottom-right'] as const).map((corner) => (
        <span
          key={corner}
          className={`touchpad-corner-mark touchpad-corner-mark--${corner}`}
          data-testid="touchpad-corner-mark"
          aria-hidden="true"
        />
      ))}

      <div className="touchpad-core" data-testid="touchpad-core" aria-hidden="true">
        <span className="touchpad-core__ring" />
        <span className="touchpad-core__point" />
      </div>

      <div className="touchpad-surface__copy">
        <span>Área de gesto</span>
        <small>Preview — sem envio</small>
      </div>
    </section>
    <div className="touchpad-preview-actions" aria-label="Ações futuras do touchpad">
      <button type="button" disabled aria-disabled="true">
        <CornerDownLeft aria-hidden="true" />
        <span>Enter</span>
      </button>
      <button type="button" disabled aria-disabled="true">
        <X aria-hidden="true" />
        <span>Esc</span>
      </button>
      <button type="button" disabled aria-disabled="true">
        <Keyboard aria-hidden="true" />
        <span>Teclado</span>
      </button>
    </div>
  </div>
);
