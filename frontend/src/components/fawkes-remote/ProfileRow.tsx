import { Trash2, UserRound } from 'lucide-react'

import { apiBaseUrl } from '../../features/fawkes-remote/apiUrl'
import { useAuthenticatedImage } from '../../hooks/useAuthenticatedImage'
import type { Platform, StreamingProfile } from '../../features/fawkes-remote/types'


interface ProfileRowProps {
  platform: Platform
  profiles: StreamingProfile[]
  credentials: { deviceId: string; token: string } | null
  disabled: boolean
  onSelect: (profileId: string) => void
  onRemove: (profileId: string) => void
}

/**
 * Os perfis do serviço, como botões.
 *
 * O avatar não é um ícone parecido: é o recorte da própria tela do computador,
 * feito na hora do cadastro. Por isso o perfil da Netflix aparece aqui com a
 * cara que ele tem lá.
 */
export function ProfileRow({
  platform,
  profiles,
  credentials,
  disabled,
  onSelect,
  onRemove,
}: ProfileRowProps) {
  if (profiles.length === 0) return null

  return (
    <div className="profile-row" role="group" aria-label="Perfis salvos">
      {profiles.map((profile) => (
        <ProfileButton
          key={profile.id}
          platform={platform}
          profile={profile}
          credentials={credentials}
          disabled={disabled}
          onSelect={onSelect}
          onRemove={onRemove}
        />
      ))}
    </div>
  )
}

function ProfileButton({
  platform,
  profile,
  credentials,
  disabled,
  onSelect,
  onRemove,
}: {
  platform: Platform
  profile: StreamingProfile
  credentials: { deviceId: string; token: string } | null
  disabled: boolean
  onSelect: (profileId: string) => void
  onRemove: (profileId: string) => void
}) {
  // O avatar é recurso autenticado: `<img src>` não manda cabeçalho, então a
  // imagem vem por fetch e vira blob.
  const avatar = useAuthenticatedImage(
    profile.temAvatar
      ? `${apiBaseUrl()}/screen/profiles/${platform}/${profile.id}/avatar`
      : null,
    credentials,
  )

  return (
    <div className="profile-chip">
      <button
        type="button"
        className="profile-chip__go"
        aria-label={`Entrar como ${profile.nome}`}
        disabled={disabled}
        onClick={() => onSelect(profile.id)}
      >
        <span className="profile-chip__avatar" aria-hidden="true">
          {avatar !== null ? (
            <img src={avatar} alt="" />
          ) : (
            <UserRound size={20} />
          )}
        </span>
        <span className="profile-chip__nome">{profile.nome}</span>
      </button>
      <button
        type="button"
        className="profile-chip__remover"
        aria-label={`Remover o perfil ${profile.nome}`}
        onClick={() => onRemove(profile.id)}
      >
        <Trash2 size={12} aria-hidden="true" />
      </button>
    </div>
  )
}
