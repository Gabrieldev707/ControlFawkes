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

## 3. Logo da Max

- Causa raiz: `/platforms/max.svg` apontava para um glifo cinza quadrado em vez do wordmark da plataforma, com contraste e proporção incompatíveis com o card.
- Correção: o asset local foi substituído pelo wordmark vetorial Max já presente no histórico do projeto, com `viewBox="0 0 24 24"` e preenchimento branco para o fundo escuro.
- Preservado: caminho e case `/platforms/max.svg`, nome acessível `Max`, dimensões do card e `object-fit: contain` da classe compartilhada. Nenhum logo foi desenhado em CSS.
- Verificação automatizada: teste confirma asset, caminho de produção, título, viewBox e classe de contenção. Build de produção valida a cópia para `dist`.

## 4. Plataformas web no Google Chrome

- Causa raiz: o launcher usava `webbrowser.open`, delegando ao navegador padrão e sem conseguir distinguir Chrome ausente de falha de abertura.
- Correção: `ChromeLocator` procura instalações padrão, App Paths do Windows e PATH; `BrowserLauncher` inicia o executável diretamente com `--new-tab`, sem perfil temporário ou modo anônimo.
- Segurança: Netflix, Max, Prime Video, Disney+ e YouTube são resolvidos exclusivamente pelo registry do backend. URL arbitrária é recusada antes da localização ou criação de processo.
- Erros: Chrome ausente retorna `PLATFORM_OPEN_FAILED` com mensagem específica; falha de processo não declara sucesso.
- Verificação automatizada: 20 testes direcionados aprovados com locator e processo simulados. Nenhum Chrome real foi iniciado; validação física permanece pendente.

## 5. Spotify com preferência pelo aplicativo

- Causa raiz: Spotify ainda usava o navegador padrão diretamente, sem tentar o aplicativo instalado e sem informar como a abertura ocorreu.
- Correção: o launcher tenta primeiro o URI oficial `spotify:`; se o protocolo não estiver disponível, abre `https://open.spotify.com` no Chrome.
- Protocolo: todo `OPEN_PLATFORM` bem-sucedido informa `CHROME`, `SPOTIFY_APP` ou `SPOTIFY_WEB_CHROME`. Estratégia ausente ou desconhecida é rejeitada no frontend.
- Falha segura: se aplicativo e Chrome falharem, o backend retorna erro e não declara execução.
- Verificação automatizada: launchers, fallback, integração WebSocket, validação runtime, lint e build aprovados com mocks. Nenhum Spotify ou Chrome real foi iniciado; validação física permanece pendente.
