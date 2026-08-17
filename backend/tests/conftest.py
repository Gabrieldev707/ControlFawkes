"""Ajustes válidos para a suíte inteira."""

import os
import tempfile
from pathlib import Path

from app.bridge.credencial import VARIAVEL_DE_CAMINHO
from app.bridge.native_host import VARIAVEL_SEM_LOG
from app.security.instancia_unica import VARIAVEL_DE_DESLIGAMENTO


# A trava de instância única impede um SEGUNDO servidor de subir, porque dois
# contam o tempo assistido em dobro. A suíte, porém, sobe a aplicação inteira em
# processo com o `TestClient`, e quase sempre com o servidor de verdade no ar —
# então ela levava a trava na cara e 172 testes quebravam por um motivo que não
# tem nada a ver com o que eles verificam.
#
# Desligada aqui, e não dentro do código de produção: a proteção continua valendo
# para qualquer execução de verdade, e quem lê a suíte vê que ela foi desligada.
os.environ[VARIAVEL_DE_DESLIGAMENTO] = "1"

# Os testes do native host exercitam `servir()` de verdade, e ele registra em
# `data/bridge/host.log` — o MESMO arquivo que serve para saber se o Chrome
# conectou. Sem desligar, cada rodada da suíte despeja "RECEBIDA PING" ali e o
# diagnóstico deixa de valer. Medido: cinco linhas falsas que pareciam vir do
# navegador.
os.environ[VARIAVEL_SEM_LOG] = "1"

# Pelo mesmo motivo, e com consequência pior: a suíte sobe a aplicação inteira
# com o `TestClient`, e o startup GERA a credencial da ponte. Sem desviar, uma
# rodada de testes escreve — ou sobrescreve — o segredo de verdade da máquina, e
# o Native Host que estiver rodando passa a apresentar uma credencial que não
# vale mais.
#
# Fora do repositório de propósito: o segredo não é código, não é fixture e não
# pode acabar num `git add -A` distraído.
os.environ[VARIAVEL_DE_CAMINHO] = str(
    Path(tempfile.gettempdir()) / "controlfawkes-testes" / "credencial",
)
