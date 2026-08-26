# Validação física — o que só um dedo prova

> A suíte automatizada tem 1.196 testes de backend e 399 de frontend, e todos
> passam. Eles provam a LÓGICA: a mensagem chega, é validada, e chama o
> adaptador certo. Os adaptadores dos testes são falsos.
>
> **Nenhum teste automatizado prova que o dedo no celular move o mouse desta
> máquina.** É isso que este documento cobre, e é a Fase 18 do Master Loop.

Data da última validação física completa registrada: **09/08/2026**
(`FINAL_VALIDATION.md`). Desde então houve nove commits e, em 25/08, mudanças
que alteram o alvo de todos os botões de mídia.

---

## Por que revalidar agora

Três mudanças de 25/08/2026 decidem **qual janela** cada botão encontra:

| mudança | o que ela altera |
|---|---|
| `platform_of` só reconhece navegador | qual janela é um serviço |
| `find()` passou a usar `media_window()` | qual janela recebe a tecla |
| `_da_ponte` cria leitura sem o Windows | se os controles ficam ativos |

E o conserto do bfcache no content script nunca rodou até a extensão ser
recarregada.

---

## Antes de começar

- [ ] Extensão recarregada em `chrome://extensions`
- [ ] Backend subido **pelo venv** — `backend\.venv\Scripts\python.exe`, e não
      pelo Python do sistema (sem `winsdk`/`pycaw` ele fica cego; medido)
- [ ] Terminal do backend visível: falhas agora imprimem `[leitura]` ou
      `[historico]` em vez de sumirem

Quando algo falhar, o comando que responde sem adivinhação:

```
backend\.venv\Scripts\python.exe -c "import httpx,json;print(json.dumps(httpx.get('http://127.0.0.1:8100/bridge/diagnostico').json(),indent=2,ensure_ascii=False))"
```

---

## 0. O que JÁ foi validado em 26/08/2026

Marcado com as palavras do usuário, e não por dedução minha. Cada linha abaixo
foi ele quem confirmou, olhando a tela do celular:

- [x] **Netflix** — obra, `E1 · Pilot`, posição e histórico. *"JOGA CHAMPAGNE
      CLAUDE PELA PRIMEIRA VEZ LEU"*
- [x] **Disney+** — `T1 E1 · Nunca Conheça seus Heróis`, com a minutagem real
      do player (20:32 de 50:43). *"APROVADOOO"*, e depois *"testei em 2 séries
      na disney e foi"*
- [x] **Prime Video** — `T3 E7 · Fire from Olympus`. *"prime ta aprovado"*
- [x] **Max** — `Lanternas`, com a série nomeada em vez do episódio
      `"Trust Fall"` que a janela publica. *"AGORA FOI em tocando agora"* e
      *"continuar assistindo o lanternas... chegou"*
- [x] **"Continuar assistindo"** com temporada, episódio e minutagem do episódio
- [x] O tempo até a obra aparecer caiu de ~3 min para ~30 s

### O que mudou DEPOIS dessa validação, e por isso precisa de nova passada

As Fases 15, 16 e 17 entraram na mesma noite, depois dos "aprovado" acima:

- **Fase 15** trocou quem decide qual aba responde (`arbitro.py`). O caminho é
  o mesmo com uma aba só; com duas, a escolha mudou.
- **Fase 16** trocou COMO o play/pause chega: agora vai direto ao `<video>` pela
  extensão, e só cai para a barra de espaço se a ponte não responder.
- **Fase 17** passou a descartar mensagem fora de ordem.

Então a seção 1 abaixo vale de novo — e agora para os quatro serviços, não só
para a Netflix.

---

## 1. Netflix — o caminho novo

- [ ] Abrir um episódio ou filme e dar play
- [ ] O cartão mostra **o nome da obra**, não "Netflix"
- [ ] O cartão **não** diz "série não identificada" embaixo
- [ ] A barra de progresso anda sozinha
- [ ] Play/pause pelo celular: o vídeo obedece **e o ícone vira** na hora
- [ ] Tela cheia entra e sai
- [ ] −10s e +10s
- [ ] Depois de ~3 min tocando, a obra aparece em "continuar assistindo"
- [ ] Numa série, o cartão do perfil mostra `T1 E3` (só a Netflix tem adapter)

### O teste do bfcache — o conserto mais importante da auditoria

- [ ] Com o vídeo tocando, **navegar para outra página** na mesma aba
- [ ] **Voltar** (botão voltar do navegador)
- [ ] O cartão volta a atualizar em até um minuto

> Se ficar mudo, o conserto do `pageshow` não pegou. Era o defeito em que a aba
> voltava viva do bfcache e o content script já tinha desmontado tudo — para
> sempre, sem erro em lugar nenhum.

### A pendência que ficou aberta

- [ ] Com um episódio na tela, no console da aba:
      `document.querySelector('[data-uia="video-title"]')?.outerHTML`

> Vindo o bloco com a série e o "T2:E1", a cascata do adapter está certa.
> Vindo `undefined`, o piso da URL sustenta a identidade e só o NOME se perde —
> que é o modo de falha desejado, e não o inverso.

---

## 2. Não-regressão dos outros cinco

São as regras permanentes do Master Loop, e `platform_of` mexeu no que decide
todas elas. Em cada um: **tocar, pausar pelo celular, e ver o cartão nomear a
obra.**

- [ ] **Max** — a janela publica o EPISÓDIO; o cartão deve dizer isso, não
      passar o episódio por obra
- [ ] **Disney+** — a SMTC costuma pendurar aqui; o socorro pela janela tem de
      entrar
