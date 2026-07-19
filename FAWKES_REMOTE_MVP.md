# Fawkes Remote — Especificação do MVP

## 1. Visão geral

O **Fawkes Remote** será um módulo mobile-first para controlar, pelo iPhone, um computador Windows conectado à TV por HDMI.

A experiência deve reutilizar a identidade visual e os principais elementos do front atual do Fawkes:

- esfera/orbe central;
- animações de escuta;
- estados visuais;
- botão para falar;
- entrada por texto;
- visualizador de áudio;
- respostas dinâmicas;
- comunicação em tempo real.

O sistema será utilizado inicialmente apenas dentro da mesma rede Wi-Fi.

O Fawkes será a interface visual e de voz. O controle real do computador será executado por um serviço local determinístico.

---

## 2. Objetivo do MVP

Permitir que o usuário, pelo iPhone:

1. fale ou digite o conteúdo que deseja assistir;
2. escolha manualmente a plataforma;
3. escolha manualmente o filme ou vídeo quando houver ambiguidade;
4. controle a reprodução;
5. controle separadamente o volume do player e o volume do Windows;
6. use touchpad e teclado remoto;
7. veja feedback real de cada ação executada.

O sistema não deve usar uma LLM para escolher plataformas, filmes, vídeos ou links.

---

## 3. Princípio central de segurança

> O sistema pode interpretar comandos conhecidos, abrir plataformas oficiais, preencher pesquisas e controlar players. Ele nunca deve escolher ou abrir um resultado ambíguo sem uma ação explícita do usuário.

Regras obrigatórias:

- não clicar em links aleatórios;
- não pesquisar pelo Google para encontrar serviços;
- abrir somente domínios permitidos;
- não escolher automaticamente um filme entre vários resultados;
- não fingir que um comando foi executado;
- informar erros de forma clara;
- exigir confirmação para desligar ou reiniciar o computador.

---

## 4. Decisão arquitetural

O MVP deve ser implementado dentro do ecossistema atual do OrcTech, mas como módulo isolado.

Estrutura sugerida:

```text
OrcTech/
├── frontend/
│   └── src/
│       ├── pages/
│       │   └── FawkesRemotePage.tsx
│       ├── components/
│       │   └── fawkes-remote/
│       ├── hooks/
│       └── services/
│
└── fawkes-remote/
    ├── app/
    │   ├── api/
    │   ├── browser/
    │   ├── commands/
    │   ├── platforms/
    │   ├── security/
    │   ├── transcription/
    │   ├── websocket/
    │   └── windows/
    ├── tests/
    └── README.md
```

Branch sugerida:

```text
feat/fawkes-remote-mvp
```

O módulo deve reaproveitar componentes visuais existentes do Fawkes sempre que isso não criar acoplamento desnecessário.

---

## 5. Responsabilidades

### Fawkes Remote Frontend

Responsável por:

- interface mobile;
- animações;
- captura de áudio;
- entrada por texto;
- escolha da plataforma;
- escolha de resultados;
- controle de reprodução;
- touchpad;
- teclado remoto;
- feedback de conexão;
- feedback de sucesso ou erro.

### Fawkes Remote Server

Responsável por:

- autenticação local;
- pareamento;
- WebSocket;
- transcrição;
- interpretação determinística;
- controle do navegador;
- controle do Windows;
- adaptadores das plataformas;
- validação de comandos;
- retorno do estado atual.

### Fawkes original

No MVP, não deverá ser obrigatório executar:

- Ollama;
- Pinecone;
- memória;
- RAG;
- agente conversacional;
- raciocínio por LLM.

A identidade e os componentes visuais podem ser compartilhados sem carregar todo o cérebro atual do Fawkes.

---

## 6. Experiência mobile

A interface deve ser desenhada especificamente para a tela de um iPhone.

Não criar um dashboard técnico.

Não colocar todas as funções na mesma tela.

A aplicação deverá mudar de acordo com o contexto.

Estados principais:

```text
HOME
LISTENING
TRANSCRIBING
CONFIRMING_TRANSCRIPT
CHOOSING_PLATFORM
SEARCHING
CHOOSING_RESULT
REMOTE_CONTROL
TOUCHPAD
KEYBOARD
ERROR
DISCONNECTED
```

