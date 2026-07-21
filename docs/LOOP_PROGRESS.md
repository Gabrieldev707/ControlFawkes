# ControlFawkes — Loop Progress

## Estado inicial

- Branch: `feat/fase-1-6-foundation`
- Base: `4a58c1c267b44c694ccd718d4ba2ffe744c9519d`
- Branch preservada: `feat/windows-controls-phase-2` em `1160ded9d460b76cdf4374439084355592ab337a`
- Backend inicial: 5 testes passando
- Frontend inicial: lint e build passando; script de teste ausente
- Testes manuais: `PENDING USER VALIDATION`

## Fase 1.6 — Implementação concluída, aguardando aprovação

### Objetivo

Consolidar protocolo, autenticação local, comandos de texto, reconexão, feedback real, CI e documentação sem integrar controle do Windows.

### Fatias planejadas

1. Protocolo versionado e autenticação no backend.
2. Pareamento e validação de protocolo no frontend.
3. Comandos de texto autenticados de ponta a ponta.
4. Rede local e reconexão contínua.
5. CI, documentação e verificação final.

### Estado atual

As cinco fatias foram implementadas e verificadas na branch isolada. A validação
física pelo iPhone e a aprovação explícita da fase continuam pendentes; nenhuma
fase posterior deve começar antes disso.

### Fatia 1 concluída — Protocolo versionado e autenticação no backend

#### Objetivo

Exigir autenticação antes de comandos e oferecer pareamento local com PIN temporário, token aleatório, persistência somente do hash e revogação.

#### Implementado

- `protocolVersion: 1` obrigatório e validado como inteiro estrito;
- tipos Pydantic fechados e campos extras proibidos;
- estado inicial `AUTH_REQUIRED` e transição autenticada para `READY`;
- PIN de seis dígitos, validade de cinco minutos, uso único e limite de cinco tentativas;
- token URL-safe aleatório, SHA-256 no armazenamento e comparação em tempo constante;
- arquivo JSON com lock e substituição atômica;
- listagem sem hashes e revogação por utilitário local;
- rejeição de JSON inválido, payload inválido, versão incompatível, mensagem desconhecida, PIN inválido, token inválido e comando não autenticado;
- seleção de plataforma autenticada retorna intenção reconhecida com `executed: false`.

#### Arquivos criados

- `backend/app/protocol/__init__.py`
- `backend/app/protocol/dispatcher.py`
- `backend/app/schemas/auth.py`
- `backend/app/security/device_store.py`
- `backend/app/security/pairing.py`
- `backend/scripts/manage_devices.py`
- `backend/tests/test_pairing.py`

#### Arquivos alterados

- `.gitignore`
- `backend/app/api/websocket.py`
- `backend/app/main.py`
- `backend/app/schemas/ws.py`
- `backend/requirements.txt`
- `backend/tests/test_ws.py`

#### Testes executados

```text
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp backend/data/pytest-fase16
.venv\Scripts\python.exe -m compileall -q app scripts tests
.venv\Scripts\python.exe scripts/manage_devices.py --help
```

#### Resultado

- Backend: 25 testes passando.
- Compilação Python: sem erros.
- Utilitário local: interface `list`/`revoke` disponível.
- Auditoria de capacidades proibidas: nenhuma referência encontrada nos arquivos da fatia.
- Aviso não bloqueante: o TestClient atual emite uma depreciação do Starlette sobre `httpx`.

#### Problemas encontrados

- O diretório temporário padrão do pytest não era gravável no sandbox.
- O primeiro caminho alternativo de `--basetemp` não possuía diretório pai.
- Valores `True` e `1.0` podiam atravessar a comparação preliminar de versão por igualdade do Python.

#### Correções realizadas

- A suíte foi isolada em um subdiretório ignorado de `backend/data/`.
- A versão passou a exigir `type(protocol_version) is int` e valor igual a `1`.
- Foram adicionados casos de regressão para versão ausente, inteira incorreta, string, booleano e decimal.

#### Limitações

- O frontend ainda não envia as novas mensagens autenticadas.
- `TEXT_COMMAND` autenticado ainda responde `NOT_IMPLEMENTED` até a fatia do parser.
- O teste pelo iPhone permanece pendente.

