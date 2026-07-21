# Auditoria de recuperação da Fase 2

Data: 2026-07-21

## Objetivo

Comparar a fundação segura da Fase 1.6 com a branch histórica da Fase 2 e
decidir, antes de qualquer implementação funcional, quais conceitos podem ser
recuperados sem enfraquecer autenticação, protocolo, validação ou feedback real.

Esta auditoria não realizou merge, cherry-pick ou checkout da branch antiga.
Todos os arquivos foram lidos diretamente pelos objetos Git.

## Invariantes verificados

| Item | Resultado |
| --- | --- |
| Branch de trabalho | `feat/controlfawkes-loop-mvp` |
| Base real da nova branch | `125b9f57a0020a1f19b6ba2b018f862112ef7665` |
| Fundação preservada | `feat/fase-1-6-foundation` em `125b9f57a0020a1f19b6ba2b018f862112ef7665` |
| Fase 2 preservada | `feat/windows-controls-phase-2` em `1160ded9d460b76cdf4374439084355592ab337a` |
| Merge-base das branches históricas | `4a58c1c267b44c694ccd718d4ba2ffe744c9519d` |
| Working tree antes da auditoria | limpa |
| Merge ou cherry-pick | nenhum |

O prompt mencionava `c348a80` como HEAD esperado da fundação. A base usada foi
`125b9f5`, pois este é o HEAD mais recente e aprovado da Fase 1.6, contendo o
hotfix visual solicitado depois daquele documento.

O repositório `C:\Dev\OrcTech\OrcTech_v1` estava na branch `recovery/fase-0`
com alterações locais preexistentes. Nenhum arquivo desse repositório foi
lido como fonte de implementação, alterado, removido ou versionado por esta
auditoria.

## Baseline da fundação

Executada na nova branch antes de qualquer alteração funcional:

```text
Frontend lint: PASS
Frontend build: PASS (aviso conhecido de chunk acima de 500 kB)
Frontend tests: 42 PASS
Backend tests: 54 PASS (um aviso conhecido de depreciação do TestClient)
```

## Critérios de classificação

- **REUTILIZAR**: unidade isolada, testada e sem dependência do protocolo antigo;
  ainda deve entrar por uma implementação e revisão normais.
- **ADAPTAR**: conceito ou unidade útil, mas precisa aderir ao protocolo v1,
  estado real, arquitetura atual ou requisitos mobile.
- **DESCARTAR**: implementação incompatível, redundante, enganosa ou menos
  segura que a fundação atual.
- **REIMPLEMENTAR**: requisito inexistente ou protótipo sem comportamento real;
  deve nascer sobre contratos novos e testes próprios.

## Resumo executivo

A branch da Fase 2 possui uma direção visual útil, navegação interna com três
destinos, componentes testados para volume e um serviço real de volume Windows.
Ela **não** possui launcher de plataformas, mídia real, touchpad real ou teclado
remoto. Os respectivos controles são previews ou botões desabilitados.

O protocolo antigo não possui `protocolVersion`, usa tipos e códigos abertos,
troca os nomes de estado da fundação e responde sucesso para seleção de
plataforma e texto sem executar nada. Por isso, dispatcher, schemas gerais,
autenticação, WebSocket e página orquestradora não podem ser transplantados.

Conclusão: recuperar componentes visuais pequenos e o desenho do adapter de
volume; reimplementar toda comunicação e toda capacidade de controle sobre a
fundação segura.

## Backend