---

## 7. Tela inicial

Elementos principais:

- identificação discreta do Fawkes;
- esfera central;
- texto curto de orientação;
- botão para falar;
- opção para digitar;
- ícones das plataformas;
- estado da conexão com o computador.

Exemplo conceitual:

```text
FAWKES

             [ ORBE ]

        Toque para falar

    "O que vamos assistir?"

       [ Digitar comando ]

 Netflix   Max   Prime
 Disney+   YouTube

      Computador conectado
```

A esfera deve responder visualmente aos estados:

- aguardando;
- ouvindo;
- transcrevendo;
- executando;
- concluído;
- erro.

---

## 8. Entrada por voz

Fluxo:

```text
Usuário toca ou segura o botão
→ navegador grava áudio
→ áudio é enviado ao servidor local
→ servidor envia para transcrição
→ texto retorna ao celular
→ usuário confirma ou edita
→ comando é processado
```

Usar `MediaRecorder` no navegador.

A transcrição poderá usar a API de áudio da OpenAI.

O Whisper ou outro modelo de transcrição será usado apenas para converter áudio em texto.

Ele não deve decidir:

- plataforma;
- filme;
- resultado;
- link;
- ação perigosa.

Tela de confirmação:

```text
Você disse:

"Coloca Harry Potter"

[Continuar]
[Editar]
[Gravar novamente]
```

Para comandos simples durante uma reprodução, poderá existir futuramente uma configuração de execução imediata. No MVP, priorizar confirmação para evitar erros.

---

## 9. Entrada por texto

O usuário deve poder digitar o mesmo tipo de comando que falaria.

Exemplos:

```text
Harry Potter
Pesquisa Harry Potter
Abre a Netflix
Pausa
Tela cheia
Aumenta o volume do vídeo
Aumenta o volume do computador
Volta 10 segundos
```

Voz e texto devem passar pelo mesmo interpretador.

---

## 10. Interpretador determinístico

Não usar LLM para comandar o computador.

Criar um parser baseado em intenções e regras conhecidas.

Exemplo de estrutura:

```ts
type RemoteIntent =
  | { type: 'OPEN_PLATFORM'; platform: Platform }
  | { type: 'SEARCH_MEDIA'; query: string; platform?: Platform }
  | { type: 'PLAY_PAUSE' }
  | { type: 'SEEK'; seconds: number }
  | { type: 'FULLSCREEN' }
  | { type: 'EXIT_FULLSCREEN' }
  | { type: 'STREAM_VOLUME'; value?: number; delta?: number }
  | { type: 'SYSTEM_VOLUME'; value?: number; delta?: number }
  | { type: 'STREAM_MUTE' }
  | { type: 'SYSTEM_MUTE' }
  | { type: 'SHOW_TOUCHPAD' }
  | { type: 'SHOW_KEYBOARD' };
```

Exemplos de normalização:

```text
"coloca em tela cheia"
"bota full tela"
"abre em tela cheia"
→ FULLSCREEN
```

```text
"aumenta o filme"
"aumenta o volume do vídeo"
"aumenta a Netflix"
→ STREAM_VOLUME +10
```

```text
"aumenta o computador"
"aumenta o volume geral"
→ SYSTEM_VOLUME +10
```

Quando o comando não for reconhecido:

```text
"Não entendi esse comando."

[Digitar novamente]
[Falar novamente]
[Abrir controle]
```

---

## 11. Escolha da plataforma

Se o usuário não informar a plataforma, o sistema deve perguntar.

Exemplo:

```text
Usuário:
"Quero assistir Harry Potter"

Fawkes:
"Em qual plataforma?"

[Netflix]
[Max]
[Prime Video]
[Disney+]
[YouTube]
```

Os botões devem usar os ícones oficiais ou representações visuais autorizadas das plataformas.

A plataforma nunca será escolhida automaticamente no MVP.

---

## 12. Plataformas suportadas

MVP:

- Netflix;
- Max;
- Prime Video;
- Disney+;
- YouTube.

Lista fixa de domínios permitidos:

```text
netflix.com
max.com
primevideo.com
disneyplus.com
youtube.com
```

O servidor deve rejeitar navegação automática para domínios fora da lista.

---

## 13. Pesquisa de conteúdo