#### Commit

`feat: add versioned local pairing protocol`

#### Próxima fatia

Protocolo TypeScript fechado, tela de pareamento, persistência local de credenciais e autenticação automática no frontend.

### Fatia 2 concluída — Pareamento e autenticação no frontend

#### Objetivo

Aplicar o protocolo v1 no cliente, permitir pareamento por PIN e reutilizar credenciais locais sem liberar comandos antes de `READY`.

#### Implementado

- unions TypeScript fechadas para conexão, servidor, autenticação, orb, mensagens e erros;
- validação runtime de mensagens com versão, campos e códigos exatos;
- descarte de mensagens WebSocket inválidas;
- formulário acessível de PIN com filtro numérico e estados desconectado/pendente/erro;
- armazenamento local de `deviceId` e token sob chaves do ControlFawkes;
- `AUTH` automático uma única vez por conexão;
- remoção de credenciais quando o backend rejeita o token;
- comandos bloqueados até conexão, autenticação e estado `READY`;
- todas as mensagens existentes do frontend incluem `protocolVersion: 1`;
- gerador UUID v4 com fallback para `getRandomValues()` em HTTP local quando `randomUUID()` não existe.

#### Arquivos criados

- `frontend/src/components/fawkes-remote/PairingScreen.tsx`
- `frontend/src/components/fawkes-remote/PairingScreen.test.tsx`
- `frontend/src/features/fawkes-remote/protocol.ts`
- `frontend/src/features/fawkes-remote/protocol.test.ts`
- `frontend/src/features/fawkes-remote/FawkesRemotePage.test.tsx`
- `frontend/src/test/setup.ts`
- `frontend/src/utils/uuid.ts`
- `frontend/src/utils/uuid.test.ts`
- `frontend/vitest.config.ts`

#### Arquivos alterados

- `frontend/package.json`
- `frontend/src/components/fawkes-remote/index.ts`
- `frontend/src/features/fawkes-remote/FawkesRemotePage.tsx`
- `frontend/src/features/fawkes-remote/types.ts`
- `frontend/src/hooks/useWebSocket.ts`
- `frontend/src/styles/fawkes-remote.css`

#### Testes executados

```text
npm run test -- --run
npm run lint
npm run build
.venv\Scripts\python.exe -m pytest -q
```

#### Resultado

- Frontend: 21 testes passando em 5 arquivos.
- Frontend lint: sem erros.
- Frontend build: concluído; permanece apenas o aviso conhecido de chunk acima de 500 kB.
- Backend: 25 testes passando.

#### Problemas encontrados

- O jsdom não era limpo automaticamente entre testes do formulário.
- A assinatura genérica do Web Crypto mudou no TypeScript 6.
- `crypto.randomUUID()` não é uma dependência segura para todo acesso HTTP por IP local.

#### Correções realizadas

- Cleanup global da Testing Library foi configurado no Vitest.
- O buffer aleatório foi tipado explicitamente como `Uint8Array<ArrayBuffer>`.
- Foi adicionado UUID v4 com fonte aleatória injetável e fallback testado.

#### Limitações

- O campo textual ainda não envia `TEXT_COMMAND`.
- O botão de voz ainda será desabilitado e marcado como “Em breve” na próxima fatia.
- Reconexão contínua e eventos de retorno da rede ainda não foram implementados.

#### Commit

`feat: add frontend pairing flow`

#### Próxima fatia

Parser determinístico, comando textual autenticado e mensagens reais sincronizadas com a orb.

### Fatia 3 concluída — Comandos textuais determinísticos

#### Objetivo

Entregar o fluxo autenticado de ponta a ponta para comandos de texto sem executar plataformas ou ações do computador.

#### Implementado

- normalização por lowercase, espaços, acentos e preservação de `disney+`;
- aliases fechados para Netflix, Max, Prime Video, Disney+, YouTube e Spotify;
- intenções `OPEN_PLATFORM`, `SHOW_HELP` e `UNKNOWN` sem LLM;
- resposta `OPEN_PLATFORM` obrigatoriamente marcada com `executed: false`;
- fluxo WebSocket `BUSY → COMMAND_RESULT/ERROR → READY`;
- `TextInput` semântico com Enter, trim, limite de 500 caracteres e bloqueios;
- limpeza do campo apenas após frame aceito pelo WebSocket;
- bloqueio de envios duplicados durante execução;
- status com mensagem real do backend, `aria-live="polite"` e `role="alert"` em erro;
- botão de voz desabilitado e identificado como “Em breve”.

