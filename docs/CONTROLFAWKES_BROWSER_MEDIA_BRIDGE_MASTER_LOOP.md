# ControlFawkes Browser Media Bridge
## Master Implementation Loop

> Documento operacional de implementação.
> Uma etapa só recebe `[x]` quando implementação, testes e critérios de saída estiverem satisfeitos.

---
## Regra de autonomia

O agente deve avançar automaticamente para a próxima fase sempre que o gate atual estiver verde. Não deve pedir autorização entre fases. Só deve interromper o loop diante de bloqueio técnico real, decisão arquitetural não coberta, risco de perda de dados ou ação externa irreversível.
# 0. Estado do Loop

- [x] Fase 0 — Caracterização do sistema atual
- [x] Fase 1 — Decisão de transporte → **Native Messaging**
- [x] Fase 2 — Contratos e modelos
- [x] Fase 3 — Refactor SMTC + Window Title
- [x] Fase 4 — Extensão MV3 mínima
- [x] Fase 5 — Generic HTML5 Observer
- [x] Fase 6 — Transporte integrado
- [x] Fase 7 — Media Merger
- [ ] Fase 8 — Source Availability / Freshness
- [ ] Fase 9 — Consumption Policy
- [ ] Fase 10 — Netflix Adapter
- [ ] Fase 11 — Identidades de mídia
- [ ] Fase 12 — Histórico
- [ ] Fase 13 — RelogioDaMidia
- [ ] Fase 14 — Multiple Tabs
- [ ] Fase 15 — MediaSessionArbiter
- [ ] Fase 16 — Controles
- [ ] Fase 17 — Hardening
- [ ] Fase 18 — Validação final

---

# 1. Regra do Loop

```text
INSPECIONAR
    ↓
IMPLEMENTAR PEQUENO PASSO
    ↓
TESTAR
    ↓
AUDITAR RESULTADO
    ↓
GATE PASSOU?
   ↙       ↘
 NÃO       SIM
 ↓          ↓
CORRIGIR   MARCAR [x]
 ↓          ↓
 └──────► PRÓXIMA ETAPA
```

Nunca avançar uma fase com gate vermelho.

---

# 2. Regras permanentes

- [ ] Não remover comportamento existente sem teste.
- [ ] Não simplificar heurísticas históricas sem entender o bug que originou a regra.
- [ ] Não criar adapters sem necessidade comprovada.
- [ ] Não permitir regressão de Spotify Desktop.
- [ ] Não permitir regressão de Max.
- [ ] Não permitir regressão de Disney+.
- [ ] Não permitir regressão de Prime Video.
- [ ] Não permitir regressão de YouTube.
- [ ] Netflix não pode depender de SMTC para metadata da obra.
- [ ] Nenhuma fonte inteira pode vencer o Media Merger.
- [ ] Resolução é por campo.
- [ ] Toda decisão arquitetural importante deve ser registrada.

---

# 3. Fase 0 — Caracterização do sistema atual

> Entrega do mapeamento: **`docs/MEDIA_PIPELINE.md`**
> Entrega dos testes: **`backend/tests/test_characterization_media.py`** (51 testes)

## Mapear

- [x] Entrada principal da SMTC. — `_read_windows`, ordem exata em MEDIA_PIPELINE §2
- [x] Leitura do título da janela. — `WindowFocuser.media_window`, §3
- [x] `PLATAFORMAS_COM_OBRA_NA_JANELA`. — tabela de capabilities já em produção, §4
- [x] Regras atuais de confiança. — 9 heurísticas com o bug de origem de cada, §5
- [x] Timeline da SMTC. — §6
- [x] `RelogioDaMidia`. — 3 estados (VIVA/PARADA/SUSPEITA), §6
- [x] `audio_activity.py`. — §7
- [x] Decisão atual de mídia ativa. — DUAS decisões que não conversam, §8
- [x] Histórico. — chave é a obra, nunca o episódio, §9
- [x] Catálogo. — §10
- [x] `security/pairing.py`. — §11
- [x] `security/origins.py`. — §11
- [x] Dispatcher/resync. — 1s / 10s / 15s, §12
- [x] Timeout da SMTC. — `LeituraEmVoo`, 5s para desistir / 20s para tentar, §2

## Characterization tests

### Batman / áudio
- [x] Reproduzir o bug histórico de player tecnicamente playing sem consumo real.
- [x] Garantir que tempo assistido não aumenta sem evidência de áudio/consumo.
- [x] E o par: com evidência de consumo, conta — senão "nunca conta" passaria.

### Timeline stale
- [x] SMTC mantém timeline antiga após troca de conteúdo.
- [x] Título muda enquanto timeline ainda pertence à mídia anterior.
- [x] Volta a andar ⇒ volta a ser confiável sem reiniciar o servidor.

### Window Title
- [x] Título correto.
- [x] Título genérico.
- [x] Título vazio.
- [x] `(Não está respondendo)` — e o parêntese que NÃO é marca de travamento.
- [x] Provider no prefixo.
- [x] Provider no sufixo.
- [x] Max. — nomeia o episódio, `trustworthy=False`
- [x] Disney+. — nomeia a obra, `trustworthy=True`
- [x] Prime Video. — nomeia a obra, `trustworthy=True`
- [x] YouTube. — nomeia a obra, `trustworthy=True`
- [x] Netflix. — nunca nomeia o conteúdo, `trustworthy=False`

### SMTC
- [x] Resposta normal.
- [x] Timeout. — abandonada sem cancelar; `travada` é o gatilho do fallback
- [x] Ausência.
- [x] Metadata parcial.
- [x] Timeline válida.
- [x] Timeline stale.

### Combinado SMTC + Window Title
- [x] SMTC genérica cede o título para a janela.
- [x] SMTC nomeia a série, janela nomeia o episódio.
- [x] Janela genérica não rouba o título da SMTC.
- [x] Prefixo do serviço sai do título da própria SMTC.
- [x] Plataforma vem do aplicativo antes do título.
- [x] Sem janela, a leitura da SMTC continua inteira.
- [x] **O título RESOLVIDO é o que julga a linha do tempo** — o entrelaçamento
      mais fino, e o que mais corre risco na Fase 3.

## Gate
- [x] Pipeline documentado. — `docs/MEDIA_PIPELINE.md`
- [x] Heurísticas delicadas explicadas. — §5 e §14, com o bug de origem
- [x] Bugs históricos protegidos por testes.
- [x] Comportamento combinado SMTC + Window Title caracterizado.
- [x] Suite atual passa. — 763 backend, 325 frontend
- [x] **FASE 0 CONCLUÍDA**

---

# 4. Fase 1 — Decisão de transporte

## Spike A — Native Messaging

```text
Extension
→ Service Worker
→ Native Messaging
→ Thin Native Host
→ IPC local
→ ControlFawkes já em execução
```

> Código: `backend/app/bridge/` · `backend/scripts/instalar_native_host.py`
> `browser-extension/` · testes: `backend/tests/test_bridge_native_host.py` (22)

