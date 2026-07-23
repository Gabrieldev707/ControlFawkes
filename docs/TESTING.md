# Testes

## Automação

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

Os testes usam adapters mockados. Eles não abrem navegador real, não alteram
volume, não movem mouse, não digitam, não mudam fullscreen e não controlam TV.

```text
AUTOMATED TESTS: PASS
MANUAL TESTS: PENDING USER VALIDATION
```

Última verificação do MVP: 71 testes de frontend e 156 de backend, lint e build
aprovados. O build mantém apenas o aviso conhecido de chunk acima de 500 kB; o
backend mantém o aviso conhecido de depreciação do TestClient do Starlette.

## Roteiro físico no iPhone

1. Abrir o frontend pelo IPv4 do computador.
2. Autenticar com o PIN exibido no backend.
3. Navegar por Home, Controle, Touchpad, Teclado, Volume, Plataformas e Ajustes.
4. Abrir Spotify e confirmar a janela real.
5. Abrir YouTube e confirmar a janela real.
6. Abrir Netflix e confirmar a janela real.
7. Forçar uma falha segura e confirmar mensagem de erro sem sucesso falso.
8. Com a janela-alvo ativa, testar play/pause.
9. Ler, aumentar, diminuir e definir o volume do Windows.
10. Ativar e desativar mudo, conferindo o estado real retornado.
11. Ativar o touchpad; testar movimento, toque, clique duplo, clique direito, scroll e arraste.
12. Testar texto, Enter, Backspace, Escape, setas, Tab e Espaço no teclado remoto.
13. Desligar o Wi-Fi e confirmar que o touchpad desativa e o app mostra desconexão.
14. Religar o Wi-Fi e confirmar reconexão automática.
15. Atualizar a página.
16. Confirmar reutilização do token sem novo PIN.

Durante o teste, manter o PC visível e usar a parada de emergência se um arraste
ficar preso. Não testar em uma janela com dados sensíveis.