#### Arquivos criados

- `backend/tests/test_parser.py`
- `frontend/src/components/fawkes-remote/TextInput.test.tsx`
- `frontend/src/components/fawkes-remote/RemoteStatusText.tsx`
- `frontend/src/components/fawkes-remote/RemoteStatusText.test.tsx`
- `frontend/src/components/fawkes-remote/VoiceButton.test.tsx`

#### Arquivos alterados

- `backend/app/commands/parser.py`
- `backend/app/protocol/dispatcher.py`
- `backend/app/schemas/ws.py`
- `backend/tests/test_ws.py`
- `frontend/src/components/fawkes-remote/TextInput.tsx`
- `frontend/src/components/fawkes-remote/VoiceButton.tsx`
- `frontend/src/components/fawkes-remote/index.ts`
- `frontend/src/features/fawkes-remote/FawkesRemotePage.tsx`
- `frontend/src/features/fawkes-remote/FawkesRemotePage.test.tsx`
- `frontend/src/features/fawkes-remote/protocol.ts`
- `frontend/src/features/fawkes-remote/protocol.test.ts`
- `frontend/src/features/fawkes-remote/types.ts`
- `frontend/src/styles/fawkes-remote.css`

#### Testes executados

```text
npm run test -- --run
npm run lint
npm run build
.venv\Scripts\python.exe -m pytest -q
```

#### Resultado

- Frontend: 32 testes passando em 8 arquivos.
- Backend: 54 testes passando.
- Lint: sem erros.
- Build: concluído, com o aviso conhecido de tamanho do bundle.
- Auditoria: nenhuma referência a execução de navegador, shell, Windows, volume ou touchpad nos arquivos da fatia.

#### Problemas encontrados

- Os componentes iniciais não possuíam contratos de submissão, acessibilidade ou estado desabilitado.
- O estado `READY` chegava imediatamente depois do resultado e poderia apagar cedo demais a mensagem relevante.

#### Correções realizadas

- Componentes receberam props fechadas e testes de comportamento.
- `READY` é ignorado enquanto uma requisição ainda preserva seu resultado visível; a interface volta a “Computador pronto.” somente após o timeout visual.

#### Limitações

- O parser não pesquisa conteúdo nem escolhe mídia.
- Selecionar uma plataforma continua sem abrir site ou aplicativo.
- A reconexão ainda possui o limite antigo de tentativas e será tratada na próxima fatia.

#### Commit

`feat: add authenticated text commands`

#### Próxima fatia

URL WebSocket baseada no hostname local e reconexão contínua orientada por lifecycle.

### Fatia 4 concluída — Rede local e reconexão contínua

#### Objetivo

Remover a dependência de `localhost` no iPhone e manter uma única conexão WebSocket tentando se recuperar durante toda a vida da aplicação.

#### Implementado

- URL padrão derivada de `window.location.hostname` e `VITE_WS_PORT`;
- seleção automática de `ws` ou `wss` conforme o protocolo da página;
- `VITE_WS_URL` mantida apenas como override opcional;
- backoff exponencial `1s × 1,5` com teto de 15 segundos e sem limite de tentativas;
- reset de tentativas após abertura bem-sucedida;
- prevenção de sockets e timers duplicados;
- reconexão manual;
- reconexão imediata em `online`;
- reconexão ao voltar para `document.visibilityState === 'visible'`;
- cancelamento de timers, listeners e callbacks do socket no unmount;
- proteção contra callbacks de sockets antigos por identidade.

#### Arquivos criados

- `frontend/src/hooks/useWebSocket.test.ts`

#### Arquivos alterados

- `.env.example`
- `frontend/src/hooks/useWebSocket.ts`

#### Testes executados

```text
npm run test -- --run
npm run lint
npm run build
.venv\Scripts\python.exe -m pytest -q
```

#### Resultado

