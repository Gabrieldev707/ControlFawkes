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
- [x] Fase 8 — Source Availability / Freshness
- [x] Fase 9 — Consumption Policy
- [x] Fase 10 — Netflix Adapter
- [x] Fase 11 — Identidades de mídia
- [x] Fase 12 — Histórico
- [x] Fase 13 — RelogioDaMidia
- [~] Fase 14 — Multiple Tabs  *(dataset coletado; falta 1 cenário: PiP)*
- [x] Fase 15 — MediaSessionArbiter
- [x] Fase 16 — Controles
- [x] Fase 17 — Hardening
- [~] Fase 18 — Validação final  *(4 serviços aprovados pelo usuário; falta
      revalidar o que entrou depois)*

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

> Entrega: **`app/bridge/estado.py`** (estado vivo + saúde da ponte) e
> **`app/media/fusao.py`** (o Merger entrando no caminho de produção).
> Testes: **`backend/tests/test_bridge_estado.py`** (29 testes).

## Browser Bridge — `SaudeDaPonte`
- [x] connected — `lastSeen` dentro de `SEGUNDOS_ATE_DESCONECTAR` (60s)
- [x] lastSeen — segundos desde o último evento de qualquer tipo
- [x] lastPositionUpdate — segundos desde o último evento COM posição

> Os dois últimos são separados porque divergem no caso que importa: uma aba
> pausada continua batendo (viva) sem mexer a posição (tempo velho).

## SMTC — `SaudeDaSMTC`, já entregue na Fase 3
- [x] available
- [x] responsive
- [x] lastSuccess
- [x] latency

## Window Title — `SaudeDoWindowTitle`, já entregue na Fase 3
Não possui health de conexão.
- [x] windowPresent
- [x] titlePresent
- [x] parseable

Campos dinâmicos:
- [x] currentTime
- [x] playbackState
- [x] audible

não ficam vivos indefinidamente. Prazo: `SEGUNDOS_ATE_O_TEMPO_ENVELHECER`
(25s = dois batimentos e meio da extensão). Fora do prazo, `dinamicos_frescos`
vira falso e a `Leitura` deixa de OFERECER o campo ao Merger — não é uma oferta
fraca, é oferta nenhuma.

Metadata:
- [x] workTitle
- [x] episodeTitle

pode sobreviver temporariamente — `CAMPOS_DINAMICOS` do Merger não os inclui,
então o frescor não os derruba.

## Decisões registradas

- **O relógio é o do servidor, monotônico.** Não o `timestamp` do evento: ele
  vem do relógio da aba, que a própria validação tolera estar dez minutos
  torto. Medir frescor com o relógio da fonte é deixar a fonte declarar-se
  fresca.
- **A posição é extrapolada entre batimentos.** O batimento é de 10s por
  decisão da extensão (atravessar as fronteiras é o que custa caro, não medir);
  a outra metade dessa decisão é `SessaoDaPonte.posicao_agora`.
- **O serviço tem de casar.** `plataforma_do_host` traduz `location.hostname`
  para `Platform`, e sem casamento o tempo da ponte NÃO é aplicado. Uma aba da
  Netflix atrás não pode carimbar a linha do tempo do Prime Video da frente.
- **Só os campos dinâmicos passam pelo Merger, por enquanto.** É onde há dois
  candidatos. `workTitle` tem uma fonte só até a Fase 10 existir; passá-lo pelo
  Merger devolveria o mesmo valor com mais cerimônia.
- **O desempate entre abas é mínimo e não é o árbitro.** Quem toca vence quem
  está parado; entre duas que tocam, a que falou por último. O árbitro é a
  Fase 15 e precisa de audível, foco e aba ativa, que a ponte não manda.

## Gate
- [x] Fonte morta não fornece estado dinâmico. — `test_fonte_morta_nao_fornece_estado_dinamico`
- [x] Window Title recente não vira automaticamente confiável. — `test_window_title_recente_nao_vira_confiavel`
- [x] Capability != freshness. — `test_capacidade_nao_e_frescor`
- [x] **FASE 8 CONCLUÍDA**

---

