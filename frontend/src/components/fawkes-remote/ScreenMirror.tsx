import { Camera, Loader2, MousePointerClick, RefreshCw, UserPlus, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'

import { apiBaseUrl } from '../../features/fawkes-remote/apiUrl'
import { PLATFORM_BRANDS } from '../../features/fawkes-remote/platformBrand'
import type { Platform } from '../../features/fawkes-remote/types'


interface ScreenMirrorProps {
  platform: Platform
  credentials: { deviceId: string; token: string } | null
  disabled: boolean
  /**
   * Clicar de verdade naquele ponto da janela. Disparado por um botão, nunca
   * pelo toque na imagem: enquanto se cadastra um perfil, clicar faria a
   * Netflix sair da tela de perfis — e o recorte do avatar, que acontece ao
   * salvar, pegaria a tela seguinte em vez do perfil.
   */
  onTap: (x: number, y: number) => void
  /** Cadastro: o ponto tocado vira um perfil com nome e avatar. */
  onRegister: (x: number, y: number, nome: string) => Promise<boolean>
}

type Estado = 'inicial' | 'buscando' | 'pronta' | 'fechada' | 'falhou'

interface Marca {
  x: number
  y: number
}

/**
 * A tela do computador, num quadro, no celular.
 *
 * Existe porque escolher perfil na Netflix pelo touchpad é mirar um cursor
 * invisível numa TV do outro lado da sala — e a tela de login é pior ainda,
 * porque obriga a trocar de tela no controle no meio do caminho.
 *
 * É uma foto sob demanda, não uma transmissão: um quadro por toque no botão.
 * Ler o HTML da página seria mais "esperto" e bem pior — exigiria o navegador
 * com porta de depuração aberta, perfil separado, login de novo, e quebraria
 * quando a Netflix mudasse o site.
 */
export function ScreenMirror({
  platform,
  credentials,
  disabled,
  onTap,
  onRegister,
}: ScreenMirrorProps) {
  const [estado, setEstado] = useState<Estado>('inicial')
  const [quadro, setQuadro] = useState<string | null>(null)
  const [marca, setMarca] = useState<Marca | null>(null)
  const [nome, setNome] = useState('')
  const [salvando, setSalvando] = useState(false)
  const imagemRef = useRef<HTMLImageElement>(null)
  const { name } = PLATFORM_BRANDS[platform]

  // O quadro é um blob: sem revogar, cada atualização deixaria o anterior
  // preso na memória do navegador.
  useEffect(() => () => { if (quadro) URL.revokeObjectURL(quadro) }, [quadro])

  const buscarQuadro = useCallback(async () => {
    if (credentials === null) return
    setEstado('buscando')
    setMarca(null)
    try {
      const resposta = await fetch(`${apiBaseUrl()}/screen/frame/${platform}`, {
        headers: {
          'X-Device-Id': credentials.deviceId,
          'X-Device-Token': credentials.token,
        },
      })
      if (resposta.status === 404) {
        setEstado('fechada')
        return
      }
      if (!resposta.ok) {
        setEstado('falhou')
        return
      }
      const url = URL.createObjectURL(await resposta.blob())
      setQuadro((anterior) => {
        if (anterior) URL.revokeObjectURL(anterior)
        return url
      })
      setEstado('pronta')
    } catch {
      setEstado('falhou')
    }
  }, [credentials, platform])

  // Trocar de plataforma sem apagar o quadro mostraria a Netflix na aba do
  // Disney+ — e um toque ali clicaria na janela errada.
  useEffect(() => {
    setEstado('inicial')
    setMarca(null)
    setQuadro((anterior) => {
      if (anterior) URL.revokeObjectURL(anterior)
      return null
    })
  }, [platform])

  function fracaoDoToque(evento: React.MouseEvent<HTMLImageElement>): Marca | null {
    const imagem = imagemRef.current
    if (imagem === null) return null
    const caixa = imagem.getBoundingClientRect()
    if (caixa.width === 0 || caixa.height === 0) return null
    return {
      x: (evento.clientX - caixa.left) / caixa.width,
      y: (evento.clientY - caixa.top) / caixa.height,
    }
  }

  async function salvarPerfil() {
    if (marca === null || !nome.trim()) return
    setSalvando(true)
    const deuCerto = await onRegister(marca.x, marca.y, nome.trim())
    setSalvando(false)
    if (deuCerto) {
      setNome('')
      setMarca(null)
    }
  }

  return (
    <section className="screen-mirror" aria-label={`Tela do ${name} no computador`}>
      <div className="screen-mirror__head">
        <p className="screen-mirror__eyebrow">
          <Camera size={12} aria-hidden="true" />
          Tela do {name}
        </p>
        <button
          type="button"
          className="screen-mirror__refresh"
          disabled={disabled || estado === 'buscando'}
          onClick={buscarQuadro}
        >
          {estado === 'buscando'
            ? <Loader2 size={13} aria-hidden="true" className="voice-btn__spinner" />
            : <RefreshCw size={13} aria-hidden="true" />}
          {estado === 'inicial' ? 'Ver a tela' : 'Atualizar'}
        </button>
      </div>

      {estado === 'pronta' && quadro !== null ? (
        <div className="screen-mirror__palco">
          <img
            ref={imagemRef}
            className="screen-mirror__quadro"
            src={quadro}
            alt={`Foto da janela do ${name}`}
            onClick={(evento) => {
              // Só marca. O toque na foto é escolha de ponto, não comando.
              const ponto = fracaoDoToque(evento)
              if (ponto !== null) setMarca(ponto)
            }}
          />
          {marca !== null ? (
            <span
              className="screen-mirror__alvo"
              style={{ left: `${marca.x * 100}%`, top: `${marca.y * 100}%` }}
              aria-hidden="true"
            />
          ) : null}
        </div>
      ) : (
        <p className="screen-mirror__vazio">
          {estado === 'buscando' ? 'Fotografando a tela…' : null}
          {estado === 'inicial' ? `Toque em "Ver a tela" para enxergar o ${name} daqui.` : null}
          {estado === 'fechada' ? `${name} não está aberto no computador.` : null}
          {estado === 'falhou' ? 'Não consegui fotografar a janela agora.' : null}
        </p>
      )}

      {/* O cadastro aparece só depois do toque, com o ponto já escolhido: é o
          mesmo gesto que a pessoa acabou de fazer, agora com um nome. */}
      {marca !== null && estado === 'pronta' ? (
        <div className="screen-mirror__cadastro">
          <label htmlFor="perfil-nome">Guardar este ponto como perfil</label>
          <div className="screen-mirror__linha">
            <input
              id="perfil-nome"
              type="text"
              value={nome}
              maxLength={40}
              placeholder="Nome do perfil"
              disabled={disabled || salvando}
              onChange={(evento) => setNome(evento.target.value)}
            />
            <button
              type="button"
              aria-label="Guardar perfil"
              disabled={disabled || salvando || !nome.trim()}
              onClick={salvarPerfil}
            >
              {salvando
                ? <Loader2 size={16} aria-hidden="true" className="voice-btn__spinner" />
                : <UserPlus size={16} aria-hidden="true" />}
            </button>
            <button
              type="button"
              className="screen-mirror__cancelar"
              aria-label="Cancelar cadastro"
              onClick={() => { setMarca(null); setNome('') }}
            >
              <X size={16} aria-hidden="true" />
            </button>
          </div>

          {/* Conferir a mira antes de dar nome: clica no ponto marcado sem
              cadastrar nada. Útil para descobrir qual perfil é qual. */}
          <button
            type="button"
            className="screen-mirror__clicar"
            disabled={disabled}
            onClick={() => {
              onTap(marca.x, marca.y)
              // Fotografa de novo logo depois: sem isto o clique é cego, e a
              // pessoa só descobre onde ele caiu olhando para a TV.
              window.setTimeout(() => { void buscarQuadro() }, 700)
            }}
          >
            <MousePointerClick size={13} aria-hidden="true" />
            Só clicar aqui, sem salvar
          </button>
        </div>
      ) : null}
    </section>
  )
}