- Frontend: 42 testes passando em 9 arquivos.
- Backend: 54 testes passando.
- Lint: sem erros.
- Build: concluído, com o aviso conhecido de tamanho do bundle.
- Teste de reconexão manteve novas conexões após 13 quedas consecutivas e confirmou teto de 15 segundos.

#### Problemas encontrados

- O hook anterior interrompia após dez tentativas e limitava o atraso a dez segundos.
- Não existiam listeners de rede ou visibilidade.
- Callbacks e timers podiam sobreviver a mudanças de socket sem uma identidade explícita.

#### Correções realizadas

- Um único owner de socket passou a controlar lifecycle, timer e tentativas.
- Eventos imediatos limpam o timer pendente antes de conectar.
- Cleanup neutraliza callbacks antes de fechar o socket.

#### Limitações

- Acesso real pelo IP depende do firewall e da configuração da rede Wi-Fi.
- A validação no iPhone continua pendente de execução pelo usuário.

#### Commit

`fix: harden local websocket reconnect`

#### Próxima fatia

CI, README independente, auditoria final, execução local integrada e roteiro de validação manual.

### Fatia 5 concluída — CI, documentação e verificação integrada

#### Objetivo

Tornar a fundação reproduzível em um checkout limpo, documentar operação e
segurança e comprovar o fluxo local sem incluir capacidades de fases futuras.

#### Implementado

- CI separado para frontend e backend em push e pull request;
- dependências de teste do backend declaradas no arquivo de requisitos;
- README completo para instalação, rede local, pareamento, comandos, protocolo,
  testes, segurança, troubleshooting e limites da fase;
- documento legado corrigido para a arquitetura independente, mantendo o Fawkes
  original somente como referência visual;
- artefatos locais, dados de pareamento e caches explicitamente ignorados;
- roteiro de validação manual pelo iPhone documentado.

#### Verificação automatizada final

```text
Frontend: 42 testes passando em 9 arquivos
Backend: 54 testes passando
Lint: sem erros
Build: concluído
Python compileall: sem erros
pip check: nenhuma dependência quebrada
```

O build mantém um aviso não bloqueante de chunk acima de 500 kB. O backend
mantém um aviso não bloqueante de depreciação do TestClient do Starlette.

#### Verificação local integrada

- frontend e `/health` responderam HTTP 200 pelo IPv4 Wi-Fi `192.168.0.168`;
- WebSocket real percorreu `AUTH_REQUIRED → PAIR_RESULT → READY`;
- `abre spotify` percorreu `BUSY → COMMAND_RESULT → READY`, com
  `executed: false`;
- autenticação por credencial persistida foi aceita;
- texto desconhecido retornou `UNKNOWN_COMMAND`;
- o dispositivo temporário foi revogado e a credencial passou a retornar
  `INVALID_TOKEN`;
- o dispositivo temporário usado na verificação foi removido do store.

A verificação visual automatizada não pôde ser executada porque o binário
`agent-browser` do plugin não está instalado no ambiente. A carga HTTP, os
componentes e os fluxos de interface permanecem cobertos por build e testes. O
teste físico no iPhone continua corretamente marcado como pendente.

#### Auditoria de escopo e segurança

- nenhum arquivo em `backend/data/`, `.env` ou `.env.local` é rastreado;
- nenhum token real ou PIN temporário foi versionado;
- nenhuma referência a automação de navegador, shell, Windows, volume ou
  touchpad foi encontrada no código executável da fase;
- `feat/windows-controls-phase-2` permanece em
  `1160ded9d460b76cdf4374439084355592ab337a`;
- o merge-base da branch atual com a base solicitada é
  `4a58c1c267b44c694ccd718d4ba2ffe744c9519d`;
- nenhum merge ou cherry-pick da Fase 2 foi realizado.

#### Commit

`feat: complete phase 1.6 foundation`

#### Próximo passo

Executar o roteiro físico no iPhone e aguardar aprovação explícita da Fase 1.6.
Não iniciar controle real do Windows, navegador ou a fase MVP antes dessa
aprovação.

### Limitações

- Nenhuma ação real de plataforma ou do Windows será executada nesta fase.
- Validação pelo iPhone depende de teste manual do usuário na rede local.
- Diretórios locais não rastreados provenientes do checkout anterior não serão removidos nem versionados.
