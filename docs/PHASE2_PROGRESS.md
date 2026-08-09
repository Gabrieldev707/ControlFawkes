# Fase 2A — progresso

Data: 2026-07-22

Branch: `feat/controlfawkes-phase-2-intelligence`, criada a partir de `a99beef`
(topo do MVP, CI verde).

> **Dependência:** esta branch sai do MVP, que **ainda não foi mergeado** na
> `main` (PR #1). Ela contém todos os commits do MVP mais os da Fase 2A. Se o
> MVP for mergeado antes, esta branch continuará aplicável; se o MVP for
> alterado, será necessário incorporar as mudanças aqui antes do merge.

## Escopo desta rodada

Aprovado apenas o bloco determinístico:

| Fatia | Situação |
| --- | --- |
| 0 — busca allowlisted nas plataformas | Concluída |
| 1 — controle direcional | Concluída |
| 2 — escolha de plataforma | Concluída |
| 4 — links seguros do YouTube | Concluída |

Fora desta rodada, para a Fase 2B: contexto conversacional, agente, provider,
confirmação por agente, sessão de mídia e rastreamento de janela do Chrome.

## Fatia 0 — busca allowlisted

Formatos verificados contra os serviços reais antes de implementar, não
assumidos:

| Plataforma | URL | Verificação | Situação |
| --- | --- | --- | --- |
| YouTube | `/results?search_query=` | já em produção | Suportada |
| Spotify | `open.spotify.com/search/` | já em produção | Suportada |
| Netflix | `/search?q=` | 302 para login preservando a busca em `nextpage` | Suportada |
| Prime Video | `/search?phrase=` | 200 | Suportada |
| **Max** | — | `www.max.com/search` → `www.hbomax.com/search` responde 404; `play.max.com/search` descarta a consulta e cai na home | **Sem busca** |
| **Disney+** | — | `/search` responde 404; `/browse/search` cai numa página de UUID que também responde 404 | **Sem busca** |

Max e Disney+ ficaram de fora seguindo a instrução de não inventar URL. Abrir a
página inicial das duas continua funcionando; apenas a busca não existe. Elas
também não aparecem na escolha de plataforma, para não criar um beco sem saída.

A allowlist passou a ser tabelada — `(hostname, path, único parâmetro aceito)` —
em vez de condicionais soltas, mantendo o mesmo rigor: https obrigatório, sem
usuário/senha, sem porta, sem fragmento e um só parâmetro não vazio. A URL
continua sendo montada exclusivamente no backend.

### Parser

Prefixo e sufixo passaram a ter alcances diferentes:

- **prefixo** (`toca <plataforma> <consulta>`) aceita apenas plataformas
  pesquisáveis. Sem isso, `toca Max Richter` viraria busca no Max;
- **sufixo** (`toca <consulta> no <plataforma>`) aceita todas, porque a
  preposição desfaz a ambiguidade. Quando a plataforma não tem busca, a consulta
  é preservada e vira `NEEDS_PLATFORM`.

Verbos de vídeo adicionados: `assistir`, `assiste`, `quero assistir`,
`quero ver`, `passa`, `passar`, `ver`.

## Fatia 1 — controle direcional

Seis ações: `NAVIGATE_UP`, `NAVIGATE_DOWN`, `NAVIGATE_LEFT`, `NAVIGATE_RIGHT`,
`NAVIGATE_CONFIRM`, `NAVIGATE_BACK`. Mapeiam para `ARROW_*`, `ENTER` e `ESCAPE`,
que já eram teclas allowlisted — nenhuma tecla nova foi exposta.

`NAVIGATE_HOME` continua fora, sem comportamento seguro definido. Há teste
garantindo que ele é recusado como `UNSUPPORTED_MESSAGE`.

Contrato separado do teclado remoto, conforme decidido: o direcional repete ao
segurar e o teclado não; compartilhar o tipo faria os dois dividirem o mesmo
limite de taxa.

Repetição controlada:

- setas repetem, com 400 ms de espera e 120 ms de intervalo, para o toque curto
  não disparar repetição;
- OK e voltar **nunca** repetem: entrariam em vários itens ou sairiam de várias
  telas. Guarda de ~3/s por ação no backend;
- limite de 20/s por conexão para o direcional, independente do teclado. Há
  teste provando que inundar o direcional não consome a cota do teclado;
- soltar o dedo fora do botão, trocar de tela ou desmontar a tela param a
  repetição.

A mensagem não tem payload: não há como pedir tecla arbitrária por ela.

O direcional é o único controle que não espera a resposta anterior. Se
esperasse, segurar a seta enviaria um único comando.

## Fatia 2 — escolha de plataforma

Conteúdo sem plataforma deixou de virar "não entendi". O backend responde
`NEEDS_PLATFORM` com a consulta preservada e o frontend pergunta onde procurar.

Cobre dois casos:

- `Interestelar` — nenhuma plataforma citada;
- `coloca The Last of Us no Max` — plataforma citada, mas sem busca.

A ordem das sugestões é determinística e vem do backend: verbo musical (`toca`)
coloca Spotify e YouTube na frente. Sai do verbo que o usuário escolheu, nunca
de classificação do conteúdo, e apenas reordena — nenhuma opção é removida.

Ao escolher, o cliente envia `SEARCH_MEDIA` apenas com plataforma e consulta.

A escolha pendente some ao escolher, ao cancelar e a qualquer `COMMAND_RESULT`
ou `ERROR`, e é ignorada quando o `requestId` não é o atual.

Pedidos vagos (`escolhe um filme`) continuam `UNKNOWN`: não há o que pesquisar.

## Fatia 4 — links seguros do YouTube

Aceita `youtube.com`, `www.`, `m.`, `music.` e `youtu.be`.

Validação por forma, não por confiança no host:

- https obrigatório — bloqueia de uma vez `file:`, `javascript:`, `data:` e http;
- hostname comparado por **igualdade exata**, nunca por sufixo. `endswith`
  aceitaria `youtube.com.evil.example`;
- sem usuário, senha ou porta;
- path previsto e id de vídeo no formato real (11 caracteres base64url);
- nenhum redirect é seguido antes de validar.

A URL **não é repassada**: é reconstruída a partir do id validado. Qualquer
parâmetro não reconhecido é descartado em vez de confiado, inclusive listas e
rastreadores. Só `t` (tempo) sobrevive, e apenas em formato numérico.

Duas camadas independentes: o parser de links e a allowlist do launcher, que
exige o mesmo formato de id.

### Achado durante a implementação

`javascript:alert(1)` e `file:///C:/...` caíam na escolha de plataforma — a
interface se oferecia para pesquisar isso na Netflix. Não era explorável (a
consulta é codificada e passa pela allowlist), mas era higiene ruim. Esquemas
perigosos passaram a ser recusados por prefixo exato, o que não afeta títulos
legítimos com dois-pontos, como `Se7en: ...`.

Corrigido também um bug do espelho no frontend: `isSearchMediaData` ainda só
aceitava YouTube e Spotify, então um resultado de busca da Netflix seria
descartado no parser e o usuário não veria nada.

## Fatia 9 — sessão de mídia: por que ficou fora

A proposta previa armazenar um "identificador seguro do processo" da janela
aberta pelo ControlFawkes. Teste feito nesta máquina antes de decidir:

```text
PID lançado: 24772 | ainda vivo após 4s: False
processos chrome antes=15, depois=18
```

O processo retornado por `Popen` **morre em segundos**: ele apenas repassa a aba
para a instância do Chrome já aberta, que é quem de fato abre a janela. Portanto
o PID não serve como identificador.

Caminhos possíveis, para avaliar depois:

1. **Enumerar janelas após o lançamento** (`EnumWindows` + `GetWindowThreadProcessId`),
   casando pelo processo do Chrome e pelo título. Frágil: depende de título, que
   é justamente o que a fatia queria evitar, e há corrida entre abrir e enumerar.
2. **Chrome DevTools Protocol** (`--remote-debugging-port`). Dá identidade de
   aba real e estável, mas exige subir o Chrome com a porta aberta, o que é uma
   superfície de ataque local nova e mudaria como o navegador é iniciado.
3. **Perfil dedicado** (`--user-data-dir` próprio). Isola o que é do
   ControlFawkes do Chrome pessoal e torna o processo rastreável, ao custo de o
   usuário não ter sessões nem login nas plataformas.

Nenhuma é obviamente correta; a decisão fica para a Fase 2B.

## Decisões registradas para a Fase 2B

- o contexto conversacional deve ser associado ao `deviceId`, **nunca** ao
  socket: a reconexão é contínua no celular e apagaria uma interação pendente;
- a confiança do modelo não será trava principal. A política é por tipo de ação:
  ações reversíveis podem executar; abrir link, digitar texto ou trocar de
  plataforma sempre exigem confirmação; `confidence` só auxilia desempate.

## Estado

```text
AUTOMATED TESTS: PASS
MANUAL IPHONE TESTS: PENDING USER VALIDATION
AGENT: NOT IMPLEMENTED
MERGE: BLOCKED UNTIL MANUAL APPROVAL
```