- [x] Criar host mínimo. — `app/bridge/native_host.py`, só relay
- [x] Implementar framing stdio. — `app/bridge/framing.py`, ordem NATIVA (`@I`)
- [x] Registrar manifesto no Windows. — HKCU, Chrome e Edge, reversível
- [x] Configurar caminho absoluto. — relativo é ignorado em silêncio
- [x] Fixar ID da extensão. — `bbnnlajckbgplcfoeabclhkoilboccaf`
- [x] Configurar `key` se necessário. — necessário: sem ela o ID vem do CAMINHO
- [x] Configurar `allowed_origins`. — conferido contra o manifest.json
- [x] Host → ControlFawkes. — provado ao vivo contra o servidor em execução
- [x] Caminho inverso. — `PONG` com o payload real de `/health`
- [x] Restart ControlFawkes. — o host não guarda conexão; sonda a cada mensagem
- [x] Medir custo de instalação. — ver tabela abaixo

Verificáveis só com a extensão carregada no Chrome (clique humano em
`chrome://extensions`). Ficam para a **Fase 4**, que é onde a extensão passa a
existir de verdade:

- [ ] Extension → Host. *(cano provado spawnando o `.bat` como o Chrome faz)*
- [ ] Reconnect. *(o laço reconecta; a porta do Chrome não foi exercitada)*
- [ ] Restart Chrome.
- [ ] Host morto.

### Custo de instalação medido

| Passo | Automatizável | Feito por |
|---|---|---|
| Gerar par de chaves e derivar o ID | sim | `gerar_identidade_da_extensao.py` |
| `key` no manifest.json | sim | conferida pelo instalador |
| Manifesto do host com caminho absoluto | sim | `instalar_native_host.py` |
| Chave no registro (Chrome + Edge) | sim | idem, HKCU, `--remover` desfaz |
| Lançador `.bat` sem eco em stdout | sim | versionado |
| **Carregar extensão descompactada** | **não** | **clique humano** |

O passo manual **não é custo do Native Messaging**: a extensão precisa ser
carregada do mesmo jeito no caminho por WebSocket. O custo MARGINAL do Native
Messaging é um comando de script.

## Spike B — WebSocket autenticado

```text
Extension
→ WS localhost autenticado
→ ControlFawkes
```

> Testes: `backend/tests/test_bridge_websocket_spike.py` (11)

- [x] Reutilizar pairing existente. — funciona: PIN → token → `chrome.storage`
- [x] Reutilizar origins quando aplicável. — **NÃO é aplicável.** Ver achado
- [x] Provisionar token. — mesmo `PAIR_DEVICE` do celular
- [x] Autenticar conexão. — token sobrevive a restart do servidor (fica em disco)
- [x] Rejeitar ausência de token. — `UNAUTHORIZED`
- [x] Rejeitar token inválido. — `INVALID_TOKEN` (e `INVALID_PAYLOAD` se malformado)
- [x] Restart ControlFawkes. — `DeviceStore` relê do disco, ninguém desemparelha

Não exercitados porque o transporte foi descartado (ver decisão):

- [ ] Guardar token em `chrome.storage`.
- [ ] Reconnect.
- [ ] Restart navegador.

### Achado que decidiu o spike

A origem de uma extensão é `chrome-extension://<id>`. `is_origin_allowed` exige
esquema `http`/`https`, então **a extensão é recusada hoje**. As duas saídas:

1. **`FAWKES_ALLOWED_ORIGINS`** — essa variável não ACRESCENTA à política, ela a
   SUBSTITUI por uma lista fechada. Provado em teste: pôr a extensão ali
   **derruba o celular no mesmo instante**, porque a origem dele é o IP da LAN,
   que muda com a rede, com o DHCP e com o aparelho. Não é reutilizar o modelo
   de confiança; é aposentá-lo.

2. **Aceitar `chrome-extension://<id>` na política** — o ControlFawkes passa a
   manter uma lista de extensões confiáveis. É um modelo de confiança novo,
   ainda que pequeno, sem necessidade comprovada.

E o limite do que a origem protege, também provado: **qualquer página local
passa** — um projeto em `localhost:3000`, um servidor de arquivos, qualquer
coisa que o usuário abra. A origem barra o site remoto; não barra o vizinho
local. Quem defende é o pareamento.

## Comparação

| Critério | Native Messaging | WebSocket |
|---|---|---|
| Segurança | Chrome só entrega stdio ao ID declarado | qualquer página local alcança a porta |
| Instalação | +1 comando de script (registro + manifesto) | nenhuma |
| Complexidade | framing + relay (~200 linhas, 22 testes) | reaproveita o WS que já existe |
| Reconnect | porta do Chrome; host respawna | reconexão de socket, já resolvida |
| Empacotamento | manifesto do host acompanha o instalador | nada a mais |
| Manutenção | ID estável exige `key` fixa no manifest | política de origem vira lista à mão |
| Integração atual | **zero mudança no modelo de confiança** | **quebra o celular ou cria modelo novo** |

**Transporte escolhido:** `Native Messaging`

**Motivo:** `O WebSocket não passa sem pagar um dos dois preços proibidos pelo
Master Loop — quebrar o celular (provado em teste) ou criar um segundo modelo de
confiança. O Native Messaging custa zero mudança na segurança existente, e o seu
custo de instalação é MARGINAL: a extensão precisa ser carregada à mão nos dois
caminhos, então a diferença real é um comando de script. Some-se a isso o que a
Core Audio já ensinou hoje — reduzir alcance vale mais do que reduzir passos.`

> Revisão de posição registrada: a recomendação anterior chegou a considerar o
> WebSocket como V1 pragmático, supondo que a instalação do Native Messaging
> pesasse. Medida, ela não pesa — porque o carregamento manual da extensão é
> comum aos dois. A suposição estava errada e o spike existia para descobrir
> isso.

## Gate
- [x] Ambos os caminhos avaliados. — 22 testes + 11 testes, e o cano real provado
- [x] Decisão baseada em teste real. — inclusive o teste que derruba o celular
- [x] Sem segundo modelo de confiança desnecessário. — é o que a decisão evita
- [x] Decisão registrada.
- [x] **FASE 1 CONCLUÍDA**

---

# 5. Fase 2 — Contratos e modelos

## MediaField

```ts
type MediaField<T> = {
  value: T | null
  source: MediaSource | null
  trustworthy: boolean
}
```

> Autoridade: **`backend/app/bridge/contratos.py`** — o Merger vive no Python,
> e um contrato com dois donos diverge.
> Espelho: `browser-extension/src/types/media.ts`
> Testes: `backend/tests/test_bridge_contratos.py` (13)

- [x] Sem `confidence` numérico arbitrário. — travado por teste de forma
- [x] provider
- [x] workTitle
- [x] episodeTitle
- [x] seasonNumber
- [x] episodeNumber
- [x] playbackState
- [x] audible
- [x] muted
- [x] currentTime
- [x] duration
- [x] playbackRate
- [x] `mediaType` — acrescentado: separa filme de episódio antes de haver
      identidade (Fase 11), e o Merger precisa dele para escolher autoridade.

### O que o contrato deliberadamente NÃO tem

