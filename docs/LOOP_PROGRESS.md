# ControlFawkes — Loop Progress

## Estado inicial

- Branch: `feat/fase-1-6-foundation`
- Base: `4a58c1c267b44c694ccd718d4ba2ffe744c9519d`
- Branch preservada: `feat/windows-controls-phase-2` em `1160ded9d460b76cdf4374439084355592ab337a`
- Backend inicial: 5 testes passando
- Frontend inicial: lint e build passando; script de teste ausente
- Testes manuais: `PENDING USER VALIDATION`

## Fase 1.6 — Em andamento

### Objetivo

Consolidar protocolo, autenticação local, comandos de texto, reconexão, feedback real, CI e documentação sem integrar controle do Windows.

### Fatias planejadas

1. Protocolo versionado e autenticação no backend.
2. Pareamento e validação de protocolo no frontend.
3. Comandos de texto autenticados de ponta a ponta.
4. Rede local e reconexão contínua.
5. CI, documentação e verificação final.

### Estado atual

Especificação aprovada registrada. A Fatia 1 foi implementada e verificada; a Fase 1.6 continua em andamento.

### Fatia 1 concluída — Protocolo versionado e autenticação no backend

#### Objetivo

Exigir autenticação antes de comandos e oferecer pareamento local com PIN temporário, token aleatório, persistência somente do hash e revogação.

#### Implementado

- `protocolVersion: 1` obrigatório e validado como inteiro estrito;
- tipos Pydantic fechados e campos extras proibidos;
- estado inicial `AUTH_REQUIRED` e transição autenticada para `READY`;
- PIN de seis dígitos, validade de cinco minutos, uso único e limite de cinco tentativas;
- token URL-safe aleatório, SHA-256 no armazenamento e comparação em tempo constante;
- arquivo JSON com lock e substituição atômica;
- listagem sem hashes e revogação por utilitário local;
- rejeição de JSON inválido, payload inválido, versão incompatível, mensagem desconhecida, PIN inválido, token inválido e comando não autenticado;
- seleção de plataforma autenticada retorna intenção reconhecida com `executed: false`.

#### Arquivos criados

- `backend/app/protocol/__init__.py`
- `backend/app/protocol/dispatcher.py`
- `backend/app/schemas/auth.py`
- `backend/app/security/device_store.py`
- `backend/app/security/pairing.py`
- `backend/scripts/manage_devices.py`
- `backend/tests/test_pairing.py`

#### Arquivos alterados

- `.gitignore`
- `backend/app/api/websocket.py`
- `backend/app/main.py`
- `backend/app/schemas/ws.py`
- `backend/requirements.txt`
- `backend/tests/test_ws.py`

#### Testes executados

```text
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp backend/data/pytest-fase16
.venv\Scripts\python.exe -m compileall -q app scripts tests
.venv\Scripts\python.exe scripts/manage_devices.py --help
```

#### Resultado

- Backend: 25 testes passando.
- Compilação Python: sem erros.
- Utilitário local: interface `list`/`revoke` disponível.
- Auditoria de capacidades proibidas: nenhuma referência encontrada nos arquivos da fatia.
- Aviso não bloqueante: o TestClient atual emite uma depreciação do Starlette sobre `httpx`.

#### Problemas encontrados

- O diretório temporário padrão do pytest não era gravável no sandbox.
- O primeiro caminho alternativo de `--basetemp` não possuía diretório pai.
- Valores `True` e `1.0` podiam atravessar a comparação preliminar de versão por igualdade do Python.

#### Correções realizadas

- A suíte foi isolada em um subdiretório ignorado de `backend/data/`.
- A versão passou a exigir `type(protocol_version) is int` e valor igual a `1`.
- Foram adicionados casos de regressão para versão ausente, inteira incorreta, string, booleano e decimal.

#### Limitações

- O frontend ainda não envia as novas mensagens autenticadas.
- `TEXT_COMMAND` autenticado ainda responde `NOT_IMPLEMENTED` até a fatia do parser.
- O teste pelo iPhone permanece pendente.

#### Commit

`feat: add versioned local pairing protocol`

#### Próxima fatia

Protocolo TypeScript fechado, tela de pareamento, persistência local de credenciais e autenticação automática no frontend.

### Limitações

- Nenhuma ação real de plataforma ou do Windows será executada nesta fase.
- Validação pelo iPhone depende de teste manual do usuário na rede local.
- Diretórios locais não rastreados provenientes do checkout anterior não serão removidos nem versionados.