Fluxo:

```text
query + plataforma
→ localizar ou abrir aba oficial
→ abrir a pesquisa da plataforma
→ preencher a consulta
→ coletar resultados visíveis
→ enviar resultados ao celular
→ aguardar seleção
```

O sistema não deve abrir automaticamente o primeiro resultado.

---

## 14. Ambiguidade

Quando houver mais de um resultado, apresentar cartões no celular.

Exemplo:

```text
Encontrei estes resultados:

Harry Potter e a Pedra Filosofal
[Selecionar]

Harry Potter e a Câmara Secreta
[Selecionar]

Harry Potter e o Prisioneiro de Azkaban
[Selecionar]
```

Mesmo com apenas um resultado, mostrar:

```text
Harry Potter e a Pedra Filosofal

[Assistir]
[Voltar]
```

O servidor deverá trabalhar com identificadores internos do resultado atual, evitando aceitar uma URL arbitrária enviada pelo cliente.

---

## 15. Modo controle remoto

Após abrir uma mídia, a interface muda.

A esfera permanece menor no topo para continuar recebendo comandos de voz.

Elementos:

- play/pause;
- voltar 10 segundos;
- avançar 10 segundos;
- tela cheia;
- sair da tela cheia;
- mudo;
- volume;
- touchpad;
- teclado;
- botão para falar.

Exemplo:

```text
FAWKES                 CONECTADO

Harry Potter
Max

             [ PAUSAR ]

[Voltar 10s]       [Avançar 10s]

          [ VOLUME ]

[Tela cheia]           [Mudo]

[Touchpad]             [Teclado]

        [ Falar com Fawkes ]
```

---

## 16. Volume

Existem dois controles independentes.

### Volume do player

Controla apenas a stream atual.

Exemplos:

- volume da Netflix;
- volume da Max;
- volume do YouTube.

### Volume do Windows

Controla o volume geral do computador e da saída HDMI.

A interface pode usar uma bottom sheet:

```text
VOLUME

Player
-  ━━━━━━━●━━━━  +

Computador
-  ━━━━━━━━━●━━  +

[Mudo do player]
[Mudo do computador]
```

O sistema deve exibir os valores reais quando for possível obtê-los.

Nunca mostrar um valor falso.

---

## 17. Adaptadores de plataforma

Cada serviço deverá ter um adaptador isolado.

```ts
interface PlatformAdapter {
  id: Platform;
  domains: string[];

  open(): Promise<void>;
  focus(): Promise<void>;
  search(query: string): Promise<SearchResult[]>;
  openResult(resultId: string): Promise<void>;

  playPause(): Promise<void>;
  seek(seconds: number): Promise<void>;
  enterFullscreen(): Promise<void>;
  exitFullscreen(): Promise<void>;

  getPlayerVolume(): Promise<number | null>;
  setPlayerVolume(value: number): Promise<void>;
  mutePlayer(): Promise<void>;
}
```

Não usar cliques baseados apenas em coordenadas fixas.

Prioridade:

1. DOM do player;
2. atalhos oficiais;
3. seletor conhecido;
4. controle manual pelo touchpad.

Caso um adaptador deixe de funcionar por mudança na plataforma, as outras funções devem continuar disponíveis.

---

## 18. Touchpad

Criar tela própria.

Funções:

- mover o cursor;
- clique esquerdo;
- clique direito;
- duplo clique;
- rolagem;
- arrastar;
- Enter;
- Esc;
- voltar;
- abrir teclado.

O touchpad é o fallback universal quando uma automação específica não funcionar.

Não deve ficar espremido dentro da tela principal.

---

## 19. Teclado remoto

Funções:

- enviar texto;
- Enter;
- Esc;
- Tab;
- Backspace;
- setas;
- espaço;
- atalhos permitidos.

Não disponibilizar execução livre de PowerShell, CMD ou comandos de sistema pelo campo de texto.

---

## 20. Comunicação local

A aplicação será usada apenas na rede local no MVP.

Fluxo:

```text
iPhone
→ Wi-Fi local
→ frontend servido pelo PC
→ WebSocket/HTTP
→ serviço local
→ Windows e navegador
```

O servidor deverá exibir o endereço local:

```text
http://192.168.x.x:PORT
```