# 12. Fase 9 — Consumption Policy

> Entrega: **`app/bridge/consumo.py`** — o arquivo que `contratos.py` já
> anunciava na Fase 2. Testes: **`backend/tests/test_bridge_consumo.py`**
> (16 testes).

Não confundir player rodando com usuário assistindo.

Inputs:
- [x] playbackState — o estado técnico do player
- [x] audible — Core Audio, via `processo_esta_tocando`
- [x] muted — o `<video>` da página, pela ponte
- [x] Core Audio — sondada com folga de 5s; ver `SEGUNDOS_ENTRE_SONDAS_DE_AUDIO`
- [x] demais evidências atuais do projeto — `PLATAFORMAS_FORA_DO_HISTORICO`,
      `_titulo_generico` e `trustworthy` continuam valendo antes desta política

Regra:
- [x] Histórico nunca soma tempo apenas porque `video.paused === false`.

Regression:
- [x] Caso equivalente ao bug Batman. — `test_o_bug_do_batman_esta_bloqueado`
- [x] Player technically playing.
- [x] Sem atividade real de áudio.
- [x] Tempo não aumenta.

## Decisões registradas

- **Três estados, não dois.** ASSISTINDO / NAO_ASSISTINDO / INDETERMINADO.
  NAO_ASSISTINDO é evidência CONTRÁRIA, não ausência de evidência — e a
  diferença é o que impede a fase de causar a regressão oposta.
- **INDETERMINADO conta.** Fora do Windows, sem `pycaw`, ou com a Core Audio
  recusando, exigir prova de consumo pararia o histórico para todo mundo. Já
  aconteceu: a sonda respondendo `False` para quem assistia apagou uma série
  inteira do Disney+.
- **`muted` não nega sozinho.** Legenda com som desligado é forma legítima de
  assistir. Ele só desempata quando o áudio não confirma nada.
- **A posição é guardada mesmo num intervalo que não conta.** Onde a pessoa
  parou continua verdade; o que não avança é o tempo assistido.
- **O padrão de `observar` é INDETERMINADO.** Quem decide negar diz isso em voz
  alta; um padrão restritivo silenciaria todo chamador antigo sem aviso.

## Gate
- [x] UI usa estado técnico correto. — a tela segue em `atual.playing`
- [x] Histórico usa política mais forte. — `test_a_tela_usa_o_estado_tecnico_e_o_historico_a_politica`
- [x] Bug histórico bloqueado.
- [x] **FASE 9 CONCLUÍDA**

---

# 13. Fase 10 — Netflix Adapter

Arquivo: **`src/content/providers/netflix.js`** — `.js` e não `.ts`.

> Desvio deliberado do nome no plano. Content script declarado no manifesto NÃO
> é módulo, e não há bundler: `index.js` registra que "a decisão de introduzir
> um bundler segue adiada". Um `.ts` ali não carrega. O teste é `.ts` e avalia o
> `.js` real com `new Function`, exatamente como `video-observer.test.ts` já
> fazia — o teste exercita o arquivo que o Chrome carrega, não uma cópia.

Testes: **`providers/netflix.test.ts`** (26) e
**`backend/tests/test_bridge_netflix.py`** (18).

Responsabilidade:
- [x] workTitle
- [x] episodeTitle
- [x] seasonNumber
- [x] episodeNumber
- [x] mudanças de metadata — `vigiaDaMetadata` em `index.js`, com `MEDIA_CHANGED`

Não implementar nele:
- [x] relógio
- [x] currentTime
- [x] duration
- [x] play/pause
- [x] lifecycle genérico do vídeo

> Nenhum deles aparece no arquivo. Quem os responde é `video-observer.js`, que
> já funciona nos seis serviços; duplicar aqui criaria uma segunda verdade sobre
> o tempo.

Testes:
- [x] Filme. — sem episódio inventado
- [x] Série. — obra, temporada, episódio, nome
- [x] Episódio.
- [x] Próximo episódio. — `mesmaMetadata` falso, `workTitle` igual
- [x] Seek. — não passa pelo adapter; coberto em `test_bridge_estado.py`
- [x] Pause. — idem
- [x] Reload. — leitura é sem estado; o piso da URL responde sozinho
- [x] Autoplay. — o vigia pega a troca sem o `<video>` trocar

