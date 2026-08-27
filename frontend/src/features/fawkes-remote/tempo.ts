/**
 * Minutagem, do jeito que um player escreve.
 *
 * Estava dentro do cartão de "tocando agora", que era o único lugar que
 * mostrava tempo. Agora "continuar assistindo" mostra também, e duas cópias da
 * mesma conta divergem — foi assim que o mapa de logos dos serviços acabou
 * desencontrado em quatro telas.
 */
export function formatarTempo(segundos: number): string {
  const total = Math.max(0, Math.floor(segundos))
  const horas = Math.floor(total / 3600)
  const minutos = Math.floor((total % 3600) / 60)
  const restantes = total % 60
  const doisDigitos = (valor: number) => String(valor).padStart(2, '0')
  return horas > 0
    ? `${horas}:${doisDigitos(minutos)}:${doisDigitos(restantes)}`
    : `${minutos}:${doisDigitos(restantes)}`
}
