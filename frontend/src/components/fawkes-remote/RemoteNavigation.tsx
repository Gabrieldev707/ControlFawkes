import React from 'react';
import { House, MousePointer2, SlidersHorizontal } from 'lucide-react';

export type RemoteView = 'home' | 'control' | 'touchpad';

interface RemoteNavigationProps {
  currentView: RemoteView;
  onNavigate: (view: RemoteView) => void;
}

const ITEMS = [
  { view: 'home' as const, label: 'Início', Icon: House },
  { view: 'control' as const, label: 'Controle', Icon: SlidersHorizontal },
  { view: 'touchpad' as const, label: 'Touchpad', Icon: MousePointer2 },
];

export const RemoteNavigation: React.FC<RemoteNavigationProps> = ({ currentView, onNavigate }) => (
  <nav className="remote-navigation" aria-label="Navegação do controle">
    {ITEMS.map(({ view, label, Icon }) => (
      <button
        key={view}
        type="button"
        className={currentView === view ? 'is-current' : ''}
        aria-current={currentView === view ? 'page' : undefined}
        onClick={() => onNavigate(view)}
      >
        <Icon aria-hidden="true" />
        <span>{label}</span>
      </button>
    ))}
  </nav>
);