| Candidato da Fase 2 | Classificação | Motivo e ação necessária |
| --- | --- | --- |
| `app/protocol/dispatcher.py` | DESCARTAR | Não exige protocolo versionado e retorna sucesso falso para plataforma/texto. Manter o dispatcher v1 atual e adicionar handlers pequenos por composição. |
| `app/schemas/ws.py` | DESCARTAR | Ausência de `protocolVersion`, `state: str`, `code: str` e `data: Any` quebram os contratos fechados da fundação. |
| `app/schemas/auth.py` | DESCARTAR | A fundação atual possui autenticação e resultados mais estritos; não regredir para resultados booleanos abertos. |
| `app/security/device_store.py` | DESCARTAR | A fundação atual já entrega hash, comparação constante, lock, escrita atômica, listagem segura e revogação com testes mais completos. |
| `app/security/pairing.py` | DESCARTAR | Preservar o serviço atual de PIN temporário, uso único e limite de tentativas. |
| `app/api/websocket.py` e `app/main.py` | DESCARTAR | Lifecycle e dispatcher antigos são incompatíveis; CORS limita apenas `localhost` e não resolve o acesso pelo IP local. |
| `app/commands/parser.py` | DESCARTAR | É somente um stub com `pass`; o parser da fundação é o ponto de partida. |
| `app/protocol/rate_limit.py` | ADAPTAR | A janela por dispositivo é uma boa base, mas deve usar relógio monotônico, limpeza de buckets e limites específicos para pointer/volume. |
| `app/schemas/volume.py` | REIMPLEMENTAR | Validadores de inteiros são úteis como referência, porém as mensagens devem ser `SYSTEM_VOLUME_GET/SET/DELTA`, `SYSTEM_MUTE_TOGGLE`, incluir versão e integrar o union fechado. |
| `app/windows/volume.py` | ADAPTAR | É a única integração Windows real. Preservar a ideia de COM em thread, lock e releitura do estado; introduzir interface injetável, erros fechados e dependências condicionais. |
| `tests/test_volume.py` | ADAPTAR | Reaproveitar cenários de COM inicializado/finalizado e falha, usando o novo adapter e mocks que nunca alterem o volume real. |
| `tests/test_volume_native.py` | DESCARTAR da suíte automática | Toca a API nativa e não deve rodar em CI. Converter futuramente em roteiro/manual ou teste explicitamente opt-in. |
| `tests/test_e2e_ws.py` | ADAPTAR | O fluxo parear/autenticar/acionar é útil, mas todas as mensagens devem usar protocolo v1 e os serviços precisam ser injetados. |
| `tests/test_ws.py` da Fase 2 | DESCARTAR | Cobertura muito menor que a suíte atual e contratos antigos. Acrescentar casos à suíte da fundação. |

### Capacidades backend ausentes na Fase 2

| Capacidade | Classificação | Direção |
| --- | --- | --- |
| Launcher de plataformas | REIMPLEMENTAR | Allowlist central no backend, identificador fechado e adapter mockável; nunca receber URL do frontend. |
| Spotify e demais plataformas | REIMPLEMENTAR | Implementar uma por vez com confirmação real do adapter. |
| Controles de mídia | REIMPLEMENTAR | Não há schema, handler ou adapter antigo. Criar allowlist de ações e adapter Windows separado. |
| Touchpad/input | REIMPLEMENTAR | Não há mensagens nem backend de pointer. Criar validação, agrupamento, rate limit e failsafe. |
| Teclado | REIMPLEMENTAR | Não há mensagens nem backend. Texto e teclas especiais devem ter contratos distintos e allowlist. |

## Frontend: navegação e telas

| Candidato da Fase 2 | Classificação | Motivo e ação necessária |
| --- | --- | --- |
| `RemoteNavigation.tsx` e teste | ADAPTAR | Boa navegação mobile e `aria-current`, mas cobre apenas home/controle/touchpad. Expandir para as oito telas e suportar voltar. |
| Estado local `currentView` | ADAPTAR | Serve como referência para navegação sem dependência nova; mover para estado central tipado com `CurrentScreen`. |
| `FawkesRemotePage.tsx` | DESCARTAR como unidade | Monolítica, usa chaves antigas de localStorage, não envia versão, não aguarda `READY` e mistura transporte, autenticação, volume e UI. Extrair apenas fluxos visuais. |
| `MediaControlPanel.tsx` e teste | ADAPTAR | Layout e composição são úteis; o painel mistura volume com transportes desabilitados e precisa receber ações/estados reais. |
| `TransportCluster.tsx` e teste | REIMPLEMENTAR | Todos os botões estão desabilitados e não há callbacks ou protocolo de mídia. |
| `TouchpadPreview.tsx/.css` e teste | ADAPTAR visualmente | É explicitamente “preview — sem envio”. Reusar somente composição visual, substituindo por pointer events, acessibilidade, emergência e estado real. |
| Tela de teclado | REIMPLEMENTAR | Não existe na branch antiga; `SearchSheet` não é teclado remoto. |
| Tela de plataformas | REIMPLEMENTAR | A grade existe apenas dentro da home. Criar tela e compartilhamento do componente sem duplicar estado. |
| Tela de volume | REIMPLEMENTAR | O rail existe dentro do painel de controle, mas a tela e seu fluxo próprio não existem. |
| Tela de configurações | REIMPLEMENTAR | Não existe. Incluir conexão, dispositivo e revogação/novo pareamento sem expor token. |
| Pareamento | ADAPTAR apenas apresentação | O keypad visual é testado, porém a implementação antiga usa protocolo/chaves incompatíveis. Preservar integralmente o fluxo seguro atual. |

## Frontend: componentes visuais

