# ControlFawkes

Controle remoto mobile-first para comunicação local entre um iPhone e um
computador. Este é um projeto independente: o Fawkes original serve somente
como referência visual e não é alterado nem necessário em tempo de execução.

## Estado do MVP funcional

O MVP atual oferece:

- frontend React responsivo para celular;
- backend FastAPI acessível na rede local;
- protocolo WebSocket v1 com mensagens e erros fechados;
- pareamento por PIN temporário e autenticação automática por token;
- bloqueio progressivo do pareamento após tentativas erradas;
- WebSocket restrito a origens da rede local;
- armazenamento apenas do hash do token no servidor;
- revogação local de dispositivos;
- comandos de texto determinísticos para plataformas conhecidas;
- estados reais `AUTH_REQUIRED`, `READY`, `BUSY` e erro;
- reconexão contínua com backoff e retomada por rede/visibilidade;
- testes automatizados e CI.
- navegação entre Home, controle, touchpad, teclado, volume, plataformas e ajustes;
- abertura real e allowlisted de Netflix, Max, Prime Video, Disney+, YouTube e Spotify;
- controles de sistema (volume/mudo) visualmente separados dos controles do player;
- play/pause, faixa anterior/próxima, seek e fullscreen por matriz fixa da plataforma ativa;
- leitura, ajuste, delta e mudo do volume principal pelo Core Audio;
- touchpad relativo com agrupamento por frame, limite backend de 60 movimentos/s e failsafe;
- texto Unicode limitado e nove teclas especiais seguras no teclado remoto.
- tela Controle unificada com D-pad, reprodução, volume rápido, seek,
  fullscreen, Touchpad e Teclado, sem destino de navegação duplicado;
- parser determinístico para mídia e volume comuns, sem custo de inferência;
- interpretação local opcional via Ollama, sempre depois do parser e sem
  qualquer executor próprio, API paga ou dependência de nuvem.

Toda confirmação funcional depende do retorno do adapter. Falha nativa produz
`ERROR`; a interface não apresenta sucesso otimista.

## Estrutura

```text
ControlFawkes/
├── .github/workflows/ci.yml
├── backend/
│   ├── app/
│   ├── scripts/
│   └── tests/
├── docs/
└── frontend/
    └── src/
```

## Requisitos

- Python 3.12 ou compatível;
- Node.js 22 e npm;
- Ollama é opcional; o produto inteiro funciona sem ele;
- computador e iPhone na mesma rede Wi-Fi;
- permissão no firewall do Windows para as portas 5173 e 8100 em rede privada.

Redes de convidados podem isolar os dispositivos. Não exponha essas portas na
internet nem configure redirecionamento de portas no roteador.

## Instalação

No PowerShell, instale o backend:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Depois instale o frontend:

```powershell
cd ..\frontend
npm ci
```

O arquivo `.env.example` documenta a configuração. A URL WebSocket padrão usa
automaticamente o mesmo hostname pelo qual a página foi aberta e a porta 8100:

```dotenv
VITE_WS_PORT=8100
CONTROLFAWKES_LOCAL_AI=auto
CONTROLFAWKES_OLLAMA_URL=http://127.0.0.1:11434
CONTROLFAWKES_OLLAMA_MODEL=
CONTROLFAWKES_OLLAMA_TIMEOUT=5
```

Use `VITE_WS_URL` somente quando o backend estiver em outro host ou porta.

## Execução na rede local

Um único comando, na raiz do repositório, sobe frontend e backend juntos:

```powershell
npm run dev
```

O Vite já escuta na rede (`server.host` no `vite.config.ts`), então ele imprime
o endereço `Network:` para usar no iPhone. O backend imprime o PIN de seis
dígitos do pareamento no mesmo terminal, com o prefixo `[backend]`.

Para rodar apenas um dos lados, em terminais separados:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8100
```

```powershell
cd frontend
npm run dev:frontend
```

Use o endereço `Network:` impresso pelo Vite ou execute `ipconfig`, encontre o
endereço IPv4 da interface Wi-Fi e, no iPhone,
abra `http://SEU_IP:5173`. Digite o PIN mostrado pelo backend. O PIN dura cinco
minutos, aceita até cinco tentativas e só pode ser usado uma vez.

Depois de cinco erros o pareamento fica bloqueado por 60 segundos, e a espera
dobra a cada bloqueio seguido (até 15 minutos), voltando ao início após um
pareamento bem-sucedido. É isso que impede alguém na mesma rede de adivinhar o
PIN por tentativa e erro.

O WebSocket só aceita conexões cujo `Origin` seja da rede local (`localhost`,
IPs privados ou nomes `.local`), o que impede um site aberto no navegador de
falar com o backend. Para publicar o frontend em outro endereço, defina as
origens permitidas explicitamente:

