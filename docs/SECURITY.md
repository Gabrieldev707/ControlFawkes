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
- mídia usa somente sete ações mapeadas para teclas fixas;
- volume aceita 0–100 e deltas de somente ±5;
- pointer aceita movimento relativo limitado, scroll fixo e no máximo 60 movimentos/s;
- teclado aceita texto de até 256 caracteres sem controles e nove teclas especiais;
- Ctrl, Alt, combinações, hotkeys, shell e teclas arbitrárias não existem no contrato.

## Failsafes

O touchpad exige ativação explícita. Desativação, emergência, cancelamento e
unmount descartam movimento pendente e liberam o botão. O backend também envia
`pointer up` se a conexão cair durante um arraste e limpa o bucket do rate limit.

## Privacidade

Texto remoto não é registrado, persistido, adicionado a histórico nem devolvido
na resposta. O adapter usa eventos Unicode do Windows, sem clipboard. Tokens,
PINs, dados locais e arquivos temporários permanecem fora do Git.
