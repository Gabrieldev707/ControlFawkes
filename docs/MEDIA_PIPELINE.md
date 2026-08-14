# Pipeline de mídia do ControlFawkes — estado atual

> Fase 0 do Master Loop do Browser Media Bridge.
> Descreve o que EXISTE hoje, não o que se deseja. É a base contra a qual a
> Fase 3 (separar SMTC e Window Title) será medida.

---

## 1. O fluxo, ponta a ponta

```text
                    laço, 1×/s  (NOW_PLAYING_INTERVAL_SECONDS)
                              │
                    Dispatcher._watch_now_playing
                              │
                    Dispatcher._read_now_playing
                              │
                    ┌─────────┴─────────┐
                    │                   │
              LeituraEmVoo         (se travada)
                    │                   │
        WindowsNowPlayingReader     da_janela
                    │                   │
        ┌───────────┴───────┐           │
        │                   │           │
      SMTC            Window Title   Window Title
   (winsdk)          (WindowFocuser) + audio_activity
        │                   │           │
        └───────────┬───────┘           │
                    ▼                   ▼
                        NowPlaying
                              │
              ┌───────────────┼───────────────┐
              │               │               │
       HistoryRecorder   _poster_para    NowPlayingMessage
              │           (catálogo)           │
        HistoryStore                     WebSocket → celular
              │
        historico.json
```

Ponto crítico: **não existem "duas fontes" separáveis hoje.** A janela é lida
*dentro* de `_read_windows()`, e o título resolvido volta a alimentar a decisão
sobre a linha do tempo da SMTC. É um único bloco entrelaçado.

---

## 2. Entrada principal da SMTC

`app/media/now_playing.py` → `WindowsNowPlayingReader._read_windows()`

Ordem exata das decisões:

1. `Manager.request_async()` → `get_current_session()`. `None` ⇒ nada tocando.
2. `app = sessao.source_app_user_model_id`
3. `status` — só `PLAYING (4)` e `PAUSED (5)` viram sessão. Qualquer outro ⇒ `None`.
4. `props.title` / `props.artist`
5. **Plataforma**, nesta ordem: `_plataforma_do_app(app)` → `plataforma_no_titulo(props.title)` → (mais tarde) `plataforma_no_titulo(titulo_da_janela)`
6. **Janela lida uma vez só**, já sabendo a plataforma — é isso que permite pedir a janela certa quando há vários serviços abertos
7. Se a SMTC é genérica ⇒ o título vem da janela
8. **Linha do tempo**, julgada com o título JÁ RESOLVIDO
9. Limpeza de título aplicada também ao que veio da SMTC
10. Episódio, só quando a SMTC nomeou alguma coisa

### Timeout

`LeituraEmVoo` — `SEGUNDOS_ATE_DESISTIR = 5.0`, `SEGUNDOS_ENTRE_TENTATIVAS = 20.0`.

A chamada **nunca é cancelada**: cancelar uma operação WinRT no meio a deixa
tentando concluir numa future morta, e isso matava o laço inteiro
(`InvalidStateError`). Ela é abandonada, não interrompida.

`travada` ⇒ o dispatcher cai para `da_janela`.

> Medido nesta sessão: `request_async()` sem retorno por mais de 8s com o
> Disney+ tocando. O travamento é real e frequente.

---

## 3. Leitura do título da janela

`app/windows/focus.py` → `WindowFocuser.media_window()` / `media_window_title()`

- `list_windows()` enumera janelas visíveis com título e o processo dono.
- `platform_of()` — Spotify pelo **processo**; o resto por **padrão no título**
  (`PLATFORM_TITLE_PATTERNS`), com espaço opcional para casar domínio cru
  (`play.hbomax.com`) enquanto a página carrega ou ninguém está logado.
- Entre candidatas, **a que nomeia alguma coisa vence a que mostra a home**
  (`_pagina_do_servico`).

> Medido com três abas abertas — Max no Chrome, Netflix no Edge, Netflix no
> Chrome: "a primeira que aparecer" devolvia a home da Netflix e o cartão ficava
> mudo enquanto o Max tocava ao lado.