## Decisões registradas

- **Cascata, não seletor único.** O DOM da Netflix não é contrato nosso. Cada
  estratégia falha para `null` sem derrubar as outras: barra do player
  (`data-uia="video-title"`, o atributo que a automação da própria Netflix usa)
  → título da aba → id da URL.
- **O id da URL é o piso.** `/watch/81234567` não é um nome, mas é identidade
  de reprodução estável e não depende de DOM nenhum. Enquanto houver id, a
  Fase 11 tem com o que distinguir episódio retomado de episódio seguinte.
- **Não inventar.** A forma "Obra: Season N: Episódio" traz a temporada e NÃO
  traz o número do episódio; `episodeNumber` fica `null`. Um "E1" chutado é pior
  do que número nenhum, porque a pessoa acredita nele.
- **Um adapter só.** "Não criar adapters sem necessidade comprovada" é regra
  permanente. Prime Video, Disney+, Max e YouTube nomeiam a obra na janela —
  escrever adapters para eles agora seria criar quatro sem defeito que os
  justifique.
- **O episódio vai formatado como "T2 E1 · Nome".** Não é decoração:
  `como_temporada_e_episodio` lê exatamente "T2 E1" para a tela de perfil.

## Gate
- [x] Netflix fornece metadata sem depender da SMTC para nome da obra.
      — `test_a_netflix_ganha_nome_sem_a_smtc`, com as duas fontes do Windows
      dizendo "Netflix" e a página dizendo "Sherlock"
- [x] **FASE 10 CONCLUÍDA**

> **Pendência de validação física.** Os seletores do DOM foram escritos em
> cascata e testados contra DOM sintético; eles NÃO foram medidos numa sessão
> real da Netflix. A Fase 18 tem de confirmar `data-uia="video-title"` na
> máquina do usuário. Se ele tiver mudado, o piso da URL sustenta a identidade e
> só o NOME se perde — que é o modo de falha desejado, não o inverso.

---

# 14. Fase 11 — Identidades

> Entrega: `identidade_da_reproducao` e `IdentidadeDaObra.chave` em
> **`app/media/identidade.py`**. Testes: **`tests/test_identidades_fase11.py`**.

## PlaybackIdentity
Responde: é a mesma reprodução específica?

Do sinal mais forte para o mais fraco — e a ORDEM é a decisão desta fase:
- [x] `pageId` — "/watch/81234567", a própria Netflix dizendo qual é
- [x] `seasonNumber` + `episodeNumber` — "s1e4"
- [x] nome do episódio + duração — o que já existia, para os serviços sem adapter
- [x] provider — via a obra, que já carrega a plataforma

> Misturar os sinais numa chave só faria a MESMA reprodução gerar chaves
> diferentes conforme o que a leitura conseguiu ler naquele segundo. Duas chaves
> para a mesma reprodução é o que faz o histórico achar que trocou de episódio e
> recalibrar a posição sem motivo.

## WorkIdentity
Responde: é a mesma obra no histórico?

Baseline:
- [x] provider
- [x] workTitle

> E NADA de temporada ou episódio. É essa ausência que impede a fragmentação.

Teste:
```text
Rick and Morty
S01E01 → S01E02 → S01E03
```

Esperado:
- [x] PlaybackIdentity muda. — `s1e1` → `s1e2` → `s1e3`
- [x] EPISODE_CHANGED.
- [x] WorkIdentity permanece. — `NETFLIX::rick and morty`
- [x] Uma obra no histórico. — `test_a_maratona_vira_UMA_obra_no_historico`

- [x] **FASE 11 CONCLUÍDA**

---

# 15. Fase 12 — Histórico

EPISODE_CHANGED deve:
- [x] atualizar episódio.
- [x] resetar/recalibrar posição. — e o `concluida` do episódio anterior não
      atravessa para o seguinte
- [x] atualizar metadata.
- [x] manter mesma obra.