```powershell
$env:FAWKES_ALLOWED_ORIGINS = "https://fawkes.exemplo.com"
```

Após o pareamento, o navegador guarda `deviceId` e o token no `localStorage`.
O servidor persiste somente o hash SHA-256 do token em `backend/data/`, pasta
ignorada pelo Git. Para listar ou revogar dispositivos:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts/manage_devices.py list
.\.venv\Scripts\python.exe scripts/manage_devices.py revoke ID_DO_DISPOSITIVO
```

## Comandos disponíveis

O parser ignora diferenças de maiúsculas, espaços extras e acentos. Exemplos:

```text
ajuda
abre netflix
abre max
abre prime video
abre disney+
abre youtube
abre spotify
abre youtube Kanye West
toca Runaway no Spotify
pesquisa Interestelar na Netflix
procura The Boys no Prime Video
play
volume 42
mudo
```

Variações fechadas como `abrir a max`, `vai para o youtube` e `coloca spotify`
também são reconhecidas. Pesquisas determinísticas aceitam YouTube, Spotify,
Netflix e Prime Video e apenas abrem a página de resultados, sem escolher ou
reproduzir algo ambíguo.

Max e Disney+ não têm URL de busca estável, então não recebem a consulta. Em
vez de sumirem da escolha — o que deixava um título exclusivo delas sem caminho
nenhum —, aparecem separadas, em "Abrir e procurar por lá": o controle abre a
plataforma e oferece mandar o título pelo teclado remoto.

### Navegar e apontar na mesma superfície

A tela de Controle tem uma superfície só, que faz as duas coisas sem modo:

| gesto | efeito |
| --- | --- |
| deslizar rápido ↑↓←→ | seta do direcional |
| arrastar devagar | move o cursor |
| tocar | clique / OK |
| dois dedos | voltar |
| segurar parado e arrastar | arrasta com o botão pressionado |

A distinção entre flick e mira é decidida no fim do gesto, pela duração e pela
distância. Decidir no começo exigiria segurar o cursor alguns quadros esperando
para saber o que o dedo ia fazer, e esse atraso é o que torna um touchpad ruim.
O preço é o cursor andar junto com o flick — inofensivo, porque mover o cursor
num menu não aciona nada.

As setas continuam nas bordas como botões de verdade: gesto sozinho seria
inacessível para leitor de tela e para quem tem limitação motora.

### Onde o título está (catálogo opcional)

Sem catálogo, a busca só sabe abrir uma URL de resultados: "harry potter" vira
uma lista de plataformas para o usuário adivinhar. Com uma chave do TMDB, o
controle passa a responder em vez de perguntar — "Harry Potter e a Pedra
Filosofal (2001), está no Max" — e leva direto para lá.

```powershell
# Chave gratuita em https://www.themoviedb.org/settings/api
$env:CONTROLFAWKES_TMDB_KEY = "sua-chave"
$env:CONTROLFAWKES_TMDB_REGION = "BR"      # opcional
$env:CONTROLFAWKES_TMDB_LANGUAGE = "pt-BR" # opcional
```

Só entram serviços por assinatura na região configurada: aluguel e compra ficam
de fora, porque quem pediu para assistir não pediu uma tela de pagamento. A
escolha manual continua embaixo do resultado — o catálogo acrescenta, nunca
substitui o caminho manual, e qualquer falha de rede cai nele em silêncio.

Duas coisas a saber: é a única parte do ControlFawkes que fala com um serviço
externo (a consulta e o endereço do pôster saem da máquina), e sem a chave o
comportamento é exatamente o de antes.

### Comando por voz

O botão de microfone grava, manda o áudio para o computador pareado e o
transcreve com o Whisper da OpenAI rodando local, pelo faster-whisper. O áudio
não sai da máquina e o arquivo temporário é apagado assim que a transcrição
termina. O texto resultante passa pelo mesmo parser do campo digitado.

```powershell
# Modelo. `small` acerta nomes próprios ("Harry Potter"); `base` é mais rápido,
# mas erra bastante em português.
$env:CONTROLFAWKES_WHISPER_MODEL = "small"
$env:CONTROLFAWKES_WHISPER_LANGUAGE = "pt"
$env:CONTROLFAWKES_WHISPER_COMPUTE = "int8"
$env:CONTROLFAWKES_VOICE = "on"    # "off" desliga o endpoint
```

O modelo é baixado na primeira execução (~460 MB para o `small`) e carregado no
startup, para o primeiro comando não pagar a espera. Sem o faster-whisper
instalado o resto do controle continua funcionando: só a voz responde que está
indisponível.

Duas coisas valem saber antes de contar com a voz numa demonstração:

- **Latência acompanha a CPU livre.** Num Ryzen 5 5625U com a máquina ocupada
  (llama-server rodando), um comando de 4 s levou de 7 s a 9 s. Com a CPU livre
  cai bastante. `CONTROLFAWKES_WHISPER_THREADS` limita as threads quando a
  máquina está dividida com outra coisa pesada.
- **O microfone exige HTTPS.** `getUserMedia` só existe em contexto seguro, e
  `http://IP-DA-REDE:5173` não é um. No computador (`localhost`) a voz funciona
  direto; para usar no celular, suba o controle por HTTPS (abaixo).