| Candidato da Fase 2 | Classificação | Motivo e ação necessária |
| --- | --- | --- |
| `VerticalVolumeRail.tsx` e teste | REUTILIZAR | Componente puro, acessível, limitado a 0–100 e testado. Integrar por props ao novo estado/adapter. |
| `WindowsVolumeControl.tsx/.css` e teste | ADAPTAR | Boa sincronização local/confirmada e controles grandes; trocar callbacks pelo fluxo de ação global e evitar envios duplicados no drag. |
| `PlayerVolumeControl.tsx` | DESCARTAR por enquanto | É apenas um rail desabilitado, sem fonte real de estado ou adapter. |
| `PlatformGrid.tsx` e teste | ADAPTAR | Cards, estados visuais e logos são úteis; remover dependência de `DOMRect`/attractor da ação funcional e usar resultados reais do backend. |
| `ControlCircuitLayer.tsx` e teste | REUTILIZAR visualmente | Isolado, testado e sem acesso a transporte/Windows. Pode decorar a tela de controle sem determinar sucesso. |
| `controlFeedback.ts` e teste | REUTILIZAR | Máquina visual pequena e pura; feedback final ainda deve depender da resposta do servidor. |
| `CosmicRemoteControl.css` | ADAPTAR | Fonte útil para o layout premium; extrair somente seletores dos componentes adotados e alinhar aos tokens/safe areas atuais. |
| `SearchSheet.tsx` e teste | ADAPTAR | Dialog e fechamento são úteis, mas a ação está desabilitada. Transformar posteriormente em entrada real da tela de teclado/pesquisa permitida. |
| `CommandBar.tsx` | DESCARTAR | Campo sem submissão e botão de voz sem contrato; o `TextInput` atual é funcional e testado. |
| `HoldToTalkButton.tsx` | DESCARTAR | Preview desabilitado duplica o `VoiceButton` atual. Voz permanece fora do escopo funcional imediato. |
| `RemoteStatusText.tsx` antigo | DESCARTAR | Usa sempre `role=status`; a fundação atual já diferencia `aria-live` e `role=alert` para erros. Adaptar apenas CSS de espaço, nunca o contrato. |
| `statusCopy.ts` | DESCARTAR | Deriva mensagens otimistas como “selecionada” sem confirmação real. Status deve vir do backend/ação corrente. |
| `PairingScreen.css` | ADAPTAR | Pode melhorar apresentação e teclado numérico, mantendo as props, mensagens e storage keys atuais. |
| `deviceName.ts` e teste | REUTILIZAR opcionalmente | Função pura e sem dados sensíveis; não é prioridade e não substitui o `deviceId` seguro. |

## Orb

| Candidato da Fase 2 | Classificação | Motivo e ação necessária |
| --- | --- | --- |
| `FawkesOrb.ts` da Fase 2 | DESCARTAR como implementação | Altera física, câmera, quantidade de partículas no mobile, distância de linhas e tamanho dos pontos, contrariando o escopo atual; também desfaz o halo aprovado. |
| `orbTheme.ts` da Fase 2 | ADAPTAR somente como referência | Demonstra que pontos maiores e linhas mais fortes melhoram presença, mas muda tamanhos em todos os estados. A nova calibração deve respeitar limite 1.0 e identidade atual. |
| `orbAttractor.ts` e teste | DESCARTAR nesta etapa | Acopla seleção de card à física da orb e não é necessário para feedback real. |
| `orbPhysics.ts` e teste | DESCARTAR | Troca a física aprovada por spring radial. |
| `orbQuality.ts` e teste | DESCARTAR | Reduz partículas/linhas no mobile, proibido pelo novo escopo. |
| Transparência WebGL e remoção de `alphaMap` duplicado | REIMPLEMENTAR com teste visual | São pistas úteis para presença visual, mas devem ser avaliadas isoladamente sem copiar o restante da física. |
| Modo visual de desenvolvimento | REIMPLEMENTAR | Não existe na branch antiga. Deve ser removido do build de produção por `import.meta.env.DEV`. |

## Transporte, protocolo e estado

| Candidato da Fase 2 | Classificação | Motivo e ação necessária |
| --- | --- | --- |
| `types.ts` | DESCARTAR | Mensagens sem `protocolVersion`, estados incompatíveis e payloads/resultados abertos. Estender os unions atuais. |
| `protocol.ts` | DESCARTAR | Aceita códigos arbitrários, não valida versão e valida resultados de forma superficial. |
| `useWebSocket.ts` | DESCARTAR | Reintroduz limite de dez retries e perde listeners de rede/visibilidade já corrigidos na fundação. |
| `controlFeedback.ts` | REUTILIZAR | Apenas estado visual local, sem interferir no estado real do servidor. |
| Estado global da página antiga | REIMPLEMENTAR | Separar `ConnectionState`, `AuthState`, `ServerState`, `OrbState`, `CurrentScreen`, `CurrentPlatform` e `CurrentAction` em reducer/context simples. |

