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

Especificação aprovada registrada. Primeira fatia ainda não implementada.

### Limitações

- Nenhuma ação real de plataforma ou do Windows será executada nesta fase.
- Validação pelo iPhone depende de teste manual do usuário na rede local.
- Diretórios locais não rastreados provenientes do checkout anterior não serão removidos nem versionados.

### Próxima fatia

Protocolo WebSocket v1, ciclo de PIN, armazenamento de token com hash, revogação e autenticação obrigatória.
