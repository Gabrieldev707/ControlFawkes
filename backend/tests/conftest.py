"""Ajustes válidos para a suíte inteira."""

import os

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
