import { Camera, Trash2, UserRound } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { apiBaseUrl } from '../../features/fawkes-remote/apiUrl'


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
  /** Sem credenciais o perfil vale só neste navegador. */
  credentials?: { deviceId: string; token: string } | null
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
 * O recorte acontece no próprio celular, e é o que mantém a imagem pequena:
 * um retrato moderno tem 4000px de largura e viraria megabytes trafegando por
 * nada.
 *
 * A foto era guardada só aqui, e isso mudou em 17/08/2026. `localStorage` é
 * separado por ORIGEM, e origem inclui a porta: trocar `:5174` por `:5173`
 * fazia nome e foto sumirem sem nada ter sido apagado, e o mesmo aconteceria a
 * cada troca de celular ou navegador. Um dado que a pessoa entende como "minha
 * conta" não pode depender da porta em que o servidor subiu naquele dia.
 *
 * Agora o servidor é a fonte da verdade e o `localStorage` é cache: a tela
 * pinta na hora com o que tem e corrige quando a resposta chega. O destino da
 * imagem é o mesmo computador que já está sendo controlado, na mesma rede — ver
 * `backend/app/profiles/usuario.py`.
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

function guardarLocal(chave: string, valor: string | null): void {
  try {
    if (valor) localStorage.setItem(chave, valor)
    else localStorage.removeItem(chave)
  } catch {
    // Armazenamento bloqueado ou cheio. O cache é acelerador, não a verdade:
    // sem ele a tela só pinta um instante depois, quando o servidor responde.
  }
}

/** A foto e o nome de quem usa o controle. */
export function ProfilePhoto({ nivel, total, credentials = null }: ProfilePhotoProps) {
  // Começa pelo cache local para a tela não piscar vazia enquanto o servidor
  // responde. Quem manda é a resposta, e ela chega logo abaixo.
  const [foto, setFoto] = useState<string | null>(() => lerGuardado(CHAVE))
  const [nome, setNome] = useState<string>(() => lerGuardado(NOME) ?? '')
  const [erro, setErro] = useState(false)
  const entradaRef = useRef<HTMLInputElement>(null)

  const cabecalhos = credentials === null ? null : {
    'Content-Type': 'application/json',
    'X-Device-Id': credentials.deviceId,
    'X-Device-Token': credentials.token,
  }

  // O que está no computador vence o que está neste navegador. É esta linha
  // que faz o perfil sobreviver a uma troca de porta, de aparelho ou de aba.
  useEffect(() => {
    if (cabecalhos === null) return
    let cancelado = false
    void (async () => {
      try {
        const resposta = await fetch(`${apiBaseUrl()}/profile/me`, { headers: cabecalhos })
        if (!resposta.ok) return
        const dados = await resposta.json() as { nome?: unknown; foto?: unknown }
        if (cancelado) return
        const doServidor = typeof dados.foto === 'string' ? dados.foto : null
        const nomeDoServidor = typeof dados.nome === 'string' ? dados.nome : ''

        // Servidor vazio NÃO apaga o que este navegador já tinha.
        //
        // A primeira versão disto sobrescrevia sempre, e com isso o perfil
        // sumia de novo em dois casos reais: quando o servidor ainda não tinha
        // nada (primeira abertura depois da mudança) e quando um `PUT` anterior
        // falhou por o servidor estar fora do ar. Vazio não é uma resposta
        // sobre o perfil — é a ausência de uma.
        //
        // Neste caso quem tem o dado é este navegador, e ele SOBE. É a adoção
        // do que já existia, e é o que faz a migração acontecer sozinha, sem
        // ninguém precisar digitar de novo.
        const localFoto = lerGuardado(CHAVE)
        const localNome = lerGuardado(NOME) ?? ''
        if (doServidor === null && nomeDoServidor === '' && (localFoto || localNome)) {
          void enviar(localNome.trim() || null, localFoto)
          return
        }

        setFoto(doServidor)
        setNome(nomeDoServidor)
        guardarLocal(CHAVE, doServidor)
        guardarLocal(NOME, nomeDoServidor || null)
      } catch {
        // Servidor fora do ar: fica o que o cache tinha. Melhor a foto de
        // ontem do que uma tela vazia que sugere que o dado se perdeu.
      }
    })()
    return () => { cancelado = true }
    // Só quando as credenciais mudam: `cabecalhos` é recriado a cada render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [credentials?.deviceId, credentials?.token])

  async function enviar(proximoNome: string | null, proximaFoto: string | null) {
    if (cabecalhos === null) return
    try {
      await fetch(`${apiBaseUrl()}/profile/me`, {
        method: 'PUT',
        headers: cabecalhos,
        body: JSON.stringify({ nome: proximoNome, foto: proximaFoto }),
      })
    } catch {
      // Guardado localmente de qualquer forma; sobe na próxima alteração.
    }
  }

  useEffect(() => {
    guardarLocal(NOME, nome.trim() || null)
  }, [nome])

  async function escolher(arquivo: File | undefined) {
    if (arquivo === undefined) return
    const quadrado = await comoQuadrado(arquivo)
    if (quadrado === null) {
      setErro(true)
      return
    }
    guardarLocal(CHAVE, quadrado)
    setFoto(quadrado)
    setErro(false)
    await enviar(nome.trim() || null, quadrado)
  }

  function remover() {
    // Apaga dos dois lados: "remover" tem de remover, e uma foto que voltasse
    // na próxima abertura seria pior do que não ter o botão.
    guardarLocal(CHAVE, null)
    setFoto(null)
    void enviar(nome.trim() || null, null)
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
          /* Ao sair do campo, e não a cada tecla: "Gabriel" viraria sete
             requisições, e a última chegando fora de ordem gravaria "Gabrie". */
          onBlur={() => { void enviar(nome.trim() || null, foto) }}
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