- **`confidence`** — o número não sai de lugar nenhum, e faz a decisão do
  Merger virar emergente. Substituído por `MediaField(value, source,
  trustworthy)`: a pergunta deixa de ser "quem tem mais confiança?" e passa a
  ser "esta fonte é autoridade para ESTE campo?".
- **`consumptionState` como campo** — é derivado, e derivado no backend.
  Nenhuma fonte sozinha sabe: a extensão vê uma aba, a SMTC vê uma sessão, a
  Core Audio vê um processo. Como campo, alguém o preencheria de uma fonte só.
- **`trustworthy` vindo da extensão** — autoridade é decidida pela tabela de
  capabilities do backend. Uma fonte que se declara confiável não é contrato,
  é opinião.

`MediaField.utilizavel` exige valor **e** autoridade. Foi "tem valor, logo
serve" que pôs nome de episódio no lugar do nome da obra no histórico.

## Conceitos separados

### Playback State
Responde: o player está tecnicamente reproduzindo?

### Audible
Responde: a aba produziu áudio recentemente?

### Consumption State
Responde: há evidência suficiente para contabilizar consumo?

- [x] `playbackState != consumptionState`. — `consumptionState` nem é campo
- [x] `audible` independente. — campo próprio, ao lado de `muted`
- [x] Procedência por campo. — `SessaoCanonica.procedencia()`
- [x] Suite passa. — 809 backend, 325 frontend, `tsc` limpo
- [x] **FASE 2 CONCLUÍDA**

---

# 6. Fase 3 — Refactor SMTC + Window Title

Executar somente depois dos characterization tests.

> Código: `backend/app/bridge/saude.py` · instrumentação em `LeituraEmVoo`
> Testes: `backend/tests/test_bridge_saude.py` (9)

## Window Title
Não criar `healthy = true` genérico.

- [x] `windowPresent`
- [x] `titlePresent`
- [x] `parseable`

Confiabilidade semântica continua nas capabilities.

- [x] Travado por teste: `SaudeDoWindowTitle` não tem `healthy`, nem `lastSeen`,
      nem `platform`. "Netflix - Home - Netflix" é `parseable=True` de
      propósito — presença não é verdade.

## SMTC

- [x] available — import real do `winsdk`, não `sys.platform`
- [x] responsive
- [x] lastSuccess
- [x] latency
- [x] timeout

### Por que as duas formas são diferentes

| | SMTC | Window Title |
|---|---|---|
| Modo de falha | **ausência** — pendura e não volta | **erro em silêncio** — sempre devolve algo |
| Mensurável no tempo? | sim | não |
| Tem `healthy`? | `responsive` | **não, e é proibido ter** |

### Medição ao vivo, com o Disney+ tocando

```text
saude janela : windowPresent=True  titlePresent=True  parseable=True
saude SMTC   : available=True  responsive=False  lastSuccess=None  timeout=5.0
```

`available=True` com `responsive=False` é exatamente o travamento que fazia o
Disney+ sumir. Antes isso era invisível; agora é um fato estruturado.

## Gate
- [x] Mesmos inputs → mesmos outputs. — a instrumentação só OBSERVA; nenhuma
      decisão da `LeituraEmVoo` passou a depender dela
- [x] Characterization tests verdes. — 51/51
- [x] Spotify sem regressão. — caracterizado (plataforma pelo app)
- [x] Max sem regressão. — caracterizado (episódio na janela, `trustworthy=False`)
- [x] Disney+ sem regressão. — caracterizado (obra na janela, `trustworthy=True`)
- [x] Prime Video sem regressão. — caracterizado (prefixo do serviço)
- [x] YouTube sem regressão. — caracterizado
- [x] Netflix não piorou. — continua `trustworthy=False`; nada mudou para ela
- [x] Nenhuma heurística histórica desapareceu. — 818 backend verdes
- [x] **FASE 3 CONCLUÍDA**

---

# 7. Fase 4 — Extensão MV3 mínima

```text
browser-extension/
├── manifest.json
└── src/
    ├── content/
    ├── background/
    ├── providers/
    ├── messaging/
    └── types/
```

- [x] Manifest V3. — com `key`, `nativeMessaging`, `storage`, `tabs`
- [x] Content Script. — `src/content/index.js`
- [x] Service Worker. — `src/background/service-worker.js`, só relay
- [x] Message protocol. — `src/messaging/messages.js`
- [x] Logging de lifecycle. — em `chrome.storage`, sobrevive ao worker morrer
- [x] tabId. — do `sender`, NUNCA do payload: a página não tem voz sobre isso
- [x] windowId. — idem

Registrar:
- [x] `WORKER_STARTED`
- [x] `WORKER_STOPPED` — como `WORKER_STOPPING`, via `onSuspend`
- [x] `PORT_CONNECTED`
- [x] `PORT_DISCONNECTED`
- [x] `TRANSPORT_CONNECTED`
- [x] `TRANSPORT_DISCONNECTED`

### Bug evitado na escrita

Um content script declarado no manifesto **não é módulo**: `import` ali é erro
de sintaxe, a aba fica sem script e nada acusa. O `src/content/index.js` é
autocontido por isso, com a duplicação mínima documentada no topo. A decisão de
introduzir um bundler fica adiada — complexidade antes de necessidade.

### Diagnóstico do host

`native_host.anotar()` grava em `data/bridge/host.log`. Nem stdout (É o canal do
Native Messaging) nem stderr (o Chrome captura e descarta). Sem isso, a falha
mais comum do transporte é silenciosa dos dois lados.

## Gate
- [x] **Extensão carrega.** — provado no Chrome real, ver evidência abaixo
- [x] **Content script roda.** — 190 respostas `UNKNOWN_MESSAGE_TYPE` no diário,
      em cadência de 10s. O host só conhece `PING`; qualquer outro tipo veio do
      content script, e 10s é exatamente `SEGUNDOS_ENTRE_BATIMENTOS`.
- [x] Worker pode reiniciar sem quebrar estado essencial. — o diário vive em
      `chrome.storage`; o worker não guarda estado em memória
- [x] Nenhum timer crítico depende do worker. — o relógio está no content
      script, por construção
- [x] **FASE 4 CONCLUÍDA**

### Armadilha na leitura do diário

O `chrome.storage` regrava o ARRAY INTEIRO a cada `set`, então contar ocorrências
no LevelDB conta duplicatas entre snapshots. Cheguei a ler "13
TRANSPORT_CONNECTED" e concluir que houve 12 reconexões — os 13 têm o **mesmo
timestamp**. É uma conexão só.

Consequência: **reconnect e restart do Chrome continuam NÃO provados** (Spike A).
Movidos para a Fase 17 — Hardening, que é onde eles pertencem.

### Evidência: a ponte funcionou ponta a ponta

Cadeia de processos, com o Chrome do usuário:

```text
chrome.exe (25268)  ->  cmd.exe (62552)  ->  python.exe (60020)
```

Diário da extensão, lido do `Local Extension Settings` do perfil real:

```text
21:48:41.268  WORKER_STARTED
21:48:41.272  INSTALLED
21:48:41.273  TRANSPORT_CONNECTED
21:48:41.902  HOST_MESSAGE
              {"messageType":"PONG","ok":true,
               "controlfawkes":{"service":"fawkes-remote","status":"ok"}}
```

