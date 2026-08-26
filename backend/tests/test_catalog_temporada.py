"""A temporada que o serviço não publica, achada no catálogo.

A Netflix escreve "E1" e cala sobre a temporada — medido em 26/08/2026 com
Breaking Bad, e confirmado olhando a página: ela não está em lugar nenhum.
Inventar "T1" erraria justamente para quem está na quinta.

Mas o catálogo conhece a série inteira. Medido contra a API real:

    T1 E1  runtime=59min  nome='Piloto'
    T2 E1  runtime=48min  nome='Seven Thirty-Seven'
    T3 E1  runtime=48min  nome='Chega!'
    T4 E1  runtime=48min  nome='Estilete'
    T5 E1  runtime=43min  nome='Viva Livre ou Morra'

A regra que separa isto de um palpite é o critério de SAÍDA: um palpite escolhe
o mais provável; aqui, sobrando mais de um candidato, a resposta é `None`.
"""

from __future__ import annotations

import httpx
import pytest

from app.catalog.tmdb import TmdbCatalog


BREAKING_BAD = {
    1: [
        {"episode_number": 1, "name": "Piloto", "runtime": 59},
        {"episode_number": 2, "name": "O Gato Está no Saco...", "runtime": 48},
    ],
    2: [
        {"episode_number": 1, "name": "Seven Thirty-Seven", "runtime": 48},
        {"episode_number": 2, "name": "Grilled", "runtime": 48},
    ],
    3: [{"episode_number": 1, "name": "Chega!", "runtime": 48}],
    4: [{"episode_number": 1, "name": "Estilete", "runtime": 48}],
    5: [
        {"episode_number": 1, "name": "Viva Livre ou Morra", "runtime": 43},
        {"episode_number": 14, "name": "Ozymandias", "runtime": 48},
    ],
}


def catalogo(series: dict | None = None, registro: list[str] | None = None) -> TmdbCatalog:
    series = BREAKING_BAD if series is None else series

    def handler(request: httpx.Request) -> httpx.Response:
        caminho = request.url.path
        if registro is not None:
            registro.append(caminho)
        if caminho.endswith("/search/tv"):
            consulta = request.url.params.get("query", "")
            if "nao existe" in consulta.lower():
                return httpx.Response(200, json={"results": []})
            return httpx.Response(200, json={
                "results": [{"id": 1396, "name": "Breaking Bad"}],
            })
        if caminho.endswith("/tv/1396"):
            return httpx.Response(200, json={"number_of_seasons": len(series)})
        for numero, episodios in series.items():
            if caminho.endswith(f"/tv/1396/season/{numero}"):
                return httpx.Response(200, json={"episodes": episodios})
        return httpx.Response(404, json={})

    return TmdbCatalog(
        api_key="chave-de-teste",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


# ── Quando dá para afirmar ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_o_nome_do_episodio_isola_a_temporada():
    """"Piloto" aparece em UMA linha da série inteira."""
    achada = await catalogo().temporada_do_episodio("Breaking Bad", "Piloto", 1, 3500.0)

    assert achada == 1


@pytest.mark.asyncio
async def test_o_nome_isola_mesmo_sem_o_numero():
    achada = await catalogo().temporada_do_episodio("Breaking Bad", "Ozymandias")

    assert achada == 5


@pytest.mark.asyncio
async def test_a_duracao_isola_quando_o_nome_falta():
    """58 minutos contra 59/48/48/48/43: só a T1 cabe."""
    achada = await catalogo().temporada_do_episodio(
        "Breaking Bad", None, 1, 3500.0,
    )

    assert achada == 1


@pytest.mark.asyncio
async def test_acento_e_caixa_nao_atrapalham():
    achada = await catalogo().temporada_do_episodio("Breaking Bad", "chega", 1)

    assert achada == 3


# ── Quando NÃO dá, que é o teste que importa ──────────────────────────────

@pytest.mark.asyncio
async def test_a_duracao_que_empata_nao_responde():
    """Três episódios de 48 minutos continuam sendo três.

    É aqui que a diferença entre lookup e palpite aparece: responder "T2"
    porque é o primeiro seria escolher por sorte, e a pessoa acreditaria.
    """
    achada = await catalogo().temporada_do_episodio(
        "Breaking Bad", None, 1, 2880.0,
    )

    assert achada is None


@pytest.mark.asyncio
async def test_sem_nome_e_sem_numero_nao_se_responde():
    achada = await catalogo().temporada_do_episodio("Breaking Bad", None, None, 3500.0)

    assert achada is None


@pytest.mark.asyncio
async def test_serie_desconhecida_nao_responde():
    achada = await catalogo().temporada_do_episodio(
        "Serie Que Nao Existe", "Piloto", 1,
    )

    assert achada is None


@pytest.mark.asyncio
async def test_sem_chave_nao_ha_consulta():
    caminhos: list[str] = []
    vazio = TmdbCatalog(api_key="", client=httpx.AsyncClient())

    assert await vazio.temporada_do_episodio("Breaking Bad", "Piloto", 1) is None
    assert caminhos == []


@pytest.mark.asyncio
async def test_um_nome_repetido_em_duas_temporadas_nao_responde():
    """Séries reaproveitam nome de episódio, e aí o nome deixa de isolar."""
    repetido = {
        1: [{"episode_number": 1, "name": "Renascimento", "runtime": 48}],
        2: [{"episode_number": 1, "name": "Renascimento", "runtime": 48}],
    }

    achada = await catalogo(repetido).temporada_do_episodio(
        "Breaking Bad", "Renascimento", 1,
    )

    assert achada is None


@pytest.mark.asyncio
async def test_o_nome_repetido_ainda_pode_ser_isolado_pela_duracao():
    """O par: quando as durações diferem, o desempate volta a existir."""
    repetido = {
        1: [{"episode_number": 1, "name": "Renascimento", "runtime": 59}],
        2: [{"episode_number": 1, "name": "Renascimento", "runtime": 43}],
    }

    achada = await catalogo(repetido).temporada_do_episodio(
        "Breaking Bad", "Renascimento", 1, 3500.0,
    )

    assert achada == 1


# ── Custo ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_o_custo_e_uma_requisicao_por_temporada():
    """Seis requisições para Breaking Bad.

    É por isso que o `Dispatcher` guarda o resultado — inclusive o `None` — em
    vez de perguntar a cada volta do laço, que roda uma vez por segundo.
    """
    caminhos: list[str] = []
    await catalogo(registro=caminhos).temporada_do_episodio("Breaking Bad", "Piloto", 1)

    assert len(caminhos) == 1 + 1 + len(BREAKING_BAD)
