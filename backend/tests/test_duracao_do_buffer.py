"""Duração que cresce é borda de buffer, não duração.

## O que se mediu

Disney+, com Demolidor: Renascido tocando, oito leituras seguidas do
diagnóstico ao vivo em 26/08/2026:

    660,8 → 676,8 → 692,8 → 700,8 → 708,8 → 732,8 → 740,8 → 748,8

Sempre alguns segundos à frente da posição, sempre subindo. Não é um vídeo de
onze minutos: é MSE. O player monta o vídeo por segmentos, e `video.duration`
reporta a borda do BUFFER enquanto o resto não chegou.

Na tela isso é grosseiro e constante: a barra fica sempre quase cheia, o
"faltam X" fica sempre em segundos, e um episódio de cinquenta minutos se
anuncia como se estivesse acabando. Foi isto que o usuário chamou de "contagem
falsa" — e ele estava certo.

## Dois diagnósticos anteriores, os dois errados

1. "menos de 90 segundos é prévia". Suprimia reprodução de verdade no primeiro
   minuto, quando o buffer ainda é curto, e não pegava o caso medido, que já
   passava de 250 segundos.

2. "guardar a ponte basta". Não bastava: a SMTC do Chrome publica a linha do
   tempo do MESMO `<video>`, e entregava o mesmo número pela outra porta.

O que prova não é o tamanho, é o CRESCIMENTO — e o guarda tem de estar onde o
número final existe, seja qual for a fonte que o supriu.
"""

from __future__ import annotations

import pytest

from app.media.now_playing import NowPlaying
from app.protocol.dispatcher import Dispatcher
from app.windows.focus import WindowFocuser


def dispatcher() -> Dispatcher:
    """Sem janelas nem catálogo: o que se testa é o guarda."""
    return Dispatcher(
        catalog=None,
        window_focuser=WindowFocuser(window_lister=lambda: []),
    )


def leitura(posicao: float, duracao: float | None, **overrides: object) -> NowPlaying:
    campos: dict = {
        "title": "Demolidor: Renascido",
        "artist": None,
        "app": "Chrome",
        "platform": "DISNEY_PLUS",
        "playing": True,
        "position_seconds": posicao,
        "duration_seconds": duracao,
        "thumbnail": None,
        "trustworthy": True,
    }
    campos.update(overrides)
    return NowPlaying(**campos)


def observar(d: Dispatcher, leituras: list[NowPlaying]) -> NowPlaying:
    """Passa a sequência pelo guarda e devolve o último resultado."""
    ultima = None
    for cada in leituras:
        ultima = d._sem_duracao_de_buffer(cada)
    return ultima


# ── O caso medido ─────────────────────────────────────────────────────────

def test_a_duracao_que_cresce_nao_vira_duracao():
    """Os números do diagnóstico, na ordem em que chegaram."""
    crescendo = [
        leitura(646.5, 660.833332),
        leitura(666.5, 676.833332),
        leitura(676.5, 692.833332),
        leitura(686.5, 700.833332),
    ]

    final = observar(dispatcher(), crescendo)

    # A posição é real e continua valendo.
    assert final.position_seconds == pytest.approx(686.5)
    # A duração não: ela nunca descreveu a obra.
    assert final.duration_seconds is None


def test_a_duracao_parada_continua_valendo():
    """O par, e é o caso da Netflix.

    Ela publica a duração certa desde o começo — era só por isso que só ela
    estava certa.
    """
    parada = [leitura(100.0, 3500.0), leitura(110.0, 3500.0), leitura(120.0, 3500.0)]

    final = observar(dispatcher(), parada)

    assert final.duration_seconds == pytest.approx(3500.0)


def test_uma_oscilacao_de_casas_decimais_nao_e_crescimento():
    """O MSE devolve casas decimais que oscilam na mesma reprodução.

    Um limite de zero acusaria toda oscilação como buffer, e nenhuma duração
    sobreviveria.
    """
    oscilando = [leitura(100.0, 3500.001), leitura(110.0, 3500.2), leitura(120.0, 3500.05)]

    final = observar(dispatcher(), oscilando)

    assert final.duration_seconds is not None


def test_a_desconfianca_gruda():
    """Depois que a duração se provou borda de buffer, ela não se redime.

    Ela para de crescer quando o vídeo termina de baixar, e nesse ponto o
    número pode até estar certo — mas quem já mentiu não volta a ser fonte sem
    outra prova.
    """
    cresce_e_estabiliza = [
        leitura(100.0, 200.0),
        leitura(150.0, 300.0),
        leitura(200.0, 300.0),
        leitura(250.0, 300.0),
    ]

    final = observar(dispatcher(), cresce_e_estabiliza)

    assert final.duration_seconds is None


def test_a_duracao_que_DIMINUI_nao_e_buffer():
    """Duração menor é outra reprodução — o episódio seguinte, mais curto."""
    trocou = [leitura(3400.0, 3500.0), leitura(10.0, 2900.0), leitura(20.0, 2900.0)]

    final = observar(dispatcher(), trocou)

    assert final.duration_seconds == pytest.approx(2900.0)