Não fazer:
```text
EPISODE_CHANGED → nova linha automaticamente
```
- [x] A chave do arquivo continua sendo a da OBRA. Trocar de reprodução fecha a
      conta do trecho e abre outra DENTRO da mesma linha.

Testes:
- [x] mesma série / próximo episódio.
- [x] mesmo episódio retomado. — mesmo `pageId`, a posição avança
- [x] filme diferente.
- [x] série diferente.
- [x] seek grande. — mesma reprodução, posição nova; coberto em `test_bridge_estado`
- [x] pause longo. — o consumo da Fase 9 barra; a posição fica
- [x] navegador fechado.
- [x] extensão reconectada. — `test_a_extensao_caindo_no_meio_nao_fragmenta`

## Decisões registradas

- **"concluída" pertence à REPRODUÇÃO, não à obra.** Terminar um episódio não
  marca a série — ela sairia de "continuar assistindo" no momento em que a
  pessoa mais quer o próximo.
- **O `ended` do `<video>` é a única evidência DIRETA de fim.** A SMTC publica
  "pausado", que é o que um filme no meio também é. Era por isso que filme
  terminado nunca saía da lista: a razão posição/duração quase nunca chega a
  0,94, porque no fim o player pula para a tela seguinte.
- **Posição de série volta rotulada, em vez de sumir.** `posicaoDoEpisodio` e
  `duracaoDoEpisodio` respondem "onde parei"; `posicao`/`duracao` continuam
  fora da obra multi-reprodução, que é o conserto do Batman.

## Gate
- [x] Sem fragmentação por episódio.
- [x] Sem pôster errado por colisão simples de título. — o nome do episódio
      nunca vira `workTitle`: o adapter os separa, e `trustworthy` barra o resto
- [x] Histórico anterior continua funcionando. —
      `test_o_historico_anterior_continua_funcionando`
- [x] **FASE 12 CONCLUÍDA**

---

# 16. Fase 13 — RelogioDaMidia

> Entrega: o ramo `parada_da_ponte` em **`app/media/fusao.py`**.
> Testes: **`tests/test_relogio_fase13.py`** (9 testes).

Quando Browser currentTime estiver saudável:
- [x] usar posição medida.
- [x] não estimar desnecessariamente.

Quando Browser Bridge cair:
```text
currentTime unavailable
→ avaliar outras fontes
→ RelogioDaMidia fallback
```
- [x] A ordem é literal: a SMTC saudável assume PRIMEIRO (Prime Video, Disney+,
      Max). Só quando ninguém assume — que é o estado normal da Netflix, onde a
      SMTC nunca teve posição — o último valor medido pela ponte segura a barra.

Testes:
- [x] posição real.
- [x] extensão cai.
- [x] fallback assume.
- [x] extensão volta.
- [x] posição recalibra.
- [x] sem saltos absurdos.

## Decisões registradas

- **O valor guardado NÃO é projetado.** Projetar seria a dupla estimativa que o
  gate proíbe, e faria a barra passar do fim do filme sem nada ter acontecido.
  Ele volta marcado `position_stale`, e quem desenha não o faz avançar.
- **Não há estado SUSPEITA para a ponte.** A sessão é identificada por
  `sessionId` e some quando a reprodução acaba, então o número velho é sempre
  desta reprodução — diferente da SMTC do Chrome, que agrega abas e publica a
  linha do tempo da mídia anterior.
- **A rede só vale para quem a ponte já mediu.** Sem extensão instalada, a
  Netflix continua sem posição: dizer um número ali seria inventá-lo.

## Gate
- [x] Nenhum buraco de posição. — `test_a_extensao_caindo_nao_apaga_a_posicao`
- [x] Nenhuma dupla estimativa. — `test_entre_batimentos_projeta_uma_vez_so`
- [x] Fonte real saudável sempre vence. —
      `test_a_smtc_saudavel_assume_quando_a_ponte_envelhece`
- [x] **FASE 13 CONCLUÍDA**

---

# 17. Fase 14 — Multiple Tabs: telemetria

> Entrega: **`app/bridge/telemetria.py`** (coletor + `caso_de` + `resumir`) e
> **`scripts/ver_abas.py`**. Testes: **`tests/test_bridge_telemetria.py`** (16).
> Dataset: `data/bridge/abas.jsonl`, JSONL.