O usuário poderá adicionar a página à tela inicial do iPhone como PWA.

---

## 21. Pareamento e segurança

Na primeira conexão:

1. o computador gera um código;
2. o usuário digita o código no iPhone;
3. o servidor cria um token local;
4. o dispositivo fica autorizado.

Exemplo:

```text
Código de pareamento: 482913
```

Requisitos:

- código com expiração;
- token armazenado com segurança;
- opção de remover dispositivos;
- limite de tentativas;
- comandos validados no servidor;
- CORS restrito;
- rate limit;
- nenhuma porta exposta à internet;
- nenhuma URL arbitrária;
- nenhum comando de shell arbitrário.

---

## 22. Ações do Windows

MVP:

- aumentar/diminuir volume;
- mudo;
- mostrar área de trabalho;
- bloquear computador;
- desligar;
- reiniciar.

Desligar e reiniciar exigem confirmação e gesto prolongado.

Não incluir:

- exclusão de arquivos;
- instalação de programas;
- alteração de configurações sensíveis;
- terminal remoto;
- acesso a senhas;
- execução livre de scripts.

---

## 23. WebSocket

Mensagens sugeridas:

### Cliente para servidor

```json
{
  "type": "REMOTE_COMMAND",
  "requestId": "uuid",
  "payload": {
    "action": "FULLSCREEN",
    "platform": "NETFLIX"
  }
}
```

### Servidor para cliente

```json
{
  "type": "COMMAND_RESULT",
  "requestId": "uuid",
  "success": true,
  "message": "Tela cheia ativada."
}
```

### Erro

```json
{
  "type": "COMMAND_RESULT",
  "requestId": "uuid",
  "success": false,
  "code": "PLATFORM_NOT_ACTIVE",
  "message": "A Netflix não está ativa."
}
```

O frontend não deve presumir sucesso antes da confirmação do servidor.

---

## 24. Estados e feedback

Exibir:

- computador conectado;
- computador desconectado;
- plataforma ativa;
- ação sendo executada;
- ação concluída;
- comando não reconhecido;
- player não encontrado;
- navegador não encontrado;
- volume indisponível;
- transcrição falhou;
- dispositivo não autorizado.

Usar vibração/haptic feedback no iPhone quando suportado.

---

## 25. Desempenho mobile

Criar modo mobile leve para o visual do Fawkes.

Reduzir:

- quantidade de partículas;
- resolução do canvas;
- efeitos de pós-processamento;
- animações quando a página estiver em segundo plano;
- frequência de atualização no estado idle.

Manter:

- esfera;
- identidade;
- mudança de cor;
- resposta ao áudio;
- transições de estado.

O frontend não deve exigir Ollama, Pinecone ou processamento pesado no aparelho.

---

## 26. Tecnologias sugeridas

### Frontend

- React;
- TypeScript;
- Vite;
- Framer Motion;
- PWA;
- CSS já compatível com o projeto;
- WebSocket.

### Backend local

Aproveitar o backend Python/FastAPI já existente quando fizer sentido.

Possíveis componentes:

- FastAPI;
- WebSocket;
- Playwright;
- APIs do Windows;
- biblioteca segura para mouse/teclado;
- integração com transcrição da OpenAI.

Evitar adicionar um segundo backend em Node.js apenas por conveniência, caso o FastAPI atual consiga atender sem criar acoplamento ruim.

---

## 27. Ordem de implementação

### Fase 1 — Auditoria e isolamento

- analisar os componentes atuais do Fawkes;
- identificar o que pode ser reutilizado;
- criar branch;
- criar rota/página isolada;
- não alterar o comportamento do Fawkes atual.

### Fase 2 — Front mobile

- tela inicial;
- esfera;
- entrada por texto;
- botão de voz;
- ícones das plataformas;
- estados visuais;
- modo controle;
- touchpad;
- tela de volume.

### Fase 3 — Comunicação local

- endpoint de health;
- WebSocket;
- pareamento;
- reconexão;
- feedback real.

### Fase 4 — Controle do Windows

- volume;
- mudo;
- teclado;
- mouse;
- touchpad;
- mostrar desktop;
- bloqueio;
- desligamento com confirmação.

### Fase 5 — Navegador

