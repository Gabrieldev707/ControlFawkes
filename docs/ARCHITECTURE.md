# Arquitetura do ControlFawkes

## Visão geral

O ControlFawkes é um sistema local independente, composto por um cliente React
mobile-first e um backend FastAPI no computador Windows. O navegador nunca
recebe URLs livres, códigos de tecla arbitrários ou acesso direto às APIs do
sistema operacional.

```text
iPhone / React
  -> WebSocket v1
    -> validação Pydantic + autenticação
      -> dispatcher de ações fechadas
        -> adapters isolados
          -> navegador / mídia / Core Audio / mouse / teclado do Windows
```

## Backend

- `api/`: endpoints HTTP e WebSocket.
- `protocol/`: valida versão, autenticação e direciona mensagens.
- `security/`: PIN temporário, tokens, hashes e store de dispositivos.
- `commands/`: parser determinístico, sem LLM ou shell.
- `platforms/`: registry de URLs, localização do Chrome e launchers injetáveis.
- `media/`: allowlist de controles de mídia e adapter de teclas fixas.
- `windows/`: adapter assíncrono de volume Core Audio.
- `input/`: adapters de pointer e teclado, além do rate limiter.
- `schemas/`: contratos fechados do protocolo.

Os adapters recebem dependências injetáveis. A suíte automatizada fornece mocks,
portanto não abre navegador, não altera volume, não move ponteiro e não digita.
As plataformas web usam o executável do Google Chrome sem perfil temporário ou
modo anônimo, preservando a sessão local já autenticada do usuário.
O Spotify tenta primeiro o protocolo oficial do aplicativo e usa o mesmo
`BrowserLauncher` como fallback web, retornando a estratégia realmente aceita.

## Frontend

- `features/fawkes-remote/`: orquestra conexão, autenticação e ações atuais.
- `state/` e `hooks/`: navegação e transporte WebSocket.
- `pages/remote/`: telas funcionais de mídia, plataformas, volume, touchpad e teclado.
- `components/`: orb, pareamento, feedback e navegação compartilhados.
- `styles/`: tokens e layouts mobile.

Os estados de conexão, autenticação, servidor, orb, tela, plataforma e ação são
separados. O frontend só mostra sucesso depois de `COMMAND_RESULT` válido.

## Limites arquiteturais

- uma instância local controla o computador que executa o backend;
- o alvo de mídia/teclado é a janela ativa;
- não há descoberta remota, nuvem, conta externa ou exposição à internet;
- não há Redux, shell, execução de URL recebida, atalhos combinados ou histórico de texto.
