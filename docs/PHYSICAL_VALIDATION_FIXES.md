# Correções após validação física do MVP

Esta rodada registra ajustes derivados do teste físico no iPhone. Cada seção corresponde a uma fatia independente e a um commit próprio. Testes automatizados usam somente adaptadores e processos simulados: eles nunca acionam mouse, teclado, volume, Chrome ou Spotify reais.

## 1. Classificação de gestos do touchpad

- Causa raiz: qualquer deslocamento iniciava `POINTER_DOWN`, transformando movimento comum em arraste; além disso, o clique não tinha limite de duração, tolerância explícita nem cancelamento persistente para multitouch e rolagem.
- Correção: toque só é clique quando dura no máximo 250 ms e permanece até 6 px do ponto inicial. Movimento maior cancela o clique; segurar por 350 ms antes de mover ativa o arraste explícito.
- Segurança: `pointercancel`, multitouch, rolagem, parada e desativação cancelam o clique e liberam um botão mantido. O evento `click` nativo da superfície é bloqueado para evitar clique fantasma.
- Preservado: movimento relativo, agregação por `requestAnimationFrame`, limites de delta, rate limit do backend e botões explícitos.
- Verificação automatizada: 8 testes do componente e lint aprovados. Validação física móvel permanece pendente.

## 2. Presença visual da orb

- Causa raiz: a regulagem de halo, linhas e elétrons já estava nos alvos da rodada, mas a intensidade interpolada dos pontos ainda parava em 1,00 na maioria dos estados e em 0,94 no estado de erro.
- Correção: brilho por estado ajustado para `idle 1,08`, `listening 1,10`, `transcribing 1,08`, `needs_selection 1,06`, `executing 1,10`, `success 1,10` e `error 1,02`.
- Mantidos: halo intermediário `0,42`, multiplicador de linhas `0,085`, elétrons `1,00`, opacidade inicial dos pontos `1,00`, tamanhos, contagens, geometria, física, paletas e transições.
- Limite: todos os estados permanecem entre 1,02 e o teto moderado de 1,10, sem CSS global nem opacidade no contêiner.
- Verificação automatizada: contrato dos temas da orb aprovado. Comparação física no iPhone permanece pendente.