Registrar por sessão:
- [x] tabId — do `sender`, no service worker
- [x] windowId — idem
- [x] active — idem
- [x] audible — idem, e é o campo que mais vale: o Chrome sabe por ABA,
      enquanto a Core Audio só sabe por PROCESSO e o Chrome é um processo só
- [x] muted — o do `<video>` e o `tabMuted` da aba, separados: são dois botões
- [x] playbackState
- [x] lastPlay — como `msDesdeUltimoPlay`
- [x] lastMediaEvent — como `msDesdeUltimoEvento`
- [x] lastInteraction quando disponível — `visible` e `windowFocused` são o que
      o Chrome de fato oferece; um "última interação" real exigiria escutar
      teclado e mouse da página, que é coleta que este projeto não faz
- [x] pictureInPicture
- [x] provider

> Os intervalos vão em MILISSEGUNDOS DESDE, e não como carimbo absoluto: o
> relógio da aba pode estar torto e o backend não tem como corrigir um carimbo
> que não é dele. Um intervalo continua utilizável.
>
> E a telemetria NÃO é herdada do evento anterior, ao contrário da duração e do
> nome da obra. "A aba estava ativa há um minuto" não responde "a aba está
> ativa?", e herdar produziria o dado plausível-e-errado que a Fase 8 recusa.

Cenários — o coletor os NOMEIA (`caso_de`), e a coleta depende de uso real:
- [ ] Netflix + YouTube. → `servicos-diferentes` / `duas-tocando`
- [ ] Netflix + Netflix. → `mesmo-servico`
- [ ] Netflix + Spotify Web. → `servicos-diferentes`
- [ ] Netflix pausado + YouTube playing. → `background-tocando`
- [ ] aba ativa pausada + background audible. → `ativa-pausada-outra-tocando`
- [ ] PiP. → `pip`
- [ ] janela não focada. → `windowFocused: false` na linha
- [ ] várias janelas Chrome. → `varias-janelas`

## Gate
- [x] Casos ambíguos identificados. — os oito têm nome, e a linha diz qual é
- [x] Nenhuma política congelada antes dos dados. — `ColetorDeAbas` não tem
      método que devolva "a sessão ativa", e não pode ganhar um
- [x] **Dataset real coletado.** — 1542 observações, 1526 com telemetria de
      aba, cinco serviços, entre 25 e 26/08/2026. Sete dos oito cenários têm
      dado.
- [ ] **PiP: zero observações em 1526.** ← o que falta. Dez segundos de uso;
      ver `docs/VALIDACAO_FISICA.md`, seção 9.
- [ ] **FASE 14 CONCLUÍDA**

### A leitura do dataset, em 26/08/2026 — e o que ela desmentiu

A primeira coisa que os dados fizeram foi desmentir a leitura crua deles.

    instantes com sessões repetidas na mesma aba   1078 de 1526
    maior número de sessões numa única aba         8

Eram sessões fantasma da MESMA aba. Contando sessões havia 477 instantes com
"duas tocando"; contando ABAS há **18**. Vinte e seis vezes menos. O árbitro
teria sido escrito para um conflito que quase não acontece.

A causa foi corrigida (`EstadoDaPonte._esquecer_a_mesma_aba`: uma aba carrega
um content script e um `sessionId` por vez, então um id novo da mesma aba
encerra o anterior), e o classificador passou a contar abas
(`telemetria.uma_por_aba`) em vez de confiar na invariante do outro módulo.

O que cada sinal respondeu, nos 18 instantes reais:

    ACTIVE    aponta exatamente uma em 12; VÁRIAS em 6; nunca nenhuma
    AUDIBLE   aponta exatamente uma em  4; NENHUMA em 14

E o achado que definiu a ordem da Fase 15:

    aba ATIVA, tocando, com `audible === False`:  187 de 276  (68%)