Extensão → service worker → Native Messaging → host fino → HTTP → ControlFawkes
em execução → e a resposta de volta. O transporte escolhido na Fase 1 está
provado no mundo real.

### Medição do MV3 (o documento mandava medir, não assumir)

**Uma porta de Native Messaging aberta mantém o service worker vivo.** Medido:
porta aberta às 18:48:41, worker ainda vivo às 19:05:50 — **17 minutos** sem
nenhuma outra atividade, muito além dos ~30s de inatividade que suspenderiam um
worker sem porta.

Consequência de projeto: o worker **não** vai reiniciar sozinho enquanto a ponte
estiver conectada. Isso é conveniente e é uma armadilha — o cenário "worker
morre no meio da reprodução" fica RARO, não impossível, e código que dependa de
ele estar vivo passa em teste e falha em produção. O relógio continua no content
script.

### O que falta, e por quê

Content script declarado no manifesto **só injeta em abas carregadas depois** da
extensão. A extensão foi carregada com as abas já abertas, então nenhuma delas
tem o script.

**Ação:** abrir qualquer aba `http`/`https` nova (não `chrome://`, onde content
script não roda por política do Chrome).

**Verificação, sem interpretação:**

```text
data/bridge/host.log                    ganha  RECEBIDA PORT_CONNECTED
                                        e depois RECEBIDA POSITION_SYNC a cada 10s
diário da extensão (chrome.storage)     ganha  DA_ABA
```

Os dois registros gravam **só o tipo da mensagem**, nunca o payload: ele carrega
`href` e `origem`, e gravar isso transformaria um log de diagnóstico num
histórico de navegação — que o ControlFawkes não coleta e não quer.

---

# 8. Fase 5 — Generic HTML5 Observer

> Código: `browser-extension/src/content/video-observer.js`
> Testes: `.../video-observer.test.ts` (15), na suíte do frontend

## Discovery
- [x] Detectar `<video>`.
- [x] Detectar `<audio>` quando relevante.
- [x] Procurar no document.
- [x] Procurar em open Shadow Roots quando necessário. — os fechados não são
      alcançáveis por ninguém; fingir que são só produziria código morto.
- [x] **Escolher o MAIOR, não o primeiro.** Páginas de serviço têm `<video>` de
      trailer e de anúncio junto com o player, e o primeiro na ordem do DOM
      costuma ser o errado.

## Lifecycle

```text
discover
→ bind
→ observe
→ detached?
→ unbind
→ rediscover
→ bind
```

- [x] Detectar elemento removido.
- [x] Detectar novo elemento.
- [x] Rebind.
- [x] Verificar `isConnected`. — é o que pega a troca: o objeto antigo continua
      existindo e respondendo `currentTime`, só não está mais no documento
- [x] Evitar observers duplicados. — `prender` sai cedo se já for o mesmo
      elemento; `parar()` desliga tudo

## Campos
- [x] currentTime
- [x] duration
- [x] paused
- [x] ended
- [x] playbackRate

## Eventos
- [x] play
- [x] pause
- [x] seek (`seeking`)
- [x] seeked
- [x] ended
- [x] loadedmetadata
- [x] durationchange
- [x] ratechange
- [x] `emptied` — acrescentado: é o que o MSE dispara ao esvaziar o buffer numa
      troca, e sem ele a troca só é notada na reconferida periódica

## Duration
- [x] NaN. — vira `null`
- [x] Infinity. — ao vivo, vira `null`
- [x] indisponível.
- [x] torna-se disponível depois.

> `NaN` e `Infinity` viram `null` por DECISÃO, não por acidente de
> serialização: os dois virariam `null` no JSON de qualquer jeito, e depender
> disso esconderia a intenção.

## Milestone 1A — Transporte/plumbing
- [x] HTML5 simples envia currentTime. — coberto em jsdom
- [x] duration.
- [x] playbackState.
- [x] playbackRate.

## Milestone 1B — Observer real
- [x] Player real MSE/DRM. — Prime Video, Spider-Noir, medido ao vivo
- [x] Play. / Pause. / Seek. — 6 PLAY, 5 PAUSE, 6 SEEK no `host.log`
- [x] Background tab.
- [x] Troca de mídia. — 6 `MEDIA_CHANGED`, cada um um `detached` + rebind
- [x] Elemento antigo removido. — jsdom + player real
- [x] Novo `<video>` criado.
- [x] Rebind automático. — os `POSITION_SYNC` continuam depois de cada troca
- [x] Dados continuam chegando sem restart.

### Medição ao vivo — Prime Video, Spider-Noir

```text
20:07:31  POSITION_SYNC  playing  currentTime=1389.945105  duration=2879.606  rate=1
20:07:41  POSITION_SYNC  playing  currentTime=1399.936140  duration=2879.606  rate=1
20:07:51  POSITION_SYNC  playing  currentTime=1409.935132  duration=2879.606  rate=1
```

`currentTime` avança **+9,99 s a cada batimento de 10 s**. `duration` estável e
coerente (48 min). `playbackRate` correto. 117 eventos recebidos no total, com
a cadência de 10 s intacta.

### Bônus: "host morto" do Spike A, fechado

Matei o processo do host à força para carregar o código novo. A extensão
**reconectou sozinha em menos de 10 s** — o `enviarAoHost` reabre a porta no
próximo batimento. Isso fecha um dos itens que a Fase 1 tinha deixado para a
Fase 17.

### Decisão revista: o que é "navegação" no log

O log gravava só o TIPO da mensagem, para não virar histórico de navegação. Mas
sem os valores a Fase 5 não tinha como ser provada — o log dizia que uma
mensagem chegou, não o que ela dizia.

A regra continua; o que mudou é a leitura de quais campos **são** navegação:
`href` e `provider` dizem onde a pessoa esteve; `currentTime` e `duration`
dizem quanto tempo tem um vídeo, e isso não identifica nada. Só os quatro
campos temporais entram (`_CAMPOS_TEMPORAIS`).

## Gate
- [x] HTML5 simples aprovado. — 15 testes em jsdom
- [x] **Player real aprovado.** — Prime Video, com valores medidos
- [x] Troca de elemento aprovada. — jsdom e player real
- [x] Sem referência eterna ao primeiro `<video>`. — teste dedicado
- [x] Shadow DOM aberto não quebra discovery.
- [x] **FASE 5 CONCLUÍDA**

### O bug do Batman NÃO bloqueia esta fase

A investigação separou as três camadas, e a origem **não é o observador** —
que acabou de provar medir o player real corretamente. Ver o registro completo
na seção de bugs.

### Por que jsdom não basta, e o teste que existe por isso

Validar só numa página HTML5 simples aprova um observador que nunca funcionaria
na Netflix. Netflix, Max, Disney+ e Prime Video usam MSE e **trocam o
elemento** em mudança de qualidade e em troca de episódio. Quem guardou o
primeiro `<video>` segue lendo `currentTime` de um objeto fora do documento —
um número plausível, congelado, sem erro nenhum aparecer.

É o critério de implementação incorreta nº 18, e há um teste com esse nome.