`focus.py` importa `now_playing` **dentro da função**, de propósito, para não
inverter a direção da dependência.

---

## 4. `PLATAFORMAS_COM_OBRA_NA_JANELA` — a tabela de capabilities que já existe

Esta é a `SourceCapabilities` da V1.1, em produção, hoje:

| Serviço | O que a janela nomeia | Conta como obra |
|---|---|---|
| Prime Video | `Prime Video: Batman: Caped Crusader` — a obra | sim |
| YouTube | o vídeo, que é a obra | sim |
| Disney+ | `O Justiceiro \| Disney+` — a obra | sim |
| Max | `46 Long • HBO Max` — o **episódio** | não |
| Netflix | `Netflix - Home - Netflix` — **nada, nunca** | não |

Expressa como o booleano `NowPlaying.trustworthy`. Na Fase 3 vira capability
por campo; hoje é um único bit.

---

## 5. Regras atuais de confiança

| Regra | Onde | Bug que a originou |
|---|---|---|
| `_titulo_generico` | `now_playing.py` | linha "Netflix" de 120s virava o serviço mais usado do perfil |
| `_PAGINAS_INICIAIS` | idem | "Home", "Shows", "Movies" entravam como filmes assistidos |
| `_PARECE_ENDERECO` | idem | `play.hbomax.com` entrava como obra e ia buscar capa |
| `_sem_marca_de_travado` | idem | `(Não está respondendo)` virava parte do título |
| `_sem_invisiveis` | idem | Max envolve o episódio em U+2068/U+2069 |
| `trustworthy` | idem | Rick and Morty virou 4 títulos com nome de episódio |
| `PLATAFORMAS_FORA_DO_HISTORICO` | `recorder.py` | música inflava horas e disputava "mais usado" |
| `PLATAFORMAS_COM_CATALOGO` | `tmdb.py` | vlog do YouTube recebia pôster de filme |
| `_fala_do_mesmo_item` | `tmdb.py` | "Prime Video: Batman" virou um evento de boxe |

---

## 6. Timeline da SMTC e `RelogioDaMidia`

Três estados (`EstadoDaLinha`):

```text
VIVA      posição anda, ou parou há < 12s  → projeta
PARADA    travada, MESMO título            → devolve o número, sem projetar
SUSPEITA  travada, título MUDOU            → devolve None
```

`SEGUNDOS_ATE_DESCONFIAR = 12.0` — a posição bruta do Chrome dá saltos a cada
poucos segundos e fica parada entre eles; um limite curto confundiria o
intervalo normal com congelamento.

**O título é o que separa PARADA de SUSPEITA**, e é o título *resolvido* — no
navegador o cru é sempre o nome do site, que não muda quando o conteúdo muda.

`posicao_extrapolada` devolve `None` quando a projeção estoura a duração: uma
barra errada é pior do que barra nenhuma.

---

## 7. `audio_activity.py`

Responde "está saindo som deste processo agora?" pela Core Audio.

```text
AudioSessionState: Inactive=0, Active=1, Expired=2
```

Devolve `True` / `False` / `None`. `None` é "não sei" e preserva o palpite
otimista — um controle que diz "pausado" para quem está assistindo é pior do
que um que conta tempo demais.

**Limitação herdada:** o Chrome agrupa o áudio de todas as abas numa sessão só.
Mede-se o processo, não a aba. A extensão resolve isso com `tab.audible`.

> Bug corrigido nesta sessão: a constante estava em `2` (`Expired`). Com a SMTC
> travada é esta função que decide se há reprodução, então **tudo que passava
> pelo navegador era contado como pausado**.

---

## 8. Decisão de mídia ativa

Existem **duas** decisões distintas, e elas não conversam:

- `WindowsMediaSessionDetector.detect()` (`media/session.py`) — para onde
  mandar comandos. Áudio → título em foco → qualquer janela aberta.
- `WindowFocuser.media_window()` — de onde ler o nome. Prefere a janela que
  nomeia algo.