Dois terços das vezes a aba que a pessoa está olhando declara não ser audível.
É a terceira aparição do mesmo defeito — `consumo.py` e `audio_activity.py` são
as outras duas —, e agora ele tem número.

    windowFocused   presente em 29% das abas
    visible         diverge de `active` em 416 observações

> **Por que o loop para aqui.** A regra de autonomia manda avançar com gate
> verde e interromper diante de bloqueio real. Este é um: o gate desta fase
> exige dados que só o uso produz, e o gate dela proíbe, com todas as letras,
> congelar a política da Fase 15 antes deles. Escrever o árbitro agora — "quem
> toca, é audível e está na aba ativa vence" — seria inventar a regra e depois
> procurar dados que a confirmem. É como nasceu o `confidence: 0.98` que
> `contratos.py` existe para não repetir.

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

> Entrega: **`app/bridge/arbitro.py`** (`escolher` + `por_que`). Testes:
> **`tests/test_arbitro.py`** (24). Integrado em `EstadoDaPonte.atual`.

- [x] Política explícita. — a docstring do módulo cita o número que produziu
      cada critério.
- [x] Ordem definida. — LEXICOGRÁFICA, dez critérios. Uma pontuação somada
      deixaria três sinais fracos derrubarem um forte, e ninguém saberia dizer
      por quê depois.
- [x] Empates definidos. — `visto_em`, depois `sessionId`.
- [x] Sem race condition. — função PURA: recebe a lista, devolve um elemento.
      Sem estado, sem relógio próprio, sem efeito.

A ordem, e a evidência de cada posição:

    1. identificada       sabe dizer O QUE reproduz (obra ou pageId)
    2. tocando            881 instantes têm exatamente uma tocando
    3. audível            PROMOVE; nunca rebaixa (187 de 276)
    4. aba ativa          isola uma em 12 de 18
    5. janela em foco     desempata as 6 com VÁRIAS ativas; só 29% a declaram
    6. visível            diverge de `active` em 416 observações
    7. play mais recente  separou 24 de 24 quando presente
    8. sabe a obra / a página   qualidade da leitura, não atenção
    9. visto por último   determinismo
   10. sessionId          desempate final absoluto

> **O critério 1 quase não existiu.** A primeira versão punha "tocando" no topo
> e ressuscitou um bug medido em 25/08/2026: a vitrine da home da Netflix toca
> um trailer de quarenta segundos sozinha, e por "quem toca vence" ela ganhava
> do Fight Club que a pessoa tinha pausado para ir olhar o catálogo. Uma
> reprodução que ninguém consegue nomear não é o que a pessoa está assistindo.
>
> LIMITE CONHECIDO: o YouTube não tem adapter, então é sempre "não
> identificado" e perde para um filme PAUSADO de outro serviço. É o
> comportamento de hoje, não uma regressão desta fase, e o conserto é um
> adapter — não um remendo no árbitro.

## Gate
- [x] Cenários da Fase 14 possuem resultado esperado. — cada critério tem teste
      preso ao número que o produziu.
- [x] Troca entre abas previsível. — testes de determinismo, e `por_que()`
      responde QUAL critério decidiu.
- [x] Histórico não soma duas sessões indevidamente. — trocar de aba fecha a
      conta anterior; duas obras, dois tempos, duas linhas.
- [x] **FASE 15 CONCLUÍDA**

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

> Entrega: **`app/bridge/comandos.py`** (fila + espera longa), duas rotas em
> `app/api/bridge.py`, `laco_de_comandos` em `native_host.py`,
> `entregarComando` no service worker, `executarComando` no content script.
> Testes: **`tests/test_comandos.py`** (34) e os de rota em
> `tests/test_bridge_endpoint.py`.

## O caminho, e por que ele é invertido

Native Messaging é o Chrome quem inicia: ele SPAWNA o host e fala por stdio.
Ninguém de fora abre uma conexão com o host — e essa é exatamente a propriedade
que fez a Fase 1 preferi-lo a um WebSocket em localhost, que qualquer página
aberta alcança. Manter a propriedade custa **inverter a pergunta**:

```text
host  ──GET /bridge/comandos (a rota SEGURA até 25s)──►  ControlFawkes
host  ◄──────────────── o comando ────────────────────
host  ──stdout──►  service worker  ──►  aba  ──►  <video>
host  ──POST /bridge/comandos/{id}/resultado──────────►  ControlFawkes
```