def test_a_primeira_leitura_nao_acusa_ninguem():
    """Sem uma leitura anterior não há crescimento a observar.

    Recusar aqui deixaria toda reprodução sem duração no primeiro batimento.
    """
    final = observar(dispatcher(), [leitura(100.0, 3500.0)])

    assert final.duration_seconds == pytest.approx(3500.0)


def test_o_nome_e_a_posicao_sobrevivem():
    """O que a tela deve mostrar: o que se sabe, sem o que não se sabe.

    Nome e posição são verdade; a barra e o "faltam X" precisam de duração, e
    inventá-la é pior do que não desenhar nada.
    """
    final = observar(dispatcher(), [leitura(100.0, 110.0), leitura(150.0, 160.0)])

    assert final.title == "Demolidor: Renascido"
    assert final.position_seconds == pytest.approx(150.0)
    assert final.duration_seconds is None


def test_obras_diferentes_nao_contaminam_uma_a_outra():
    """A desconfiança é da OBRA, e não do serviço.

    Um episódio com buffer crescendo não pode apagar a duração do filme que a
    pessoa assistir depois.
    """
    d = dispatcher()
    observar(d, [leitura(100.0, 200.0), leitura(150.0, 300.0)])

    outra = observar(d, [
        leitura(100.0, 7000.0, title="Duna: Parte Dois"),
        leitura(110.0, 7000.0, title="Duna: Parte Dois"),
    ])

    assert outra.duration_seconds == pytest.approx(7000.0)


def test_sem_duracao_nao_ha_o_que_julgar():
    final = observar(dispatcher(), [leitura(100.0, None), leitura(150.0, None)])

    assert final.duration_seconds is None
    assert final.position_seconds == pytest.approx(150.0)


# ── A regressão que este guarda causou em toda série ──────────────────────
#
# A chave era `(platform, title)`, e numa série o título é o mesmo em todos os
# episódios enquanto a duração muda a cada um. Passar de um episódio de 47
# minutos para um de 48 parecia exatamente "a duração cresceu" — e a
# desconfiança gruda, então a série perdia a duração PARA SEMPRE.
#
# Medido em 27/08/2026, com a extensão mandando o número certo o tempo todo:
#
#     host.log   duration=2894.975416   (48:15, Breaking Bad T1 E6)
#     tela       "T1 E6 · 15:12"        sem o "de 48:15"
#
# Na tela, o formato certo é o do Invincible: "T3 E4 · 17:32 de 49:18". Sem
# duração, sobra só a posição — e ela sozinha não diz de onde a pessoa volta.

def episodio(duracao: float, identidade: str, posicao: float = 100.0) -> NowPlaying:
    return leitura(posicao, duracao, title="Breaking Bad", platform="NETFLIX",
                   playback_id=identidade)


def test_o_episodio_seguinte_MAIS_LONGO_nao_e_borda_de_buffer():
    """O caso exato: 47 minutos e depois 48, na mesma série."""
    d = dispatcher()

    observar(d, [episodio(2820.0, "id:70196253"), episodio(2820.0, "id:70196253")])
    seguinte = observar(d, [episodio(2880.0, "id:70196254")])

    assert seguinte.duration_seconds == pytest.approx(2880.0)


def test_a_desconfianca_de_um_episodio_nao_contamina_o_proximo():
    """Gruda dentro da reprodução, e morre com ela.

    Sem isto, um episódio que por qualquer motivo tivesse a duração crescendo
    condenava todos os episódios seguintes da mesma série.
    """
    d = dispatcher()

    # Este cresce de verdade: é borda de buffer.
    observar(d, [episodio(200.0, "id:70196253"), episodio(300.0, "id:70196253")])
    seguinte = observar(d, [episodio(2880.0, "id:70196254")])

    assert seguinte.duration_seconds == pytest.approx(2880.0)


def test_dentro_do_MESMO_episodio_o_crescimento_continua_sendo_pego():
    """O caso do Disney+ não pode ter sido perdido no conserto.

    Lá o buffer cresce DENTRO do episódio, e a identidade de reprodução não
    muda enquanto isso — é justamente esse recorte que separa os dois casos.
    """
    d = dispatcher()

    final = observar(d, [
        leitura(646.5, 660.8, playback_id="id:79955576"),
        leitura(666.5, 676.8, playback_id="id:79955576"),
        leitura(676.5, 692.8, playback_id="id:79955576"),
    ])

    assert final.duration_seconds is None


def test_sem_identidade_a_obra_ainda_serve_de_recorte():
    """Leituras que não sabem se identificar continuam com o comportamento
    antigo — e com o defeito antigo. É o piso, não o alvo."""
    d = dispatcher()

    final = observar(d, [
        leitura(100.0, 200.0, playback_id=None),
        leitura(150.0, 300.0, playback_id=None),
    ])

    assert final.duration_seconds is None