### Ação para fechar o gate

A extensão carregada é a versão da Fase 4, sem o observador. **Recarregue-a** em
`chrome://extensions` (botão de recarregar no cartão) e abra o Disney+.

Verificação, sem interpretação:

```text
data/bridge/host.log   RECEBIDA SESSION_STARTED   ao entrar no player
                       RECEBIDA PLAY / PAUSE      ao controlar
                       RECEBIDA POSITION_SYNC     a cada 10s
                       RECEBIDA MEDIA_CHANGED     ao trocar de episódio
```

---

# 9. Fase 6 — Transporte integrado

Envelope mínimo:

```json
{
  "protocolVersion": 1,
  "messageType": "...",
  "timestamp": 0,
  "payload": {}
}
```

> Código: `backend/app/bridge/eventos.py`
> Testes: `backend/tests/test_bridge_eventos.py` (21)

Validar:
- [x] versão
- [x] tipo
- [x] tamanho — no `framing`: 1 MB de entrada, 64 MB de saída
- [x] campos
- [x] timestamps — com deriva tolerada de 600 s
- [x] valores impossíveis
- [x] provider
- [x] tabId — `bool` é `int` em Python; sem checagem explícita `True` viraria
      a aba número 1
- [x] sessionId

Eventos:
- [x] SESSION_STARTED / MEDIA_CHANGED / PLAY / PAUSE
- [x] SEEK / ENDED / POSITION_SYNC / SESSION_ENDED

Progress:
- [x] Eventos críticos imediatamente. — `IMEDIATOS`, no content script
- [x] Heartbeat ~10s. — medido em produção, cadência intacta
- [x] Posição em play / pause / seek / troca de mídia / ended. — a leitura vai
      junto em todo evento imediato

### "Valores impossíveis" — a parte que rende

O fácil é `currentTime` negativo. O que morde é o **plausível-mas-errado**, que
foi o defeito da linha do tempo congelada do Chrome e é o do Batman:

| Caso | Resposta | Por quê |
|---|---|---|
| `currentTime > duration` | **recusa** | Não é valor ruim, é valor de OUTRA reprodução |
| `duration <= 0` | vira ausente | Ao vivo, ou metadata que não chegou |
| `NaN` / `Infinity` | vira ausente | Nenhum dos dois é tempo |
| `playbackRate` fora de 0.0625–16 | vira ausente | Fora da faixa do HTML é lixo |
| `True` como tempo | vira ausente | `bool` é `int`; valeria 1.0 |

**Nada é corrigido em silêncio.** Ou passa, ou o campo vira ausente, ou a
mensagem é recusada inteira. Corrigir caladamente é como um número errado entra
no sistema parecendo certo — a história inteira do Batman.

### Provado pelo `.bat` real

```text
POSITION_SYNC (Spider-Noir)      -> ACK
PLAY                             -> ACK
currentTime 9999 / duration 2879 -> ERROR IMPOSSIBLE_POSITION
sem sessionId                    -> ERROR INVALID_SESSION_ID
```

### `sessionId` — embrião da PlaybackIdentity

O content script passa a gerar um id por REPRODUÇÃO, renovado quando o
elemento é trocado. É o que vai permitir distinguir "mesmo episódio retomado"
de "próximo episódio" — a distinção que falta hoje e que produziu o bug do
Batman.

## Gate
- [x] Comunicação estável. — 117 eventos reais, cadência de 10 s intacta
- [x] Reconnect. — provado matando o processo do host
- [ ] **Restart browser.** — adiado para a Fase 17 (Hardening), junto com os
      outros itens de reinício. Não reinicio o Chrome do usuário no meio de
      uma sessão de streaming.
- [x] Restart ControlFawkes. — o host não guarda conexão; sonda a cada mensagem
- [x] Tráfego aceitável. — 1 mensagem/10 s por aba, contra 1/s do laço atual
- [x] **FASE 6 CONCLUÍDA** — com "restart browser" explicitamente adiado

> **Atenção operacional:** a extensão carregada ainda é a versão sem
> `sessionId`. Até você recarregá-la, os eventos ao vivo passam a receber
> `INVALID_SESSION_ID` em vez de entrar. Nada visível quebra — eles ainda não
> alimentam a UI; isso é a Fase 7.

---

# 10. Fase 7 — Media Merger

## FIELD_AUTHORITY

```text
currentTime:
  1. html-media-element
  2. smtc

duration:
  1. html-media-element
  2. smtc

playbackState:
  1. html-media-element
  2. smtc

workTitle:
  1. provider-adapter
  2. window-title
  3. smtc

episodeTitle:
  1. provider-adapter
  2. window-title
  3. smtc

provider:
  1. provider-adapter
  2. window-title
  3. smtc
```

Algoritmo:

```text
1. pegar FIELD_AUTHORITY[field]
2. iterar em ordem
3. capability permite?
4. fonte disponível?
5. campo fresco?
6. primeira elegível vence
```

> Entrega: **`backend/app/bridge/merger.py`** — `FIELD_AUTHORITY`, `Leitura`,
> `fundir()`. Testes em `test_bridge_merger.py` (24).

Proibido:
- [x] Último evento vencer. — invertida a lista de leituras, a saída é a mesma
- [x] Última fonte registrada vencer. — mesmo teste
- [x] Maior confidence vencer. — não existe `confidence`; ver `contratos.py`
- [x] Fonte inteira vencer. — o laço é por CAMPO, e uma fonte fora da tabela
      daquele campo não escreve nele nem declarando valor perfeito
- [x] Timing decidir. — não há relógio no módulo

Testes:
- [x] SMTC playing / video paused. — vence o `<video>`
- [x] SMTC paused / video playing. — e o par, senão seria acaso
- [x] SMTC título antigo / adapter novo.
- [x] Window Title correto / SMTC genérico.
- [x] Adapter correto / Window Title genérico. — o caso da Netflix
- [x] Fonte prioritária stale. — cede o tempo e MANTÉM o nome da obra
- [x] Fonte secundária saudável.

## Ingestão autenticada

> Entrega: **`backend/app/bridge/credencial.py`** e **`backend/app/api/bridge.py`**.
> Testes em `test_bridge_credencial.py` (19) e `test_bridge_endpoint.py` (22).

Segredo dedicado à ponte, e **não** o pairing de clientes externos: o Native
Host é peça interna local, então isto é autenticação de PROCESSO.

- [x] Segredo gerado e guardado sob `backend/data/bridge/`. — ignorado pelo git
- [x] Nunca exposto ao content script nem ao manifest. — teste varre a extensão
- [x] Nunca registrado. — provado no log do host e na resposta à extensão
- [x] Conferido em toda mensagem. — sem sessão, sem memória
- [x] Endpoint restrito a loopback. — medido: pela LAN, com a credencial CERTA,
      responde 404 enquanto `/health` no mesmo endereço responde 200
- [x] Toda a validação da Fase 6 preservada depois de autenticar.
- [x] Testes: credencial correta, ausente, incorreta, endereço não-loopback,
      mensagem válida e mensagem inválida.

