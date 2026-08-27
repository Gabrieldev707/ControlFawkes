@echo off
rem Ponto de entrada que o Chrome inicia. NADA pode escrever em stdout aqui:
rem stdout E o canal do Native Messaging, e um unico byte extra desalinha o
rem enquadramento e derruba a conexao sem mensagem de erro.
setlocal
cd /d "%~dp0.."
".venv\Scripts\python.exe" -m app.bridge.native_host