É o embrião do `MediaSessionArbiter`. Hoje não há conceito de "sessão por aba":
o Chrome é um processo só.

---

## 9. Histórico

`HistoryStore` — `data/historico.json`, chave `PLATAFORMA::titulo normalizado`.

- `SEGUNDOS_PARA_CONTAR = 90` — piso para entrar
- `SEGUNDOS_ENTRE_GRAVACOES = 120` — intervalo entre escritas no meio da sessão
- `MAXIMO_DE_ITENS = 120`
- `terminado` = posição/duração ≥ 0,94

**A chave é a OBRA, nunca o episódio.** É a `WorkIdentity` da Fase 11, já
existindo. `_mesma_obra` funde a linha sem serviço com a linha com serviço.

`listar()` filtra na leitura (título genérico, capa de serviço sem catálogo);
`podar_capas()` persiste essa mesma régua no arquivo.

---

## 10. Catálogo

`TmdbCatalog` — chave em `data/tmdb.json` ou `CONTROLFAWKES_TMDB_KEY`.
Opcional: sem chave, tudo funciona como antes.

Pôster só quando: há título, não é genérico, `trustworthy`, e a plataforma está
em `PLATAFORMAS_COM_CATALOGO`.

---

## 11. Segurança

- `security/origins.py` — origem local (localhost, IP privado, `.local`). Ausência
  de Origin é **aceita** de propósito: recusá-la não impediria um cliente nativo
  e quebraria clientes legítimos.
- `security/pairing.py` — PIN com bloqueio progressivo; token por dispositivo em
  `data/paired_devices.json`; comparação com `hmac_safe_equal`.
- `security/instancia_unica.py` — bloqueio exclusivo de arquivo. No Windows dois
  processos conseguem escutar a mesma porta, e os dois contariam o tempo.

**Ponto de entrada do Bridge:** o pareamento da extensão deve nascer daqui, não
de um segundo modelo de confiança.

---

## 12. Dispatcher / resync

```text
NOW_PLAYING_INTERVAL_SECONDS = 1.0
HEARTBEAT_INTERVAL_SECONDS   = 10.0
POSITION_RESYNC_SECONDS      = 15.0
```

`_vale_enviar` compara a mensagem **sem `positionSeconds`** (`_sem_posicao`) —
só transmite quando algo muda de verdade, mais um resync periódico porque a
contagem local acumula erro. O celular conta os segundos sozinho.

O contrato de campos é fechado dos dois lados: `NowPlayingSession` no backend e
`isNowPlayingSession` no frontend. Campo novo em um só lado faz o celular
**descartar a mensagem inteira**, em silêncio.

---

## 13. Onde o Browser Bridge se conecta

| # | Ponto | Arquivo |
|---|---|---|
| 1 | Nova fonte, irmã da SMTC e da janela | `Dispatcher._read_now_playing` |
| 2 | Media Merger substitui a composição embutida | `_read_windows` |
| 3 | `currentTime` real rebaixa o relógio a fallback | `RelogioDaMidia` |
| 4 | `tab.audible` entra na Consumption Policy | `audio_activity` + `recorder` |
| 5 | `EPISODE_CHANGED` substitui a inferência por título | `HistoryRecorder.observar` |
| 6 | Sessão por aba substitui "um processo Chrome" | `media/session.py` |
| 7 | Pareamento da extensão | `security/pairing.py` |
| 8 | Campos novos exigem os DOIS lados do contrato | `schemas/ws.py` + `protocol.ts` |

---

## 14. O que a Fase 3 vai ter de desmontar com cuidado

1. A janela é lida dentro da leitura da SMTC, com a plataforma já resolvida.
2. O título resolvido julga a linha do tempo da SMTC.
3. `limpar_titulo_de_janela` é aplicada aos dois títulos, não só ao da janela.
4. `episodio_da_janela` compara as duas fontes; só existe com as duas.
5. `focus.py` importa `now_playing` dentro da função para não inverter a
   dependência.

Cada um destes está coberto em `backend/tests/test_characterization_media.py`.