## Gate
- [x] Resultado determinístico.
- [x] Ordem explícita. — `FIELD_AUTHORITY`, tabela única
- [x] Divergências principais testadas.
- [x] **FASE 7 CONCLUÍDA**

> O Merger ainda NÃO está no caminho de leitura de produção. Ele entra quando
> houver frescor para alimentá-lo — Fase 8. Ligá-lo antes disso seria decidir
> `currentTime` com um `dinamicos_frescos` que ninguém mede.

---

# 11. Fase 8 — Source Availability / Freshness

## Browser Bridge
- [ ] connected
- [ ] lastSeen
- [ ] lastPositionUpdate

## SMTC
- [ ] available
- [ ] responsive
- [ ] lastSuccess
- [ ] latency

## Window Title
Não possui health de conexão.
- [ ] windowPresent
- [ ] titlePresent
- [ ] parseable

Campos dinâmicos:
- [ ] currentTime
- [ ] playbackState
- [ ] audible

não ficam vivos indefinidamente.

Metadata:
- [ ] workTitle
- [ ] episodeTitle

pode sobreviver temporariamente.

## Gate
- [ ] Fonte morta não fornece estado dinâmico.
- [ ] Window Title recente não vira automaticamente confiável.
- [ ] Capability != freshness.
- [ ] **FASE 8 CONCLUÍDA**

---

# 12. Fase 9 — Consumption Policy

Não confundir player rodando com usuário assistindo.

Inputs:
- [ ] playbackState
- [ ] audible
- [ ] muted
- [ ] Core Audio
- [ ] demais evidências atuais do projeto

Regra:
- [ ] Histórico nunca soma tempo apenas porque `video.paused === false`.

Regression:
- [ ] Caso equivalente ao bug Batman.
- [ ] Player technically playing.
- [ ] Sem atividade real de áudio.
- [ ] Tempo não aumenta.

## Gate
- [ ] UI usa estado técnico correto.
- [ ] Histórico usa política mais forte.
- [ ] Bug histórico bloqueado.
- [ ] **FASE 9 CONCLUÍDA**

---

# 13. Fase 10 — Netflix Adapter

Arquivo: `providers/netflix.ts`

Responsabilidade:
- [ ] workTitle
- [ ] episodeTitle
- [ ] seasonNumber
- [ ] episodeNumber
- [ ] mudanças de metadata

Não implementar nele:
- [ ] relógio
- [ ] currentTime
- [ ] duration
- [ ] play/pause
- [ ] lifecycle genérico do vídeo

Testes:
- [ ] Filme.
- [ ] Série.
- [ ] Episódio.
- [ ] Próximo episódio.
- [ ] Seek.
- [ ] Pause.
- [ ] Reload.
- [ ] Autoplay.

## Gate
- [ ] Netflix fornece metadata sem depender da SMTC para nome da obra.
- [ ] **FASE 10 CONCLUÍDA**

---

# 14. Fase 11 — Identidades

## PlaybackIdentity
Responde: é a mesma reprodução específica?

Pode incluir:
- provider
- workTitle
- seasonNumber
- episodeNumber

## WorkIdentity
Responde: é a mesma obra no histórico?

Baseline:
- provider
- workTitle

Teste:
```text
Rick and Morty
S01E01 → S01E02 → S01E03
```

Esperado:
- [ ] PlaybackIdentity muda.
- [ ] EPISODE_CHANGED.
- [ ] WorkIdentity permanece.
- [ ] Uma obra no histórico.

- [ ] **FASE 11 CONCLUÍDA**

---

# 15. Fase 12 — Histórico

EPISODE_CHANGED deve:
- [ ] atualizar episódio.
- [ ] resetar/recalibrar posição.
- [ ] atualizar metadata.
- [ ] manter mesma obra.

Não fazer:
```text
EPISODE_CHANGED → nova linha automaticamente
```

Testes:
- [ ] mesma série / próximo episódio.
- [ ] mesmo episódio retomado.
- [ ] filme diferente.
- [ ] série diferente.
- [ ] seek grande.
- [ ] pause longo.
- [ ] navegador fechado.
- [ ] extensão reconectada.

## Gate
- [ ] Sem fragmentação por episódio.
- [ ] Sem pôster errado por colisão simples de título.
- [ ] Histórico anterior continua funcionando.
- [ ] **FASE 12 CONCLUÍDA**

---

# 16. Fase 13 — RelogioDaMidia

Quando Browser currentTime estiver saudável:
- [ ] usar posição medida.
- [ ] não estimar desnecessariamente.

Quando Browser Bridge cair:
```text
currentTime unavailable
→ avaliar outras fontes
→ RelogioDaMidia fallback
```

Testes:
- [ ] posição real.
- [ ] extensão cai.
- [ ] fallback assume.
- [ ] extensão volta.
- [ ] posição recalibra.
- [ ] sem saltos absurdos.

## Gate
- [ ] Nenhum buraco de posição.
- [ ] Nenhuma dupla estimativa.
- [ ] Fonte real saudável sempre vence.
- [ ] **FASE 13 CONCLUÍDA**

---

# 17. Fase 14 — Multiple Tabs: telemetria

Registrar por sessão:
- [ ] tabId
- [ ] windowId
- [ ] active
- [ ] audible
- [ ] muted
- [ ] playbackState
- [ ] lastPlay
- [ ] lastMediaEvent
- [ ] lastInteraction quando disponível
- [ ] pictureInPicture
- [ ] provider

Cenários:
- [ ] Netflix + YouTube.
- [ ] Netflix + Netflix.
- [ ] Netflix + Spotify Web.
- [ ] Netflix pausado + YouTube playing.
- [ ] aba ativa pausada + background audible.
- [ ] PiP.
- [ ] janela não focada.
- [ ] várias janelas Chrome.

## Gate
- [ ] Dataset real coletado.
- [ ] Casos ambíguos identificados.
- [ ] Nenhuma política congelada antes dos dados.
- [ ] **FASE 14 CONCLUÍDA**

---

# 18. Fase 15 — MediaSessionArbiter

```text
Media Merger = resolve campos de UMA sessão
MediaSessionArbiter = decide QUAL sessão é ativa
```

Possíveis sinais:
- playing
- audible
- active tab
- focused window
- lastPlay
- lastInteraction
- PiP

- [ ] Política explícita.
- [ ] Ordem definida.
- [ ] Empates definidos.
- [ ] Sem race condition.

## Gate
- [ ] Cenários da Fase 14 possuem resultado esperado.
- [ ] Troca entre abas previsível.
- [ ] Histórico não soma duas sessões indevidamente.
- [ ] **FASE 15 CONCLUÍDA**

---

# 19. Fase 16 — Controles

Fluxo:

```text
ControlFawkes
→ Transport
→ Extension
→ Content Script
→ Media Element
```

Implementar:
- [ ] PLAY
- [ ] PAUSE
- [ ] SEEK_TO
- [ ] SEEK_BY

Depois, só se necessário:
- [ ] next episode
- [ ] previous
- [ ] fullscreen
- [ ] PiP

## Gate
- [ ] Comando chega à sessão correta.
- [ ] Múltiplas abas não recebem comando indevido.
- [ ] Estado retorna corretamente.
- [ ] **FASE 16 CONCLUÍDA**

