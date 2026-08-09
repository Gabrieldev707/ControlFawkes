# Segurança

## Modelo local

O serviço deve ser usado somente em rede privada confiável. Não encaminhe as
portas 5173/8100 no roteador e não exponha o backend à internet. Redes guest
podem isolar iPhone e computador.

## Autenticação

- PIN aleatório de seis dígitos, válido por cinco minutos e de uso único;
- máximo de cinco tentativas antes de emitir novo PIN;
- token aleatório armazenado no iPhone;
- servidor persiste somente SHA-256 do token e compara em tempo constante;
- dispositivos podem ser listados e revogados localmente;
- toda ação funcional exige conexão autenticada.

## Allowlists e validação

- plataformas são identificadores fechados; o frontend nunca envia URL;
- o Chrome recebe somente URLs oficiais do registry do backend, sem shell,
  perfil codificado, credencial, URL arbitrária ou alteração do navegador padrão;
- pesquisa aceita somente rotas de resultados do YouTube, Spotify, Netflix e Prime Video construídas
  e codificadas no backend; ela não escolhe nem reproduz resultado ambíguo;
- mídia usa somente sete ações fechadas; o backend exige uma plataforma
  conhecida em primeiro plano e aplica uma matriz de teclas por plataforma;
- volume aceita 0–100 e deltas de somente ±5;
- pointer aceita movimento relativo limitado, scroll fixo e no máximo 60 movimentos/s;
- teclado aceita texto de até 256 caracteres sem controles e nove teclas especiais;
- Ctrl, Alt, combinações, hotkeys, shell e teclas arbitrárias não existem no contrato.

## Inteligência local

- nenhuma API cloud, chave externa ou telemetria é usada;
- a URL do Ollama precisa ser HTTP loopback sem credenciais;
- o parser determinístico sempre roda antes e comandos conhecidos não chamam o modelo;
- a saída usa schema discriminado, enums fechados, tipos estritos e `extra=forbid`;
- plataforma e ação precisam estar ancoradas no texto ou no contexto do mesmo dispositivo;
- timeout, erro de transporte, JSON inválido, campo extra, alucinação e exceção
  inesperada retornam ao erro seguro, sem executor alternativo;
- o modelo nunca recebe capacidade de shell, URL, tecla, pointer ou chamada de sistema.

## Failsafes

O touchpad exige ativação explícita. Desativação, emergência, cancelamento e
unmount descartam movimento pendente e liberam o botão. O backend também envia
`pointer up` se a conexão cair durante um arraste e limpa o bucket do rate limit.

## Privacidade

Texto remoto não é registrado nem devolvido na resposta. Quando a IA local está
ativa, somente plataforma, última consulta e ação ficam em memória por até dez
minutos, isoladas por `deviceId`, com limite de 32 dispositivos; nada disso é
persistido. O adapter usa eventos Unicode do Windows, sem clipboard. Tokens,
PINs, dados locais e arquivos temporários permanecem fora do Git.
