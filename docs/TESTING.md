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

Última verificação da branch final: 21 arquivos/163 testes de frontend e 429
testes de backend, lint, build, compileall e `pip check` aprovados. O build
mantém o aviso conhecido de chunk acima de 500 kB; o backend mantém o aviso
conhecido de depreciação do TestClient do Starlette. `npm audit --offline`
encontrou zero vulnerabilidades no cache local; a consulta online não foi
autorizada porque enviaria metadados de dependências ao registro público.

## Roteiro físico no iPhone

1. Abrir o frontend pelo IPv4 do computador.
2. Autenticar com o PIN exibido no backend.
3. Navegar por Home, Controle, Touchpad, Teclado, Volume, Plataformas e Ajustes.
4. No Controle, testar setas, pressão contínua, OK e voltar na TV.
5. Confirmar que play/pause é central e volume −/mudo/+ exibe o nível real.
6. Abrir Spotify e confirmar a janela real.
7. Abrir YouTube e confirmar a janela real.
8. Abrir Netflix e confirmar a janela real.
9. Forçar uma falha segura e confirmar mensagem de erro sem sucesso falso.
10. Com a janela-alvo ativa, testar play/pause, seek e fullscreen.
11. Ler, aumentar, diminuir e definir o volume do Windows.
12. Ativar e desativar mudo, conferindo o estado real retornado.
13. Ativar o touchpad; testar movimento, toque, clique duplo, clique direito, scroll e arraste.
14. Testar texto, Enter, Backspace, Escape, setas, Tab e Espaço no teclado remoto.
15. Desligar o Wi-Fi e confirmar que os controles desativam e mostram `OFFLINE`.
16. Religar o Wi-Fi e confirmar reconexão automática.
17. Atualizar a página e confirmar reutilização do token sem novo PIN.
18. Com Ollama desligado, repetir pairing e um comando determinístico.
19. Opcional: configurar um modelo local e testar uma referência contextual.
20. Validar contraste, safe areas, teclado virtual e alcance com uma mão.

Durante o teste, manter o PC visível e usar a parada de emergência se um arraste
ficar preso. Não testar em uma janela com dados sensíveis.