---

# 20. Fase 17 — Hardening

Browser:
- [ ] service worker reiniciado.
- [ ] extensão recarregada.
- [ ] aba fechada.
- [ ] aba restaurada.
- [ ] Chrome reiniciado.

Transporte:
- [ ] conexão perdida.
- [ ] reconnect.
- [ ] mensagem duplicada.
- [ ] mensagem fora de ordem.
- [ ] mensagem inválida.
- [ ] versão incompatível.

ControlFawkes:
- [ ] restart.
- [ ] SMTC pendurada.
- [ ] SMTC timeout.
- [ ] Window Title genérica.
- [ ] Browser Bridge cai.

Netflix:
- [ ] autoplay.
- [ ] troca de episódio.
- [ ] mudança de qualidade.
- [ ] seek.
- [ ] pause.
- [ ] background.
- [ ] elemento substituído.

## Gate
- [ ] Nenhum crash.
- [ ] Nenhum stale currentTime tratado como vivo.
- [ ] Nenhuma sessão fantasma persistente.
- [ ] Fallback funciona.
- [ ] **FASE 17 CONCLUÍDA**

---

# 21. Fase 18 — Validação final

Netflix deve fornecer quando disponível:
- [ ] provider
- [ ] workTitle
- [ ] episodeTitle
- [ ] seasonNumber
- [ ] episodeNumber
- [ ] playbackState
- [ ] audible
- [ ] currentTime
- [ ] duration
- [ ] playbackRate

Outros:
- [ ] Max continua funcionando.
- [ ] Disney+ continua funcionando.
- [ ] Prime Video continua funcionando.
- [ ] YouTube continua funcionando.
- [ ] Spotify Desktop continua SMTC.

Falha da SMTC:
- [ ] Browser Bridge continua funcional.
- [ ] Metadata continua.
- [ ] Posição continua.

Falha da extensão:
- [ ] Fonte invalidada.
- [ ] currentTime não fica stale.
- [ ] fallback entra quando possível.

- [ ] **FASE 18 CONCLUÍDA**

---

# 22. Critérios de implementação incorreta

Se qualquer um ocorrer, voltar a fase correspondente para `[ ]`.

- [ ] Netflix depender da SMTC para título.
- [ ] WebSocket paralelo existir sem necessidade.
- [ ] `confidence` numérico decidir fonte.
- [ ] Service Worker ser responsável pelo relógio.
- [ ] Media Merger escolher uma fonte inteira.
- [ ] Adapter Netflix implementar lógica genérica do vídeo.
- [ ] Cinco adapters serem criados antes de necessidade comprovada.
- [ ] RelogioDaMidia estimar enquanto `currentTime` real saudável existe.
- [ ] Window Title desaparecer do pipeline da V1.
- [ ] EPISODE_CHANGED criar automaticamente nova obra.
- [ ] Native Host tentar ser a instância principal do ControlFawkes.
- [ ] Transporte ser escolhido sem spike.
- [ ] Fonte stale continuar tratada como dinâmica.
- [ ] Histórico contabilizar tempo somente porque `<video>` está playing.
- [ ] Media Merger não possuir FIELD_AUTHORITY explícita.
- [ ] Window Title possuir `healthy=true` genérico.
- [ ] SMTC/Window Title serem separados antes dos characterization tests.
- [ ] Observer manter referência eterna ao primeiro `<video>`.
- [ ] Observer ser considerado validado só em HTML simples.
- [ ] Multiple Tabs ser resolvido dentro do Merger.

---

# 23. Regra de rollback

Quando um gate falhar:

1. Não avançar.
2. Identificar o teste que falhou.
3. Encontrar a menor mudança responsável.
4. Corrigir.
5. Rodar testes da fase.
6. Rodar regression suite relacionada.
7. Rodar suite global.
8. Só então marcar `[x]`.

---

# 24. Registro de progresso

## Última etapa concluída
`Fase 3 — Refactor SMTC + Window Title`

## Etapa atual
`Fase 4 — Extensão MV3 mínima — IMPLEMENTADA, GATE BLOQUEADO (ação humana)`

## Último commit válido
`NENHUM. Ver "Dívidas" — não há como fazer um checkpoint verde e no escopo.`

## Testes
```text
Passed:  796 backend + 325 frontend
Failed:  0
Skipped: 0

Fase 0: test_characterization_media.py        (51)
Fase 1: test_bridge_native_host.py            (22)
        test_bridge_websocket_spike.py        (11)
Fase 2: test_bridge_contratos.py              (13)
Fase 3: test_bridge_saude.py                   (9)
Fase 4: sem testes automatizados — JS de extensão, sem runner.
        Conferido com `node --check` nos 3 arquivos + JSON do manifesto.
```

## Próximo passo exato
`Carregar a extensão descompactada em chrome://extensions (ver BLOQUEIO na
Fase 4). Depois: conferir data/bridge/host.log ganhando HOST_INICIADO, fechar
o gate da Fase 4 e os 4 itens do Spike A que dependiam disso, e seguir para a
Fase 5 (Generic HTML5 Observer).`

## Bugs encontrados

### Fase 5 — o bug do Batman (aberto, correção nas Fases 11/12)

Sintoma: o Perfil mostrava **`faltam 20 min`** para `Batman: Caped Crusader`,
uma série já assistida até o fim.

Rastreamento completo, com os números reais de 14/08/2026:

```text
UI            "faltam 20 min"
              calculado NO FRONTEND, em `restanteDe` (ProfileScreen.tsx)
              a partir de posicao/duracao cruas que /profile entrega

persistido    posicao  484.9      duracao  1680.0 (28 min)
              segundos 7850       (131 min assistidos)
              vistoEm  14/08 04:38

proporcao     484.9 / 1680.0 = 0,289  ->  terminado = False
restante      1680.0 - 484.9 = 1195 s = 20 min   <- o texto da tela
```

**Duas causas somadas, nenhuma delas no observador:**

1. **Identidade.** A linha é chaveada pela OBRA e carrega posição e duração de
   um EPISÓDIO. O sinal está à vista: **7850 s assistidos contra 1680 s de
   duração — 4,7 vezes**. Nenhuma reprodução de 28 minutos foi vista por 131.
   É a mistura WorkIdentity × PlaybackIdentity que a **Fase 11** desfaz.

2. **Fóssil.** `registrar` preserva a posição anterior quando a nova é `None` —
   e isso é CORRETO para o caso que originou a regra (uma leitura em que a
   janela não respondeu não pode apagar o que outra já achou). Só que com a
   SMTC pendurada, que é o estado medido desta máquina, a posição é **sempre**
   `None`. O valor de 04:38 nunca mais é atualizado nem alcança os 94% que o
   marcariam como terminado. Fica lá, plausível e errado.

**Respostas às 10 perguntas:**