A espera longa existe para o comando sair no instante em que a pessoa aperta o
botão. Uma consulta por segundo daria até um segundo de atraso e gastaria uma
requisição por segundo para dizer "nada".

Implementar:
- [x] PLAY
- [x] PAUSE
- [x] SEEK_TO
- [x] SEEK_BY

Ligados aos botões que já existiam: `MEDIA_PLAY_PAUSE` vira PLAY **ou** PAUSE
conforme o estado que a própria página reportou, e `MEDIA_SEEK_BACK` /
`MEDIA_SEEK_FORWARD` viram `SEEK_BY` de ∓10s.

> **O que isso conserta, além de ser mais direto.** O caminho antigo é uma
> tecla: focar a janela e apertar a barra de espaço. Três limites, dois
> medidos:
>
>     rouba o foco    a janela do Chrome pula para a frente.
>     erra de aba     a barra de espaço vai para a aba ATIVA. Medido na Fase
>                     14: em 6 dos 18 instantes com duas abas tocando havia
>                     MAIS DE UMA aba ativa.
>     toggle cego     `MEDIA_PLAY_PAUSE` alterna o que estiver lá — a queixa
>                     "pausa e não volta a play".
>
> E a tecla continua existindo como plano B. `None` do comando significa "por
> aqui não deu", e quem chama cai para ela. Quem não instalou a extensão não
> perdeu nada.

Depois, só se necessário:
- [ ] next episode
- [ ] previous
- [x] fullscreen — já existe, por duplo clique. Não passa pelo elemento porque
      `requestFullscreen` exige gesto do usuário na página.
- [ ] PiP

## Gate
- [x] Comando chega à sessão correta. — o comando carrega `tabId` (do árbitro)
      E `sessionId`; a página confere o segundo antes de executar, para não
      pausar o episódio seguinte porque o anterior foi pedido.
- [x] Múltiplas abas não recebem comando indevido. — o worker endereça a aba
      nomeada e nunca "a ativa"; sem `tabId`, não enfileira.
- [x] Estado retorna corretamente. — resultado com motivo, sempre. Recusa e
      silêncio caem para a tecla.
- [x] **FASE 16 CONCLUÍDA**

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

> Entrega: **`tests/test_hardening.py`** (28), mais o descarte de mensagem fora
> de ordem em `EstadoDaPonte.registrar` e o campo `seq` em `eventos.py`.

### O achado desta fase

`seq` **já era enviado** pelo content script desde a Fase 5 (`seq: sequencia++`
em `index.js`) e o backend o ignorava por completo: o campo existia e não era
lido por ninguém.

Sem ele, uma mensagem atrasada sobrescreve uma recente e a posição anda PARA
TRÁS sem nada ter acontecido na tela — a mesma família do `currentTime`
congelado que a Fase 0 documentou. Agora o que vem com sequência MENOR é
descartado; igual passa, porque igual é reenvio e não desordem.

E a mensagem atrasada continua contando como VIDA da sessão: a aba falou, ainda
que atrasado. Descartá-la inteira faria a sessão sumir por causa de uma
reordenação de rede.

## Gate
- [x] Nenhum crash. — entrada hostil (nulo, lista, texto, payload nulo,
      timestamp textual, `textContent` de 5000 caracteres) vira Recusa com
      motivo, nunca exceção.
- [x] Nenhum stale currentTime tratado como vivo. — `dinamicos_frescos` cai aos
      150s, a sessão some aos 300s, pausado não extrapola, e sequência menor é
      descartada.
- [x] Nenhuma sessão fantasma persistente. — `SESSION_ENDED` some na hora;
      oito sessões na mesma aba viram uma; navegador fechado esvazia pelo prazo.
- [x] Fallback funciona. — sem ponte, a leitura do Windows atravessa intacta;
      com a ponte caída, a SMTC reassume; sem os dois, não há cartão.
- [x] **FASE 17 CONCLUÍDA**

