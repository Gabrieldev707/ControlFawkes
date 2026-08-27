"""Um ControlFawkes por computador.

No Windows dois processos conseguem escutar a mesma porta, então o segundo
servidor sobe calado — e os dois gravam no mesmo histórico. Medido nesta
máquina: três minutos de relógio viraram seis minutos no catálogo.
"""

from pathlib import Path

import pytest

from app.security.instancia_unica import (
    VARIAVEL_DE_DESLIGAMENTO,
    JaEstaRodando,
    TravaDeInstancia,
)


@pytest.fixture
def trava_ligada(monkeypatch):
    """A suíte desliga a trava em `conftest.py`, para o `TestClient` poder subir
    a aplicação. Quem testa a própria trava precisa dela de volta."""
    monkeypatch.delenv(VARIAVEL_DE_DESLIGAMENTO, raising=False)


def test_the_second_instance_is_refused(tmp_path: Path, trava_ligada):
    caminho = tmp_path / "instancia.lock"
    primeira = TravaDeInstancia(caminho)
    primeira.tomar()

    try:
        with pytest.raises(JaEstaRodando):
            TravaDeInstancia(caminho).tomar()
    finally:
        primeira.soltar()


def test_the_lock_is_released_for_the_next_one(tmp_path: Path, trava_ligada):
    """Sem isto, reiniciar o servidor exigiria apagar um arquivo à mão."""
    caminho = tmp_path / "instancia.lock"
    primeira = TravaDeInstancia(caminho)
    primeira.tomar()
    primeira.soltar()

    segunda = TravaDeInstancia(caminho)
    segunda.tomar()   # não pode levantar
    segunda.soltar()


def test_releasing_without_taking_is_harmless(tmp_path: Path):
    TravaDeInstancia(tmp_path / "instancia.lock").soltar()


def test_an_unwritable_place_does_not_stop_the_server(tmp_path: Path):
    """Em imprevisto a trava é dispensada: um controle que não liga por causa do
    mecanismo que deveria protegê-lo é pior do que o problema que ele evita."""
    impossivel = tmp_path / "arquivo-no-lugar-da-pasta"
    impossivel.write_text("nao sou pasta", encoding="utf-8")

    TravaDeInstancia(impossivel / "instancia.lock").tomar()   # não pode levantar


def test_the_lock_can_be_turned_off_out_loud(tmp_path: Path, monkeypatch, trava_ligada):
    """A suíte sobe a aplicação inteira em processo, muitas vezes com o servidor
    de verdade no ar. Sem uma saída explícita, 172 testes quebravam por um motivo
    que não tem nada a ver com o que eles verificam — e passavam ou falhavam
    conforme houvesse ou não um servidor rodando."""
    caminho = tmp_path / "instancia.lock"
    primeira = TravaDeInstancia(caminho)
    primeira.tomar()

    try:
        monkeypatch.setenv(VARIAVEL_DE_DESLIGAMENTO, "1")
        TravaDeInstancia(caminho).tomar()   # não pode levantar
    finally:
        primeira.soltar()


def test_the_lock_is_on_by_default(tmp_path: Path, monkeypatch):
    """E "desligada" precisa ser algo que alguém escreveu de propósito: valor
    vazio ou "0" não desliga nada."""
    from app.security.instancia_unica import trava_desligada

    for valor, esperado in (("", False), ("0", False), ("1", True), ("sim", True)):
        monkeypatch.setenv(VARIAVEL_DE_DESLIGAMENTO, valor)
        assert trava_desligada() is esperado

    monkeypatch.delenv(VARIAVEL_DE_DESLIGAMENTO, raising=False)
    assert trava_desligada() is False
