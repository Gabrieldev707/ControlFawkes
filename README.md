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
```

Variações fechadas como `abrir a max`, `vai para o youtube` e `coloca spotify`
também são reconhecidas. Pesquisas determinísticas aceitam somente YouTube e
Spotify e apenas abrem a página de resultados, sem escolher ou reproduzir algo
ambíguo. Texto fora da tabela retorna `UNKNOWN_COMMAND`; não há LLM, pesquisa
fora desses templates ou execução arbitrária.

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

O MVP controla a janela/aplicativo atualmente ativo. A identificação de mídia
depende de uma plataforma conhecida no título da janela em primeiro plano e não
descobre players em segundo plano. Não escolhe conteúdo,
não confirma reprodução dentro de serviços, não controla TV e não automatiza
login. Voz e transcrição permanecem desabilitadas. Seek e fullscreen dependem
dos atalhos aceitos pelo aplicativo ativo. O teste físico final no iPhone
permanece responsabilidade do usuário.

Se o iPhone não acessar a página, confirme o IPv4, o perfil privado da rede e
as regras do firewall; verifique também se o roteador não usa isolamento de
clientes. O teste físico no iPhone é uma validação manual, não simulada pelo CI.