- [ ] **Prime Video**
- [ ] **YouTube** — controla e aparece no cartão, e **não** entra no histórico
- [ ] **Spotify Desktop** — o único que não passa por janela; play/pause e
      volume por aplicativo

---

## 3. Controles gerais

- [ ] Touchpad: mover, clicar, clique duplo, clique direito, rolar
- [ ] Arrastar (segurar e soltar) — e soltar o botão ao desconectar
- [ ] Teclado: digitar numa busca do serviço
- [ ] Setas direcionais e Enter
- [ ] Esc
- [ ] Volume: barra, ±, mudo
- [ ] Espelho de tela: tocar na foto clica no lugar certo
- [ ] Perfis: tocar num perfil do serviço entra nele

---

## 4. Busca

- [ ] "capitão américa" → os filmes da Marvel primeiro, todos no Disney+
- [ ] "batman" → Batman (2022) no topo
- [ ] "lanterna verde" → Lanterna Verde (2011) primeiro, "Lanternas" na lista
- [ ] A lista "Não é esse?" aparece e tocar nela troca o cartão
- [ ] Cada linha diz onde assistir

---

## 5. Falhas, que são o estado normal

- [ ] **Fechar a aba do vídeo**: o cartão some sem travar a tela
- [ ] **Desligar a extensão**: os controles continuam funcionando pela janela;
      a posição para de andar mas **não some** (fica marcada como parada)
- [ ] **Religar a extensão**: a posição recalibra sem salto absurdo
- [ ] **Reiniciar o backend com vídeo tocando**: o cartão volta em até um minuto
- [ ] **Celular fora da rede e de volta**: reconecta sozinho

---

## 6. Antes de publicar

- [ ] `npm test` e `pytest` verdes
- [ ] Nenhum `[leitura]` ou `[historico]` no terminal do backend depois de uma
      sessão inteira
- [ ] `data/historico.json` cresceu durante a sessão
- [ ] Nenhuma linha com nome de janela de editor, seção de menu ou endereço cru
- [ ] `scripts/ver_abas.py` — os cenários da Fase 14 já com dados

---

## O que continua fora do escopo, e não é bug

- **Fase 15 (árbitro de abas)** — bloqueada de propósito: o gate da Fase 14
  proíbe congelar a política antes do dataset.
- **Fase 16 (controles pela extensão)** — depende do árbitro.
- **`T1 E3` só na Netflix** — os outros serviços não publicam número de
  episódio, e escrever adapter para cada um é decisão de produto.
- **Obras chamadas "Home", "Games", "Filmes"** — o filtro de página de catálogo
  as descarta. Troca documentada: o custo inverso é a home do serviço virar
  filme assistido.
- **Player dentro de iframe** — `all_frames: false`. Os seis serviços usam o
  frame principal.


---

## 8. Fase 16 — os controles pela extensão

> Novo em 26/08/2026. Até aqui o play/pause era uma TECLA: focar a janela do
> Chrome e apertar a barra de espaço. Agora o comando vai direto ao `<video>`
> da aba que o árbitro escolheu, e a tecla virou plano B.

O que observar, em qualquer um dos quatro serviços:

- [ ] Play/pause pelo celular **sem a janela do Chrome ganhar foco**. Era o
      sintoma mais visível do caminho antigo: a janela pulava para a frente.
- [ ] Pausar e despausar **várias vezes seguidas**. O caminho antigo era um
      toggle cego e errava quando o estado real divergia do suposto — foi a
      queixa "pausa e não volta a play". Agora play e pause são comandos
      diferentes, decididos pelo estado que a página acabou de reportar.
- [ ] −10s e +10s andam exatamente dez segundos
- [ ] **Com o Chrome minimizado**, o play/pause continua funcionando. A tecla
      não conseguia; o comando consegue.

### O caso que só duas abas provam

- [ ] Abrir DUAS abas com vídeo, em serviços diferentes, e deixar as duas
      tocando
- [ ] Pelo celular, pausar
- [ ] **Confere qual das duas pausou.** Tem de ser a que o cartão está
      mostrando — não "a que estava na frente"

> Medido na Fase 14: em 6 dos 18 instantes com duas abas tocando havia MAIS DE
> UMA aba "ativa" — janelas diferentes, cada uma com a sua. A barra de espaço
> não tinha como escolher.

### Se a extensão estiver desligada

- [ ] Desligar a extensão em `chrome://extensions` e apertar play/pause
- [ ] Tem de continuar funcionando, pela tecla, como sempre funcionou

> É o plano B, e ele é o que garante que quem não instalou a extensão não
> perdeu nada.

---

## 9. Fase 14 — o único dado que falta

- [ ] Abrir DUAS abas com vídeo e pôr **uma delas em Picture-in-Picture**
      (botão direito no vídeo → "Imagem sobre imagem")
- [ ] Deixar assim por uns vinte segundos
- [ ] Rodar `backend\.venv\Scripts\python.exe scriptser_abas.py`

Isso fecha o último cenário do dataset da Fase 14. Ele tem **zero observações
em 1526**, e por isso o árbitro da Fase 15 NÃO ranqueia PiP — rankear um sinal
sem nenhuma medição é como nasceu o `confidence: 0.98` que `contratos.py`
existe para não repetir.

O que acontece hoje, dito para ninguém se surpreender: uma aba em PiP tocando,
em segundo plano, **perde** para uma aba ativa que também esteja tocando. É
justamente o caso que ela deveria ganhar.

São dez segundos de uso, e é a única coisa que separa a Fase 14 do gate verde.
