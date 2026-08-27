import {
  Baby,
  BookOpen,
  Clapperboard,
  Compass,
  Drama,
  Fingerprint,
  Ghost,
  Heart,
  Landmark,
  Laugh,
  Mic,
  Mountain,
  Music,
  Palette,
  Puzzle,
  Rocket,
  Shield,
  Swords,
  Tv,
  Users,
  Wand2,
  Zap,
  type LucideIcon,
} from 'lucide-react'


interface Contagem {
  nome: string
  segundos: number
}

interface GenreTilesProps {
  generos: Contagem[]
  /** Como escrever o tempo. Vem de fora para a tela falar uma língua só. */
  formatar: (segundos: number) => string
}

/**
 * Cada gênero tem uma cara.
 *
 * A chave é o nome normalizado — o TMDB devolve parte em português e parte em
 * inglês ("Action & Adventure", "Sci-Fi & Fantasy") mesmo pedindo pt-BR, então
 * as duas grafias precisam cair no mesmo desenho.
 */
const DESENHOS: Array<[RegExp, LucideIcon]> = [
  // A ordem importa: "animacao" contém "acao", então Animação precisa ser
  // testada primeiro — senão ela recebe o desenho de Ação e os dois gêneros
  // ficam idênticos na tela.
  [/animacao|animation/, Palette],
  [/acao|action/, Swords],
  [/aventura|adventure/, Compass],
  [/comedia|comedy/, Laugh],
  [/crime|policial/, Fingerprint],
  [/documentario|documentary/, BookOpen],
  [/drama|novela|soap/, Drama],
  [/familia|family/, Users],
  [/fantasia|fantasy/, Wand2],
  [/historia|history/, Landmark],
  [/terror|horror/, Ghost],
  [/musica|music/, Music],
  [/misterio|mystery/, Puzzle],
  [/romance/, Heart],
  [/ficcao|sci-fi|science/, Rocket],
  [/thriller|suspense/, Zap],
  [/guerra|war|politic/, Shield],
  [/faroeste|western/, Mountain],
  [/infantil|kids/, Baby],
  [/talk|entrevista/, Mic],
  [/tv|reality/, Tv],
]

// O TMDB devolve parte dos gêneros em inglês mesmo com `language=pt-BR` —
// são os que ele só tem no catálogo de séries. Traduzir aqui evita "Action &
// Adventure" no meio de "Animação" e "Mistério".
const TRADUCOES: Array<[RegExp, string]> = [
  [/^action & adventure$/, 'Ação e Aventura'],
  [/^sci-fi & fantasy$/, 'Ficção e Fantasia'],
  [/^war & politics$/, 'Guerra e Política'],
  [/^kids$/, 'Infantil'],
  [/^soap$/, 'Novela'],
  [/^talk$/, 'Talk Show'],
  [/^reality$/, 'Reality'],
  [/^western$/, 'Faroeste'],
]

function traduzirGenero(nome: string): string {
  const limpo = nome.trim().toLowerCase()
  const achado = TRADUCOES.find(([padrao]) => padrao.test(limpo))
  return achado ? achado[1] : nome
}

function normalizar(nome: string): string {
  // Decompõe e joga fora tudo que não é ASCII imprimível — o que sobra do
  // acento depois do NFKD é exatamente isso. A alternativa seria uma classe
  // com os caracteres combinantes escritos direto, que some numa
  // reencodificação do arquivo e faz "Ação" deixar de virar "acao" sem
  // nenhum erro aparecer. Aconteceu.
  return nome
    .normalize('NFKD')
    .replace(/[^ -~]/g, '')
    .toLowerCase()
}

function desenhoDe(nome: string): LucideIcon {
  const limpo = normalizar(nome)
  const achado = DESENHOS.find(([padrao]) => padrao.test(limpo))
  // Sem correspondência, a claquete: é honesto dizer "é um gênero" em vez de
  // escolher um símbolo que sugira a coisa errada.
  return achado ? achado[1] : Clapperboard
}

// Geometria do anel, em unidades do viewBox.
const RAIO = 26
const CIRCUNFERENCIA = 2 * Math.PI * RAIO

/**
 * O gosto como uma coleção de selos.
 *
 * Barras horizontais quase iguais não diziam nada — com um título só, todos os
 * gêneros dele empatam e a tela virava três barras cheias uma embaixo da outra.
 * Aqui cada gênero tem um símbolo próprio, e o anel em volta mostra o quanto
 * ele pesa em relação ao mais assistido. Dá para ler de relance, sem comparar
 * comprimentos.
 */
export function GenreTiles({ generos, formatar }: GenreTilesProps) {
  if (generos.length === 0) return null
  const maior = Math.max(...generos.map((g) => g.segundos), 1)

  return (
    <ul className="genre-tiles">
      {generos.slice(0, 6).map((genero) => {
        const Icone = desenhoDe(genero.nome)
        // Piso visível: um gênero com pouquíssimo tempo ficaria com um anel
        // invisível, e o selo pareceria quebrado.
        const proporcao = Math.max(0.08, genero.segundos / maior)
        return (
          <li className="genre-tile" key={genero.nome}>
            <span className="genre-tile__marca">
              <svg className="genre-tile__aro" viewBox="0 0 64 64" aria-hidden="true">
                <circle className="genre-tile__trilho" cx="32" cy="32" r={RAIO} />
                <circle
                  className="genre-tile__anel"
                  cx="32"
                  cy="32"
                  r={RAIO}
                  strokeDasharray={`${CIRCUNFERENCIA * proporcao} ${CIRCUNFERENCIA}`}
                />
              </svg>
              <Icone className="genre-tile__icone" size={22} aria-hidden="true" />
            </span>
            <span className="genre-tile__nome">{traduzirGenero(genero.nome)}</span>
            <span className="genre-tile__tempo">{formatar(genero.segundos)}</span>
          </li>
        )
      })}
    </ul>
  )
}