| # | Pergunta | Resposta |
|---|---|---|
| 1 | `currentTime` persistido | 484.943334 |
| 2 | `duration` persistida | 1680.008 (um episódio) |
| 3 | De qual episódio | **Indeterminável** — o registro não tem campo de episódio |
| 4 | Estado de conclusão | Não existe; `terminado` é derivado de posição/duração |
| 5 | `ENDED` registrado | **Não.** O histórico não tem o conceito |
| 6 | Concluir episódio atualiza a posição | **Não**, com a SMTC pendurada |
| 7 | Concluir a série altera algo | **Não** |
| 8 | Usa progresso de episódio anterior | **Sim** — é exatamente isso |
| 9 | Mistura Work × Playback | **Sim** |
| 10 | Onde "faltam 20 min" é calculado | **No frontend**, de dados crus do backend |

**Camada responsável:** persistência/identidade. **Não** o observador, que
acabou de provar medir o player real corretamente.

**Testes:** `test_o_estado_atual_do_bug_do_batman` fixa o defeito como fato com
os números reais; `test_serie_terminada_nao_pode_exibir_progresso_de_episodio_antigo`
é `xfail(strict=True)` — quando a correção entrar, ele passa a falhar por
passar, e alguém tem de vir tirar o marcador em vez de deixá-lo apodrecendo.

Não escondi o `faltam X min` na UI: a tela só revelou a inconsistência, e
apagar o sintoma deixaria o dado errado no arquivo.

### Fase 1

3. **Nenhum bug de código.** Os dois achados são de arquitetura e estão na
   seção da Fase 1: a origem de extensão recusada pela política atual, e o
   `FAWKES_ALLOWED_ORIGINS` substituindo em vez de acrescentar — que derruba o
   celular. Ambos com teste.

4. **Três suposições minhas caíram ao escrever os testes do spike.** Registro
   porque cada uma teria virado bug na Fase 6: `TextCommandPayload` usa `query`
   e não `text`; `token` exige 16 caracteres e o esquema roda ANTES da
   autenticação (token curto dá `INVALID_PAYLOAD`, não `UNAUTHORIZED`); e
   `AuthResultMessage.success` é `Literal[True]`, então falha nunca vem como
   `AUTH_RESULT` — vem como `ERROR`, com `INVALID_TOKEN`.

### Fase 0

Dois bugs reais, ambos achados MEDINDO a máquina, não lendo o código:

1. **`audio_activity.ATIVO` estava em `2` (`Expired`) em vez de `1` (`Active`).**
   Medido ao vivo: `chrome.exe` em `State=1` com o Disney+ tocando e a função
   respondendo "não está tocando". Como é ela que decide se há reprodução quando
   a SMTC está travada, **nada que passasse pelo navegador virava histórico**.
   Sobreviveu porque os testes de áudio passavam o booleano já pronto para
   `da_janela` — a função que lê o enum não tinha teste nenhum.
   Corrigido, com 4 testes novos incluindo um que trava `Expired` como
   "não está tocando".

2. **Disney+ fora de `PLATAFORMAS_COM_OBRA_NA_JANELA`.**
   O código dizia "fica de fora por não ter sido medido (...) entra quando
   houver medição". Medido com a série tocando:
   `O Justiceiro | Disney+ - Google Chrome` ⇒ nomeia a OBRA.
   Custava caro porque o Disney+ é justamente o serviço com que a SMTC pendura.

Confirmado ao vivo depois das duas correções: `O Justiceiro | DISNEY_PLUS |
seg=240 | capa=sim` entrou no histórico.

## Decisões tomadas

- **Caracterizar sem abrir costura de teste.** A SMTC é falsificada injetando um
  `winsdk` de mentira em `sys.modules`. Zero linhas de produção alteradas — a
  Fase 0 não pode começar a refatorar o que a Fase 3 vai refatorar.
- **Um arquivo só para a caracterização**, separado dos testes de unidade. Eles
  cobrem funções puras; o que faltava era o caminho COMBINADO.
- **Regra escrita no topo do arquivo:** se um destes testes falhar durante a
  Fase 3, a resposta padrão NÃO é atualizar o teste — é descobrir qual
  heurística sumiu.
- **`trustworthy` é a `SourceCapabilities` já em produção.** A Fase 3 generaliza,
  não substitui.

## Dívidas deliberadamente adiadas

- `_leitor()` injeta `window_title_reader` por parâmetro. A ligação real com
  `WindowFocuser.media_window_title` (incluindo a escolha entre várias janelas
  abertas) não está caracterizada — depende do desktop, não de um teste.
- A composição no nível do **dispatcher** (`_read_now_playing` caindo para
  `da_janela` quando `travada`) está caracterizada em partes, não ponta a ponta.
- Disney+ como "nomeia a obra" vem de **uma** medição, de uma série. Se algum
  tipo de conteúdo nomear o episódio, aparece uma linha por episódio — o mesmo
  defeito que o Max tem. Reconferir em alguns dias.
- **BLOQUEIO DE CHECKPOINT — precisa de decisão humana.** Não existe commit
  válido possível, e a causa foi verificada:

  ```text
  audio_activity.py    untracked  (arquivo inteiro novo para o Git)
  now_playing.py       untracked
  history/store.py     untracked
  dispatcher.py        modificado  555+/12-  vs HEAD
  schemas/ws.py        modificado  121+/14-  vs HEAD
  ```

  Os testes das Fases 0 e 1 dependem desses arquivos (o characterization test
  exige `ATIVO == 1`, o Disney+ como obra, etc.). Commitar só os arquivos novos
  produziria um commit VERMELHO — os testes cairiam num checkout limpo, porque
  as correções não estariam lá. Commitar o necessário para ficar verde varreria
  ~129 arquivos de trabalho anterior não commitado, fora do escopo da fase.

  As duas saídas violam a regra dada. O loop segue sem checkpoint; a árvore de
  trabalho é o único estado válido. **Risco:** perder tudo se a árvore for
  descartada.

- Spike A: `Extension → Host`, reconnect, restart do Chrome e host morto não
  foram exercitados através do Chrome de verdade — dependem de carregar a
  extensão descompactada, que é clique humano. Movidos para a Fase 4.

## Próximo passo exato
`Fase 1 — Spike A (Native Messaging): host mínimo com framing stdio, manifesto
registrado em HKCU, key fixa para ID estável, e provar Extension → Host → IPC →
FastAPI JÁ EM EXECUÇÃO. Medir o custo de instalação. Só então o Spike B.`

---

# 25. Critério de encerramento do Master Loop

O loop termina somente quando:

- [ ] Todas as fases estão `[x]`.
- [ ] Todos os gates estão verdes.
- [ ] Nenhum critério de implementação incorreta está presente.
- [ ] Suite completa passa.
- [ ] Bugs históricos continuam protegidos.
- [ ] Netflix funciona independentemente da SMTC para metadata.
- [ ] Serviços já funcionais não regrediram.
- [ ] Browser Bridge possui fallback.
- [ ] Histórico não fragmenta episódios.
- [ ] ConsumptionPolicy não contabiliza player silencioso como consumo.
- [ ] Multiple Tabs possui decisão determinística.
- [ ] Documentação corresponde ao código real.

---

# Definição de "Pronto"

Pronto significa:

```text
implementado
+
testado
+
comportamento anterior preservado
+
casos reais validados
+
gate aprovado
+
checkbox marcado
```

Até lá, o loop continua.
