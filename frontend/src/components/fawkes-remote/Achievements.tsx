import { Check, Lock, X } from 'lucide-react'
import { useEffect, useState } from 'react'

import { AchievementBadge } from './AchievementBadge'


export interface Conquista {
  codigo: string
  nome: string
  descricao: string
  atual: number
  alvo: number
  conquistada: boolean
}

export interface Progresso {
  nivel: number
  total: number
  proxima: Conquista | null
}

interface AchievementsProps {
  conquistas: Conquista[]
  progresso: Progresso | null
}

/**
 * As conquistas do controle.
 *
 * O nível é só a contagem de medalhas — simples de explicar e impossível de
 * inflar sem assistir a nada. A barra mostra a próxima mais perto de fechar,
 * que é a que dá para alcançar hoje, e não a próxima da lista.
 *
 * Tocar numa medalha conta o que ela pede. Sem isso, uma grade de doze
 * desenhos trancados é bonita e muda.
 */
export function Achievements({ conquistas, progresso }: AchievementsProps) {
  const [aberta, setAberta] = useState<string | null>(null)
  if (conquistas.length === 0) return null

  const selecionada = conquistas.find((c) => c.codigo === aberta) ?? null

  return (
    <section className="achievements" aria-labelledby="achievements-titulo">
      <p className="profile-screen__secao" id="achievements-titulo">Conquistas</p>

      {progresso !== null ? (
        <div className="achievements__nivel">
          <p>
            <strong>Nível {progresso.nivel}</strong>
            <span>{progresso.nivel} de {progresso.total} medalhas</span>
          </p>
          <span className="achievements__trilho" aria-hidden="true">
            <span style={{ width: `${(progresso.nivel / progresso.total) * 100}%` }} />
          </span>
          {progresso.proxima !== null ? (
            <p className="achievements__proxima">
              A caminho: <strong>{progresso.proxima.nome}</strong>
              {' '}({progresso.proxima.atual} de {progresso.proxima.alvo})
            </p>
          ) : (
            <p className="achievements__proxima">Todas conquistadas. Sério.</p>
          )}
        </div>
      ) : null}

      <ul className="achievements__grade">
        {conquistas.map((conquista) => (
          <li key={conquista.codigo}>
            <button
              type="button"
              className="achievements__medalha"
              aria-pressed={aberta === conquista.codigo}
              aria-label={
                `${conquista.nome}: ${conquista.descricao}`
                + (conquista.conquistada
                  ? ' Conquistada.'
                  : ` ${conquista.atual} de ${conquista.alvo}.`)
              }
              onClick={() => setAberta(aberta === conquista.codigo ? null : conquista.codigo)}
            >
              <AchievementBadge
                codigo={conquista.codigo}
                conquistada={conquista.conquistada}
              />
              <span className="achievements__nome" data-conquistada={conquista.conquistada}>
                {conquista.nome}
              </span>
              {!conquista.conquistada ? (
                <span className="achievements__cadeado" aria-hidden="true">
                  <Lock size={9} />
                  {conquista.atual}/{conquista.alvo}
                </span>
              ) : null}
            </button>
          </li>
        ))}
      </ul>

      {selecionada !== null ? (
        <DetalheDaConquista conquista={selecionada} onFechar={() => setAberta(null)} />
      ) : null}
    </section>
  )
}


/**
 * O detalhe de uma conquista, por cima da tela.
 *
 * Antes o texto aparecia embaixo da grade — e numa grade de quatro colunas por
 * três linhas, tocar numa medalha de cima escrevia a explicação fora da vista.
 * Parecia que o toque não fazia nada.
 */
function DetalheDaConquista({
  conquista,
  onFechar,
}: {
  conquista: Conquista
  onFechar: () => void
}) {
  // Escape fecha, como em qualquer caixa de diálogo. Vale para o teclado
  // externo do iPad e para quem abre o controle no computador.
  useEffect(() => {
    const aoTeclar = (evento: KeyboardEvent) => {
      if (evento.key === 'Escape') onFechar()
    }
    window.addEventListener('keydown', aoTeclar)
    return () => window.removeEventListener('keydown', aoTeclar)
  }, [onFechar])

  const proporcao = Math.min(1, conquista.atual / conquista.alvo)

  return (
    <div className="conquista-modal" role="dialog" aria-modal="true" aria-labelledby="conquista-nome">
      {/* O fundo fecha ao toque: é o gesto que todo mundo tenta primeiro. */}
      <button
        type="button"
        className="conquista-modal__fundo"
        aria-label="Fechar"
        onClick={onFechar}
      />
      <div className="conquista-modal__caixa">
        <button
          type="button"
          className="conquista-modal__fechar"
          aria-label="Fechar"
          onClick={onFechar}
        >
          <X size={16} aria-hidden="true" />
        </button>

        <AchievementBadge codigo={conquista.codigo} conquistada={conquista.conquistada} />

        <h3 id="conquista-nome">{conquista.nome}</h3>
        <p className="conquista-modal__como">{conquista.descricao}</p>

        {conquista.conquistada ? (
          <p className="conquista-modal__feita">
            <Check size={14} aria-hidden="true" />
            Conquistada
          </p>
        ) : (
          <>
            <span className="conquista-modal__trilho" aria-hidden="true">
              <span style={{ width: `${proporcao * 100}%` }} />
            </span>
            <p className="conquista-modal__faltando">
              {conquista.atual} de {conquista.alvo} — faltam{' '}
              {conquista.alvo - conquista.atual}
            </p>
          </>
        )}
      </div>
    </div>
  )
}