> **Anotado e não perseguido:** um teste de `test_catalog_api.py` deu erro de
> teardown UMA vez numa rodada completa e passou nas seguintes, isolado e em
> conjunto. Cheira a corrida de diretório temporário no Windows, não a defeito
> de produção. Fica registrado aqui em vez de esquecido.

---

# 21. Fase 18 — Validação final

> Roteiro marcável: **`docs/VALIDACAO_FISICA.md`**.
>
> Nada aqui é código. A suíte tem 1.196 testes de backend e 399 de frontend, e
> eles provam a LÓGICA com adaptadores falsos — nenhum deles prova que o dedo no
> celular move o mouse desta máquina. É essa a distância que esta fase cobre, e
> ela só fecha com alguém usando.

Netflix deve fornecer quando disponível:
- [x] provider
- [x] workTitle
- [x] episodeTitle
- [x] seasonNumber
- [x] episodeNumber
- [x] playbackState
- [x] audible
- [x] currentTime
- [x] duration
- [x] playbackRate

> Confirmado pelo usuário em 26/08/2026, com a linha real no `historico.json`:
> `Breaking Bad | NETFLIX | ep='E1 · Pilot' | pos=3168.8/3500.1`.

Outros — e "continua funcionando" ficou pequeno: três deles GANHARAM adapter
nesta data, e cada um por um defeito diferente e medido.

- [x] **Max** — o único cujo título de janela MENTE. Medido:
      `document.title = "⁨Trust Fall⁩ • HBO Max"` enquanto a série é
      "Lanternas" — "Trust Fall" é o nome do episódio. Adapter lê
      `player-ux-asset-title` / `player-ux-season-episode` /
      `player-ux-asset-subtitle`. O `<video>` é honesto (`dur 3437.22`).
- [x] **Disney+** — Shadow DOM (76 raízes) e `<video>` cego para o próprio
      conteúdo: `duration: Infinity`, `seekable [0, 62]` num episódio de
      cinquenta minutos. `currentTime` marcava 50.8 quando a posição real era
      146. A posição do Disney+ **nunca esteve certa** — não por regressão, mas
      porque a única fonte que existia era a errada. Adapter lê o `title-bug` e
      o slider, com ÂNCORA: o par (posição real, `currentTime` daquele
      instante), projetado enquanto o overlay estiver fora do DOM.
- [x] **Prime Video** — `<video>` honesto (`dur 1329.184`, os 22 min que a
      página declara). Faltava só o episódio, e ele estava em
      `atvwebplayersdk-episode-info`. Três armadilhas na página de detalhe: o
      botão "Resume S3 E7" (VISÍVEL enquanto o do player estava escondido), o
      seletor de temporadas, e mais de um `player-container`.
- [x] **YouTube** — controla e aparece no cartão; segue fora do histórico.
- [x] **Spotify Desktop** — segue por SMTC, sem adapter e sem comando pela
      ponte: é aplicativo, não página.

> **`navigator.mediaSession`**, medido nos três: vazio no Disney+ e no Prime
> (`playbackState: "none"`), preenchido só no Max (`title: "Lanternas"`). Fecha
> a porta de esperar que os serviços declarem metadata ao navegador.

Falha da SMTC:
- [ ] Browser Bridge continua funcional.
- [ ] Metadata continua.
- [ ] Posição continua.

Falha da extensão:
- [ ] Fonte invalidada.
- [ ] currentTime não fica stale.
- [ ] fallback entra quando possível.

### O que falta para o gate fechar

O roteiro de `docs/VALIDACAO_FISICA.md` foi cumprido para os quatro serviços em
26/08/2026 — e as Fases 15, 16 e 17 entraram DEPOIS desses "aprovado". Elas
mexem em três coisas que a validação anterior não cobre:

- quem decide qual aba responde (Fase 15)
- COMO o play/pause chega à página (Fase 16)
- o descarte de mensagem fora de ordem (Fase 17)

Então falta uma passada nas seções 1, 8 e 9 do roteiro. A seção 9 é a mais
curta e a mais importante: **dez segundos com uma aba em Picture-in-Picture**
fecham também o último cenário da Fase 14.

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
