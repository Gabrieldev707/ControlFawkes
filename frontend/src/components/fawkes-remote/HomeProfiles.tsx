import { Plus, X } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { apiBaseUrl } from '../../features/fawkes-remote/apiUrl'
import { PLATFORM_BRANDS } from '../../features/fawkes-remote/platformBrand'
import type { Platform, StreamingProfile } from '../../features/fawkes-remote/types'
import { ProfileRow } from './ProfileRow'
import { ScreenMirror } from './ScreenMirror'


interface HomeProfilesProps {
  /** O serviço que está aberto no computador. Sem isso não há o que mostrar. */
  platform: Platform | null
  credentials: { deviceId: string; token: string } | null
  disabled: boolean
  onTap: (platform: Platform, x: number, y: number) => void
  onSelectProfile: (platform: Platform, profileId: string) => void
}

/** Só o que veio no formato esperado: a lista vira botão que dispara clique. */
function perfisValidos(dados: unknown, platform: Platform): StreamingProfile[] {
  if (typeof dados !== 'object' || dados === null) return []
  const platforms = (dados as { platforms?: unknown }).platforms
  if (typeof platforms !== 'object' || platforms === null) return []
  const lista = (platforms as Record<string, unknown>)[platform]
  if (!Array.isArray(lista)) return []

  return lista.flatMap((item) => {
    if (typeof item !== 'object' || item === null) return []
    const { id, nome, temAvatar } = item as Record<string, unknown>
    if (typeof id !== 'string' || !id) return []
    if (typeof nome !== 'string' || !nome) return []
    return [{ id, nome, temAvatar: temAvatar === true }]
  })
}

/**
 * "Quem está assistindo?", na tela inicial.
 *
 * Fica aqui e não numa tela própria porque é aqui que a pessoa está no momento
 * em que precisa: acabou de abrir a Netflix e o computador está pedindo o
 * perfil. Mandar para outra tela seria repetir o atrito que o controle existe
 * para remover.
 *
 * A foto do computador aparece só no cadastro, atrás do "+": ela é a ferramenta
 * de ensinar onde o perfil fica, não algo para ficar na frente todo dia.
 */
export function HomeProfiles({
  platform,
  credentials,
  disabled,
  onTap,
  onSelectProfile,
}: HomeProfilesProps) {
  const [perfis, setPerfis] = useState<StreamingProfile[]>([])
  const [cadastrando, setCadastrando] = useState(false)

  const carregar = useCallback(async () => {
    if (platform === null || credentials === null) {
      setPerfis([])
      return
    }
    try {
      const resposta = await fetch(`${apiBaseUrl()}/screen/profiles`, {
        headers: {
          'X-Device-Id': credentials.deviceId,
          'X-Device-Token': credentials.token,
        },
      })
      setPerfis(resposta.ok ? perfisValidos(await resposta.json(), platform) : [])
    } catch {
      setPerfis([])
    }
  }, [credentials, platform])

  useEffect(() => { void carregar() }, [carregar])
  // Trocar de serviço fecha o cadastro: a foto seria de outra janela.
  useEffect(() => { setCadastrando(false) }, [platform])

  if (platform === null) return null
  const { name } = PLATFORM_BRANDS[platform]

  async function cadastrar(x: number, y: number, nome: string): Promise<boolean> {
    if (platform === null || credentials === null) return false
    try {
      const resposta = await fetch(`${apiBaseUrl()}/screen/profiles`, {
        method: 'POST',
        headers: {
          'X-Device-Id': credentials.deviceId,
          'X-Device-Token': credentials.token,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ platform, nome, x, y }),
      })
      if (!resposta.ok) return false
      await carregar()
      setCadastrando(false)
      return true
    } catch {
      return false
    }
  }

  async function remover(profileId: string) {
    if (platform === null || credentials === null) return
    try {
      await fetch(`${apiBaseUrl()}/screen/profiles/${platform}/${profileId}`, {
        method: 'DELETE',
        headers: {
          'X-Device-Id': credentials.deviceId,
          'X-Device-Token': credentials.token,
        },
      })
      await carregar()
    } catch {
      // Falhou apagar: a lista fica como está e o toque pode ser repetido.
    }
  }

  // Nada cadastrado e ninguém pedindo para cadastrar: a seção não aparece.
  // Uma linha vazia com um "+" na tela inicial seria ruído para quem nunca vai
  // usar isto.
  if (perfis.length === 0 && !cadastrando) {
    return (
      <section className="home-profiles home-profiles--vazia">
        <button
          type="button"
          className="home-profiles__abrir"
          onClick={() => setCadastrando(true)}
        >
          <Plus size={13} aria-hidden="true" />
          Salvar um perfil do {name}
        </button>
      </section>
    )
  }

  return (
    <section className="home-profiles" aria-labelledby="home-profiles-title">
      <div className="home-profiles__head">
        <p className="home-profiles__eyebrow" id="home-profiles-title">
          Quem está assistindo · {name}
        </p>
        <button
          type="button"
          className="home-profiles__acao"
          aria-label={cadastrando ? 'Fechar o cadastro' : 'Adicionar um perfil'}
          onClick={() => setCadastrando((atual) => !atual)}
        >
          {cadastrando ? <X size={14} aria-hidden="true" /> : <Plus size={14} aria-hidden="true" />}
        </button>
      </div>

      <ProfileRow
        platform={platform}
        profiles={perfis}
        credentials={credentials}
        disabled={disabled}
        onSelect={(profileId) => onSelectProfile(platform, profileId)}
        onRemove={(profileId) => void remover(profileId)}
      />

      {cadastrando ? (
        <ScreenMirror
          platform={platform}
          credentials={credentials}
          disabled={disabled}
          onTap={(x, y) => onTap(platform, x, y)}
          onRegister={cadastrar}
        />
      ) : null}
    </section>
  )
}
