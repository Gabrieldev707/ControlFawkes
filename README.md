# ControlFawkes

Controle remoto mobile-first para comunicação local entre um iPhone e um
computador. Este é um projeto independente: o Fawkes original serve somente
como referência visual e não é alterado nem necessário em tempo de execução.

## Estado da Fase 1.6

A fundação atual oferece:

- frontend React responsivo para celular;
- backend FastAPI acessível na rede local;
- protocolo WebSocket v1 com mensagens e erros fechados;
- pareamento por PIN temporário e autenticação automática por token;
- armazenamento apenas do hash do token no servidor;
- revogação local de dispositivos;
- comandos de texto determinísticos para plataformas conhecidas;
- estados reais `AUTH_REQUIRED`, `READY`, `BUSY` e erro;
- reconexão contínua com backoff e retomada por rede/visibilidade;
- testes automatizados e CI.

Reconhecer uma plataforma **não a abre** nesta fase. A resposta informa
`executed: false`, evitando apresentar uma intenção como ação concluída.

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

Abra dois terminais a partir da raiz do repositório. Inicie o backend:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8100
```

O terminal exibirá o PIN de seis dígitos do pareamento. Em outro terminal,
inicie o frontend:

```powershell
cd frontend
npm run dev -- --host 0.0.0.0
```

Execute `ipconfig`, encontre o endereço IPv4 da interface Wi-Fi e, no iPhone,
abra `http://SEU_IP:5173`. Digite o PIN mostrado pelo backend. O PIN dura cinco
minutos, aceita até cinco tentativas e só pode ser usado uma vez.

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
```

Variações fechadas como `abrir a max`, `vai para o youtube` e `coloca spotify`
também são reconhecidas. Texto fora da tabela retorna `UNKNOWN_COMMAND`; não há
LLM, pesquisa aberta ou execução arbitrária.

## Protocolo resumido

O endpoint WebSocket é `/ws`. Toda mensagem do cliente inclui
`protocolVersion: 1`, `type`, `requestId` e `payload`. Uma conexão começa em
`AUTH_REQUIRED`; `PAIR_DEVICE` ou `AUTH` válidos levam a `READY`. Um
`TEXT_COMMAND` autenticado produz `BUSY`, seguido por `COMMAND_RESULT` ou
`ERROR`, e então `READY`.

Payloads com campos extras, JSON inválido, versões incompatíveis e comandos
antes da autenticação são rejeitados com códigos explícitos.

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

Roteiro manual pelo iPhone:

1. confirmar que a tela de pareamento abre pelo IPv4 do computador;
2. testar PIN incorreto e depois o PIN válido;
3. recarregar a página e confirmar autenticação automática;
4. enviar `abre spotify` e verificar que a interface diz apenas que o comando
   foi reconhecido, sem abrir nada;
5. enviar texto desconhecido e verificar o erro visível;
6. desligar e religar o Wi-Fi e confirmar a reconexão;
7. revogar o dispositivo, recarregar a página e confirmar novo pareamento.

## Limites atuais

A Fase 1.6 não implementa controle do Windows, abertura real de plataformas,
navegação, seleção de conteúdo, playback, volume, touchpad, teclado remoto,
transcrição ou voz. O botão de voz permanece desabilitado como “Em breve”.
Essas capacidades só podem avançar depois da aprovação explícita desta fase.

Se o iPhone não acessar a página, confirme o IPv4, o perfil privado da rede e
as regras do firewall; verifique também se o roteador não usa isolamento de
clientes. O teste físico no iPhone é uma validação manual, não simulada pelo CI.
