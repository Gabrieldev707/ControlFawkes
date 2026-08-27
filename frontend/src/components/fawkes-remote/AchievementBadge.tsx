import type { ReactNode } from 'react'


interface AchievementBadgeProps {
  codigo: string
  conquistada: boolean
}

/**
 * O desenho de cada conquista.
 *
 * Todas dividem a mesma moldura hexagonal e a mesma medida — é isso que faz
 * doze desenhos diferentes parecerem uma coleção, e não doze ícones soltos.
 * O que muda é o miolo e a cor.
 *
 * Desenhadas à mão em SVG, e não tiradas de um pacote de ícones: uma medalha
 * de "maratona" precisa parecer uma medalha, não um relógio genérico. E em SVG
 * elas acompanham o tema e não pesam nada.
 */
const MIOLOS: Record<string, { cor: string; arte: ReactNode }> = {
  // Um botão de play dentro de um pulso: o primeiro comando que saiu daqui.
  PRIMEIRO_PLAY: {
    cor: '#8b5cf6',
    arte: (
      <>
        <path d="M28 24 L42 32 L28 40 Z" fill="currentColor" />
        <circle cx="32" cy="32" r="15" fill="none" stroke="currentColor" strokeWidth="1.6" opacity="0.45" />
      </>
    ),
  },
  // A bandeira de chegada: os créditos subiram.
  ATE_O_FIM: {
    cor: '#22d3ee',
    arte: (
      <>
        <path d="M24 20 V44" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" />
        <path d="M26 21 H41 L37 26 L41 31 H26 Z" fill="currentColor" />
        <rect x="26" y="21" width="5" height="5" fill="#0b0b12" opacity="0.55" />
        <rect x="36" y="26" width="5" height="5" fill="#0b0b12" opacity="0.55" />
      </>
    ),
  },
  // Três marcos vencidos em fila: a maratona.
  MARATONA: {
    cor: '#f6c85f',
    arte: (
      <>
        <path d="M20 40 Q26 26 32 34 Q38 42 44 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="44" cy="24" r="3.4" fill="currentColor" />
      </>
    ),
  },
  // Lua e estrela: a sessão que virou a noite.
  MADRUGADA: {
    cor: '#a78bfa',
    arte: (
      <>
        <path d="M38 20 A13 13 0 1 0 42 40 A10 10 0 1 1 38 20 Z" fill="currentColor" />
        <path d="M24 22 l1.4 3 3 1.4 -3 1.4 -1.4 3 -1.4 -3 -3 -1.4 3 -1.4 Z" fill="currentColor" opacity="0.8" />
      </>
    ),
  },
  // Duas bandeirinhas: passou por dois serviços.
  TURISTA: {
    cor: '#4ade80',
    arte: (
      <>
        <circle cx="26" cy="30" r="6" fill="none" stroke="currentColor" strokeWidth="2.4" />
        <circle cx="38" cy="36" r="6" fill="currentColor" opacity="0.55" />
      </>
    ),
  },
  // A bússola de quem foi longe.
  EXPLORADOR: {
    cor: '#38bdf8',
    arte: (
      <>
        <circle cx="32" cy="32" r="13" fill="none" stroke="currentColor" strokeWidth="2.2" />
        <path d="M27 37 L35 35 L37 27 L29 29 Z" fill="currentColor" />
      </>
    ),
  },
  // Paleta: gêneros que não se parecem.
  ECLETICO: {
    cor: '#fb7185',
    arte: (
      <>
        <path d="M32 19 a13 13 0 1 0 0 26 c2 0 3-1 3-2.5 0-2.5-3-2-3-4.5 0-2 1.6-3 4-3h2.5A8 8 0 0 0 45 27 C43.5 22 38.5 19 32 19 Z" fill="currentColor" opacity="0.85" />
        <circle cx="27" cy="27" r="2.1" fill="#0b0b12" />
        <circle cx="33" cy="24" r="2.1" fill="#0b0b12" />
        <circle cx="26" cy="34" r="2.1" fill="#0b0b12" />
      </>
    ),
  },
  // Pilha de fitas: a coleção.
  COLECIONADOR: {
    cor: '#facc15',
    arte: (
      <>
        <rect x="21" y="34" width="22" height="10" rx="2.5" fill="currentColor" />
        <rect x="23" y="27" width="18" height="6" rx="2" fill="currentColor" opacity="0.7" />
        <rect x="25" y="21" width="14" height="5" rx="2" fill="currentColor" opacity="0.45" />
      </>
    ),
  },
  // Chama: passou por cima de cinco finais.
  DEVORADOR: {
    cor: '#fb923c',
    arte: (
      <path d="M32 18 c5 7 9 9 9 15 a9 9 0 1 1 -18 0 c0-4 3-6 4-9 1 3 2 4 3 4 1-4 0-7 2-10 Z" fill="currentColor" />
    ),
  },
  // Escudo com casa: fiel ao mesmo serviço.
  FIEL: {
    cor: '#34d399',
    arte: (
      <>
        <path d="M32 19 L44 24 v9 c0 7-5 11-12 13 -7-2-12-6-12-13 v-9 Z" fill="none" stroke="currentColor" strokeWidth="2.3" strokeLinejoin="round" />
        <path d="M26 33 l6-5 6 5 v6 h-12 Z" fill="currentColor" />
      </>
    ),
  },
  // Calendário marcado: voltou em dias diferentes.
  CONSTANTE: {
    cor: '#c084fc',
    arte: (
      <>
        <rect x="20" y="23" width="24" height="21" rx="3.5" fill="none" stroke="currentColor" strokeWidth="2.2" />
        <path d="M20 30 H44" stroke="currentColor" strokeWidth="2.2" />
        <circle cx="27" cy="36" r="2.2" fill="currentColor" />
        <circle cx="32" cy="36" r="2.2" fill="currentColor" />
        <circle cx="37" cy="36" r="2.2" fill="currentColor" opacity="0.5" />
      </>
    ),
  },
  // Coroa: o topo da lista.
  CINQUENTA: {
    cor: '#fde047',
    arte: (
      <>
        <path d="M20 40 L23 24 L28 32 L32 22 L36 32 L41 24 L44 40 Z" fill="currentColor" />
        <path d="M20 43 H44" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" />
      </>
    ),
  },
}

// Recorte de moldura, compartilhado por todas: um hexágono de canto redondo.
const MOLDURA = 'M32 6 L52 17 V47 L32 58 L12 47 V17 Z'

export function AchievementBadge({ codigo, conquistada }: AchievementBadgeProps) {
  const miolo = MIOLOS[codigo]
  if (miolo === undefined) return null

  return (
    <svg
      className="badge"
      viewBox="0 0 64 64"
      data-conquistada={conquistada}
      aria-hidden="true"
      style={{ color: conquistada ? miolo.cor : 'var(--text-secondary)' }}
    >
      <path className="badge__fundo" d={MOLDURA} />
      <path className="badge__borda" d={MOLDURA} />
      {/* Trancada, a arte fica só insinuada: dá para ver o que se ganha sem
          confundir com o que já se tem. */}
      <g className="badge__arte" opacity={conquistada ? 1 : 0.28}>
        {miolo.arte}
      </g>
    </svg>
  )
}
