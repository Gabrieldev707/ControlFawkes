# Troubleshooting

## O iPhone não abre a página

- confirme que ambos estão no mesmo Wi-Fi e fora de rede guest;
- use o IPv4 da interface Wi-Fi mostrado por `ipconfig`;
- inicie Vite com `--host 0.0.0.0`;
- permita as portas 5173 e 8100 somente no perfil privado do Firewall do Windows.

## A página abre, mas fica desconectada

- confirme que o backend escuta em `0.0.0.0:8100`;
- verifique `VITE_WS_PORT=8100` e evite `VITE_WS_URL` antigo;
- recarregue depois de corrigir o firewall; o cliente tentará reconectar continuamente.

## O PIN falha

O PIN expira em cinco minutos, é de uso único e muda após excesso de tentativas.
Use o PIN mais recente exibido no terminal. Se o token foi revogado, recarregue
e faça novo pareamento.

## Plataforma ou mídia não funciona

Plataformas dependem do navegador padrão. Controles de seek/fullscreen dependem
dos atalhos aceitos pela janela ativa; traga o player para frente. Uma resposta
de erro significa que o adapter não confirmou a execução.

## Volume indisponível

Execute no Windows e instale `pycaw`, `comtypes` e `pywin32` pelos requisitos.
Reinicie o backend após instalar. O endpoint de áudio padrão precisa existir.

## Touchpad ou teclado não responde

- confirme conexão autenticada e estado `READY`;
- ative explicitamente o touchpad;
- se houver arraste preso, use “Parada de emergência” e reconecte;
- algumas janelas elevadas podem ignorar eventos de um processo não elevado;
- Ctrl/Alt, combinações e teclas fora da allowlist são rejeitados por projeto.
