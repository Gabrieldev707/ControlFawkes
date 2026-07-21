import React, { useState } from 'react';
import { Search, X } from 'lucide-react';

interface SearchSheetProps {
  open: boolean;
  onClose: () => void;
}

export const SearchSheet: React.FC<SearchSheetProps> = ({ open, onClose }) => {
  const [query, setQuery] = useState('');
  if (!open) return null;

  return (
    <div className="search-sheet-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <section className="search-sheet" role="dialog" aria-modal="true" aria-label="Busca digitada">
        <div className="search-sheet__handle" aria-hidden="true" />
        <header className="search-sheet__header">
          <div>
            <span className="control-eyebrow">Busca digitada</span>
            <h2 id="search-sheet-title">O que deseja procurar?</h2>
          </div>
          <button type="button" className="icon-button" aria-label="Fechar busca" onClick={onClose}><X aria-hidden="true" /></button>
        </header>
        <label className="search-sheet__field">
          <Search aria-hidden="true" />
          <span className="visually-hidden">O que deseja procurar?</span>
          <input
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label="O que deseja procurar?"
            placeholder="Harry Potter"
            autoFocus
          />
        </label>
        <p id="search-sheet-unavailable-reason" className="control-availability">
          Pesquisa disponível após conexão com o navegador
        </p>
        <div className="search-sheet__actions">
          <button type="button" className="secondary-button" onClick={onClose}>Cancelar</button>
          <button
            type="button"
            className="primary-button"
            aria-disabled="true"
            aria-describedby="search-sheet-unavailable-reason"
            disabled
          >
            Pesquisar
          </button>
        </div>
      </section>
    </div>
  );
};
