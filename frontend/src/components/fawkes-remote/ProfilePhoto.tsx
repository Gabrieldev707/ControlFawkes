import { Camera, Trash2, UserRound } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'


const CHAVE = 'controlfawkes.foto'
const NOME = 'controlfawkes.nome'

// Lado do quadrado guardado. O avatar nunca aparece maior que isto, e um
// retrato de celular moderno tem 4000px de largura — guardá-lo inteiro encheria
// o armazenamento do navegador por nada.
const LADO = 256


interface ProfilePhotoProps {
  /** Quantas medalhas já foram conquistadas, para o anel em volta da foto. */
  nivel: number
  total: number
}

function lerGuardado(chave: string): string | null {
  try {
    return localStorage.getItem(chave)
  } catch {
    return null
  }
}

/**
 * Recorta o centro da imagem num quadrado e devolve como JPEG pequeno.
 *
 * O recorte acontece no próprio celular: a foto nunca sai do aparelho, não
 * passa pelo servidor e não vai para lugar nenhum. É por isso que ela mora no
 * `localStorage` e não em `backend/data` — este é o único dado do controle que
 * é sobre a pessoa, não sobre o computador.
 */
async function comoQuadrado(arquivo: File): Promise<string | null> {
  const url = URL.createObjectURL(arquivo)
  try {
    const imagem = await new Promise<HTMLImageElement>((ok, falhou) => {
      const elemento = new Image()
      elemento.onload = () => ok(elemento)
      elemento.onerror = falhou
      elemento.src = url
    })
    const lado = Math.min(imagem.naturalWidth, imagem.naturalHeight)
    if (lado === 0) return null

    const tela = document.createElement('canvas')
    tela.width = LADO
    tela.height = LADO
    const pincel = tela.getContext('2d')
    if (pincel === null) return null
    pincel.drawImage(
      imagem,
      (imagem.naturalWidth - lado) / 2,
      (imagem.naturalHeight - lado) / 2,
      lado,
      lado,
      0,
      0,
      LADO,
      LADO,
    )
    return tela.toDataURL('image/jpeg', 0.82)
  } catch {
    return null
  } finally {
    URL.revokeObjectURL(url)
  }
}

/** A foto e o nome de quem usa o controle. */
export function ProfilePhoto({ nivel, total }: ProfilePhotoProps) {
  const [foto, setFoto] = useState<string | null>(() => lerGuardado(CHAVE))
  const [nome, setNome] = useState<string>(() => lerGuardado(NOME) ?? '')
  const [erro, setErro] = useState(false)
  const entradaRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    try {
      if (nome.trim()) localStorage.setItem(NOME, nome.trim())
      else localStorage.removeItem(NOME)
    } catch {
      // Armazenamento bloqueado: o nome vale só nesta sessão.
    }
  }, [nome])

  async function escolher(arquivo: File | undefined) {
    if (arquivo === undefined) return
    const quadrado = await comoQuadrado(arquivo)
    if (quadrado === null) {
      setErro(true)
      return
    }
    try {
      localStorage.setItem(CHAVE, quadrado)
      setFoto(quadrado)
      setErro(false)
    } catch {
      // Passou do limite do navegador. Dizer isso é melhor do que aparentar
      // que salvou e sumir no próximo carregamento.
      setErro(true)
    }
  }

  function remover() {
    try {
      localStorage.removeItem(CHAVE)
    } catch {
      // Nada a fazer: o estado abaixo já tira a foto da tela.
    }
    setFoto(null)
  }

  const proporcao = total > 0 ? nivel / total : 0

  return (
    <section className="profile-photo" aria-label="Sua foto e seu nome">
      <div className="profile-photo__moldura">
        {/* O anel em volta é o mesmo progresso das conquistas: a foto vira o
            lugar onde a evolução aparece, sem virar mais um medidor solto. */}
        <svg className="profile-photo__anel" viewBox="0 0 100 100" aria-hidden="true">
          <circle className="profile-photo__trilho" cx="50" cy="50" r="46" />
          <circle
            className="profile-photo__progresso"
            cx="50"
            cy="50"
            r="46"
            strokeDasharray={`${2 * Math.PI * 46 * proporcao} ${2 * Math.PI * 46}`}
          />
        </svg>

        <button
          type="button"
          className="profile-photo__alvo"
          aria-label={foto === null ? 'Escolher uma foto' : 'Trocar a foto'}
          onClick={() => entradaRef.current?.click()}
        >
          {foto !== null
            ? <img src={foto} alt="" />
            : <UserRound size={30} aria-hidden="true" />}
          {/* A câmera é um convite para escolher a foto — some quando já existe
              uma. Sobre o retrato de alguém, ela deixa de ser convite e vira um
              adesivo em cima do rosto; e trocar continua sendo tocar na foto,
              que é o que o rótulo do botão diz. */}
          {foto === null ? (
            <span className="profile-photo__camera" aria-hidden="true">
              <Camera size={13} />
            </span>
          ) : null}
        </button>

        <input
          ref={entradaRef}
          type="file"
          accept="image/*"
          className="visually-hidden"
          onChange={(evento) => {
            void escolher(evento.target.files?.[0])
            // Permite escolher o mesmo arquivo de novo depois de remover.
            evento.target.value = ''
          }}
        />
      </div>

      <div className="profile-photo__dados">
        <input
          className="profile-photo__nome"
          type="text"
          value={nome}
          maxLength={24}
          placeholder="Seu nome"
          aria-label="Seu nome"
          onChange={(evento) => setNome(evento.target.value)}
        />
        {/* "12 medalhas" ao lado de "Nível 2" lia-se como doze conquistadas —
            e o bloco de conquistas, na mesma tela, dizia "2 de 12". Duas contas
            diferentes para o mesmo número é pior do que não mostrar nenhuma. */}
        <p className="profile-photo__nivel">Nível {nivel} · {nivel} de {total} medalhas</p>
        {erro ? (
          <p className="profile-photo__erro">Não consegui guardar essa imagem.</p>
        ) : null}
        {foto !== null ? (
          <button type="button" className="profile-photo__remover" onClick={remover}>
            <Trash2 size={12} aria-hidden="true" />
            Remover foto
          </button>
        ) : null}
      </div>
    </section>
  )
}