- localizar Chrome/Edge;
- identificar aba ativa;
- focar janela;
- abrir domínio permitido;
- reutilizar aba existente.

### Fase 6 — Plataformas

Implementar uma por vez:

1. YouTube;
2. Netflix;
3. Max;
4. Prime Video;
5. Disney+.

Para cada plataforma:

- abrir;
- pesquisar;
- listar resultados;
- abrir resultado selecionado;
- play/pause;
- seek;
- fullscreen;
- volume;
- mute.

### Fase 7 — Voz

- MediaRecorder;
- upload;
- transcrição;
- confirmação;
- edição;
- parser;
- execução.

### Fase 8 — PWA e finalização

- manifest;
- ícones;
- instalação na tela inicial;
- safe areas do iPhone;
- reconexão;
- modo tela cheia;
- testes reais no aparelho.

---

## 28. Testes mínimos

### Unitários

- parser de comandos;
- validação de domínios;
- autorização;
- mapeamento de volume;
- validação de mensagens WebSocket.

### Integração

- cliente e servidor;
- pareamento;
- reconexão;
- envio de comando;
- retorno de erro;
- controle de volume;
- abertura de plataforma.

### Manuais

- Safari no iPhone;
- PWA adicionada à tela inicial;
- Netflix;
- Max;
- Prime Video;
- Disney+;
- YouTube;
- PC conectado por HDMI;
- troca de janela;
- navegador minimizado;
- player em tela cheia;
- queda temporária do Wi-Fi.

---

## 29. Critérios de aceite do MVP

O MVP estará concluído quando:

- o iPhone conseguir conectar ao PC pelo Wi-Fi;
- o dispositivo estiver pareado;
- o front reutilizar a identidade do Fawkes;
- o usuário puder falar ou digitar;
- a transcrição puder ser revisada;
- a plataforma for escolhida manualmente;
- resultados ambíguos forem mostrados no celular;
- nenhum resultado for aberto sem seleção;
- o usuário puder controlar play/pause;
- puder avançar e voltar;
- puder ativar tela cheia;
- puder controlar volume do player;
- puder controlar volume do Windows;
- touchpad e teclado funcionarem;
- ações retornarem sucesso ou erro real;
- nenhuma LLM for necessária para escolher ações;
- o Fawkes original continuar funcionando sem regressões.

---

## 30. Itens fora do MVP

- acesso fora de casa;
- Tailscale ou VPN;
- automação residencial;
- múltiplos computadores;
- múltiplos usuários;
- publicação na App Store;
- escolha automática de conteúdo;
- recomendação de filmes;
- conversa aberta com LLM;
- integração com Claude Code;
- integração com Codex;
- memória de preferências;
- comando de voz sem confirmação;
- suporte a todos os navegadores;
- controle remoto de arquivos.

---

## 31. Instruções para o agente implementador

1. Antes de alterar código, audite a estrutura atual do Fawkes.
2. Reutilize componentes existentes, mas não quebre o Fawkes original.
3. Crie uma branch isolada.
4. Não implemente tudo em um único arquivo.
5. Separe interface, comandos, segurança, navegador e plataformas.
6. Não use LLM para interpretar ações do computador.
7. Não use cliques aleatórios nem coordenadas fixas como solução principal.
8. Nunca abra resultados ambíguos automaticamente.
9. Mostre erros reais no frontend.
10. Faça a implementação em fases pequenas e testáveis.
11. Após cada fase, execute lint, typecheck e testes existentes.
12. Documente qualquer limitação de uma plataforma.
13. Não remova código atual sem explicar a razão.
14. Não faça commit ou push sem autorização do usuário.
15. Ao terminar, entregue um relatório com:
   - arquivos criados;
   - arquivos alterados;
   - decisões tomadas;
   - testes executados;
   - limitações;
   - próximos passos.

---

## 32. Primeira tarefa do agente

Comece apenas por estas cinco ações:

1. Audite o front e o backend atuais do Fawkes.
2. Identifique exatamente quais componentes podem ser reutilizados no mobile.
3. Proponha a arquitetura final do módulo sem implementar controles ainda.
4. Crie o esqueleto isolado da página `FawkesRemotePage`.
5. Mostre o plano de implementação e aguarde aprovação antes de avançar para automação do Windows ou das plataformas.