### Voz no celular: HTTPS na rede local

Um comando gera o certificado e outro sobe os dois lados por HTTPS:

```powershell
npm run certificado   # uma vez
npm run dev:https     # no lugar de npm run dev
```

O certificado é assinado pela própria máquina e inclui o IP da rede local — sem
esse endereço dentro dele, o iOS recusa a conexão mesmo depois de confiar no
certificado. Ele fica em `backend/data/certs/`, pasta ignorada pelo Git: a
chave privada não vai para o repositório.

No iPhone, abra o endereço `https://` que o Vite imprime. O Safari vai avisar
do certificado: toque em **Mostrar detalhes** e depois em **Visitar este site**.
Se o microfone continuar bloqueado, instale o certificado — abra o arquivo
`.crt` pelo Safari, aceite o perfil e ligue-o em **Ajustes › Geral › Sobre ›
Certificados confiáveis**.

O `npm run dev` continua existindo sem HTTPS, para quando a voz não for
necessária.

### IA local opcional

Ollama é apenas um fallback para texto que o parser devolveu como desconhecido.
Em `auto`, deixar `CONTROLFAWKES_OLLAMA_MODEL` vazio desliga toda inferência.
Para usar um modelo local já instalado, por exemplo:

```powershell
$env:CONTROLFAWKES_LOCAL_AI = "auto"
$env:CONTROLFAWKES_OLLAMA_MODEL = "qwen2.5:3b"
npm run dev
```

O modelo só escolhe entre intents existentes e devolve JSON validado. Plataforma
e ação precisam estar ancoradas no texto ou no contexto curto do mesmo
`deviceId`. JSON inválido, campo extra, ação inventada, timeout, modelo ausente
ou Ollama desligado preservam o fallback `UNKNOWN_COMMAND`. Não existe chamada
de shell, PowerShell, URL ou tecla arbitrária, e nenhuma API externa é usada.

## Protocolo resumido

O endpoint WebSocket é `/ws`. Toda mensagem do cliente inclui
`protocolVersion: 1`, `type` e `requestId`; `payload` existe somente quando o
tipo exige dados. Uma conexão começa em
`AUTH_REQUIRED`; `PAIR_DEVICE` ou `AUTH` válidos levam a `READY`. Um
`TEXT_COMMAND` autenticado produz `BUSY`, seguido por `COMMAND_RESULT` ou
`ERROR`, e então `READY`.

Payloads com campos extras, JSON inválido, versões incompatíveis e comandos
antes da autenticação são rejeitados com códigos explícitos.

O contrato completo está em [docs/PROTOCOL.md](docs/PROTOCOL.md).

## Verificação

Frontend:

```powershell
cd frontend
npm run lint
npm run build
npm run test -- --run
```

Backend:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

O CI repete lint, build e testes do frontend e toda a suíte do backend em cada
push e pull request.

O roteiro físico completo de 16 passos está em [docs/TESTING.md](docs/TESTING.md).

## Limites atuais

O produto controla a janela/aplicativo atualmente ativo. A identificação de mídia
depende de uma plataforma conhecida no título da janela em primeiro plano e não
descobre players em segundo plano. Não escolhe conteúdo,
não confirma reprodução dentro de serviços, não controla TV e não automatiza
login. Voz e transcrição permanecem desabilitadas. Seek e fullscreen dependem
dos atalhos aceitos pelo aplicativo ativo. O teste físico final no iPhone
permanece responsabilidade do usuário.

O contexto da IA local é volátil, limitado a 32 dispositivos e expira em dez
minutos. O primeiro uso após o modelo ser descarregado da memória pode exceder
o timeout e cair com segurança para `UNKNOWN_COMMAND`; aumente o timeout até 10
segundos somente se a máquina local precisar.

Se o iPhone não acessar a página, confirme o IPv4, o perfil privado da rede e
as regras do firewall; verifique também se o roteador não usa isolamento de
clientes. O teste físico no iPhone é uma validação manual, não simulada pelo CI.