## Dependências

| Dependência/arquivo | Classificação | Motivo e ação necessária |
| --- | --- | --- |
| `pycaw`, `comtypes`, `pywin32` | ADAPTAR | Necessários apenas para volume Windows. Declarar de forma compatível com Windows e manter imports dentro do adapter. |
| `psutil` | DESCARTAR | Nenhum uso encontrado na branch antiga. |
| `concurrently` e scripts `dev:*` | ADAPTAR opcionalmente | Conveniência local útil, mas o script antigo contém caminho Windows rígido e não é requisito funcional. |
| `requirements.txt` totalmente fixado | DESCARTAR | Não substituir o conjunto mínimo e portável da fundação por um freeze incidental. |
| `.env.example`, `.gitignore`, CI e documentação antigos | DESCARTAR | Preservar os arquivos atuais; a comparação mostra que a branch antiga removeria CI e documentação da Fase 1.6. |

## Assets, estilos, evidências e testes

| Item | Classificação | Uso permitido |
| --- | --- | --- |
| Logos em `frontend/public/platforms` | REUTILIZAR após comparação | Assets locais sem poder funcional; manter nomes e acessibilidade. |
| Evidências PNG em `docs/evidence` | REUTILIZAR como referência | Servem para comparar layouts 375/390/430 px, não como código ou prova do novo MVP. |
| `TouchpadPreview.css`, `WindowsVolumeControl.css` | ADAPTAR | Extrair estilos úteis por tela; revisar safe areas, altura e scroll reais no iPhone. |
| `fawkes-remote.css` completo da Fase 2 | DESCARTAR como patch integral | Grande sobreposição com a fundação; copiar inteiro apagaria correções posteriores. |
| Testes de componentes puros | REUTILIZAR/ADAPTAR junto do componente | Nenhum componente entra sem seus testes e sem novos casos de protocolo/estado. |
| Testes da página monolítica | DESCARTAR como conjunto | Muitos validam contratos antigos e sucesso otimista; reescrever por tela/reducer. |

## Mapeamento de mensagens

| Fase 2 | MVP seguro | Decisão |
| --- | --- | --- |
| `VOLUME_GET` | `SYSTEM_VOLUME_GET` | Reimplementar schema/handler v1 |
| `VOLUME_SET` | `SYSTEM_VOLUME_SET` | Reimplementar schema/handler v1 |
| `VOLUME_STEP` | `SYSTEM_VOLUME_DELTA` | Reimplementar com delta limitado |
| `VOLUME_TOGGLE_MUTE` | `SYSTEM_MUTE_TOGGLE` | Reimplementar schema/handler v1 |
| `PLATFORM_SELECTED` | manter identificador fechado | Trocar sucesso sintético por launcher allowlisted real |
| `TEXT_COMMAND` | manter contrato v1 | Parser produz intenção; execução passa pelo mesmo launcher |
| mídia | inexistente | Reimplementar allowlist fechada |
| pointer | inexistente | Reimplementar validação/rate limit/failsafe |
| teclado | inexistente | Reimplementar texto e teclas seguras separadamente |

## Sequência segura de recuperação

1. Criar navegação e telas sobre o protocolo atual, inicialmente sem efeitos no
   Windows.
2. Expandir o parser com testes, preservando intents fechadas.
3. Criar interface de launcher e implementar Spotify allowlisted com mock nos
   testes.
4. Corrigir status e orb sem alterar física ou quantidade de partículas.
5. Adicionar as demais plataformas uma por vez.
6. Criar adapters independentes para mídia, volume e input.
7. Integrar volume usando apenas o desenho seguro identificado nesta auditoria.
8. Implementar touchpad e teclado do zero; a branch antiga não contém essas
   capacidades.

## Riscos que bloqueiam transplante direto

- ausência total de versão no protocolo antigo;
- resultados `Any`, estados e códigos abertos;
- sucesso falso para plataforma e comando textual;
- storage keys incompatíveis com a fundação;
- reconexão limitada a dez tentativas;
- página única com responsabilidades misturadas;
- protótipos visuais apresentados como controles, embora desabilitados;
- mudanças de física e quantidade de partículas da orb;
- dependências Windows misturadas ao requirements portável;
- teste nativo que consulta o volume real dentro da suíte automatizada.

Nenhum desses riscos exige apagar a branch antiga. Ela permanece preservada
como fonte histórica e visual; cada recuperação será reimplementada ou adaptada
explicitamente na nova branch.
