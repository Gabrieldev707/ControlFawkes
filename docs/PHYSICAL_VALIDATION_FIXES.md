# Correções após validação física do MVP

Esta rodada registra ajustes derivados do teste físico no iPhone. Cada seção corresponde a uma fatia independente e a um commit próprio. Testes automatizados usam somente adaptadores e processos simulados: eles nunca acionam mouse, teclado, volume, Chrome ou Spotify reais.

## 1. Classificação de gestos do touchpad

- Causa raiz: qualquer deslocamento iniciava `POINTER_DOWN`, transformando movimento comum em arraste; além disso, o clique não tinha limite de duração, tolerância explícita nem cancelamento persistente para multitouch e rolagem.
- Correção: toque só é clique quando dura no máximo 250 ms e permanece até 6 px do ponto inicial. Movimento maior cancela o clique; segurar por 350 ms antes de mover ativa o arraste explícito.
- Segurança: `pointercancel`, multitouch, rolagem, parada e desativação cancelam o clique e liberam um botão mantido. O evento `click` nativo da superfície é bloqueado para evitar clique fantasma.
- Preservado: movimento relativo, agregação por `requestAnimationFrame`, limites de delta, rate limit do backend e botões explícitos.
- Verificação automatizada: 8 testes do componente e lint aprovados. Validação física móvel permanece pendente.
