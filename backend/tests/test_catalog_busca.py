"""A busca da TELA — outra pergunta que o resolver, e por isso outro caminho.

    resolver / lookup      "qual é ESTA obra?" Uma resposta certa. Rigor é o
                           correto, e recusar é uma saída legítima.

    buscar_para_escolha    "o que você quis dizer?" Uma LISTA, e quem decide é
                           quem digitou. Descartar aqui é esconder.

O caso que expôs a diferença, medido contra a API real em 25/08/2026: a pessoa
digitou "lanterna verde" querendo a série da HBO. A série chama-se "Lanternas".
Ela não entrava nos candidatos, e se entrasse seria classificada `NENHUM` —
enquanto "Lanterna Mágica", de 1984 e sem relação nenhuma, passava no filtro.
"""

from __future__ import annotations

import httpx
import pytest

from app.catalog.tmdb import TmdbCatalog


def _busca(itens: list[dict]) -> dict:
    return {"results": itens}


def _filme(id_: int, titulo: str, ano: int, pop: float) -> dict:
    return {
        "media_type": "movie", "id": id_, "title": titulo,
        "release_date": f"{ano}-01-01", "popularity": pop, "poster_path": "/p.jpg",
    }


def _serie(id_: int, nome: str, ano: int, pop: float) -> dict:
    return {
        "media_type": "tv", "id": id_, "name": nome,
        "first_air_date": f"{ano}-01-01", "popularity": pop, "poster_path": "/p.jpg",
    }


# O que a API de verdade devolve, medido. "lanterna verde" NÃO traz "Lanternas";
# só a consulta larga "lanterna" traz.
ESTREITA = [
    _filme(1, "Lanterna Verde", 2011, 13.3),
    _serie(2, "Lanterna Verde: A Série Animada", 2011, 11.7),
    _filme(3, "Lanterna Verde: Cavaleiros Esmeralda", 2011, 4.9),
    _filme(4, "O Besouro Verde", 2011, 7.2),
]
LARGA = ESTREITA + [
    _serie(9, "Lanternas", 2026, 320.4),
    _filme(10, "Lanterna cu amintiri", 1962, 0.8),
    _filme(11, "Na Lanterna da Vida", 1998, 1.3),
]

PROVIDERS = {"results": {"BR": {"flatrate": [{"provider_id": 1899, "provider_name": "Max"}]}}}


def catalogo_da_lanterna() -> TmdbCatalog:
    """Responde diferente para a consulta estreita e para a larga.

    É o comportamento medido da API, e ele é o ponto: nenhum ajuste de ordem
    alcança um candidato que a consulta nunca gerou.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        caminho = request.url.path
        if "/watch/providers" in caminho:
            return httpx.Response(200, json=PROVIDERS)
        consulta = request.url.params.get("query", "")
        itens = LARGA if consulta.strip().lower() == "lanterna" else ESTREITA
        tipo = "tv" if caminho.endswith("/search/tv") else "movie"
        return httpx.Response(200, json=_busca(
            [i for i in itens if i["media_type"] == tipo],
        ))

    return TmdbCatalog(
        api_key="chave-de-teste",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


@pytest.mark.asyncio
async def test_a_busca_alcanca_o_titulo_que_nao_contem_as_palavras_digitadas():
    """O caso do usuário, ponta a ponta.

    A série da HBO chama-se "Lanternas". Quem digita "lanterna verde" nunca a
    alcançaria por casamento de texto — a consulta larga é que a traz.
    """
    achados = await catalogo_da_lanterna().buscar_para_escolha("lanterna verde")

    nomes = [a.title for a in achados]
    assert "Lanternas" in nomes


@pytest.mark.asyncio
async def test_a_fama_manda_entre_os_degraus_fracos():
    """Vinte e quatro vezes mais popular não pode ficar atrás de 0.8.

    Medido: `Lanterna cu amintiri` (1962, pop 0.8) era classificado
    PALAVRA_FORTE e `Lanternas` (2026, pop 320.4) era NENHUM. Meio degrau de
    heurística de texto enterrava a resposta certa.

    Nos degraus FORTES o nível continua mandando — ver o teste seguinte.
    """
    achados = await catalogo_da_lanterna().buscar_para_escolha("lanterna verde")

    nomes = [a.title for a in achados]
    assert nomes.index("Lanternas") < nomes.index("Lanterna cu amintiri")


@pytest.mark.asyncio
async def test_o_casamento_exato_continua_vencendo_a_fama():
    """O que a colapsagem dos degraus fracos NÃO pode quebrar.

    "Lanternas" é 24 vezes mais popular que "Lanterna Verde", e ainda assim
    quem digitou "lanterna verde" quer ver "Lanterna Verde" primeiro. Fama só
    decide onde o nível já não distingue.
    """
    achados = await catalogo_da_lanterna().buscar_para_escolha("lanterna verde")

    assert achados[0].title == "Lanterna Verde"


@pytest.mark.asyncio
async def test_a_busca_mostra_mais_que_duas_opcoes():
    """`OPCOES_MAXIMAS = 2` servia ao pôster, não à tela.

    Medido: havia seis candidatos válidos para "lanterna verde" e a tela
    mostrava dois. Os quatro descartados eram todos Lanterna Verde legítimos.
    """
    achados = await catalogo_da_lanterna().buscar_para_escolha("lanterna verde")

    assert len(achados) > 2


@pytest.mark.asyncio
async def test_o_limite_e_respeitado():
    achados = await catalogo_da_lanterna().buscar_para_escolha("lanterna verde", limite=3)

    assert len(achados) == 3


@pytest.mark.asyncio
async def test_a_busca_traz_onde_assistir():
    """Uma lista de títulos sem onde assistir não ajuda a escolher nada."""
    achados = await catalogo_da_lanterna().buscar_para_escolha("lanterna verde")

    assert achados[0].platforms == ["MAX"]


@pytest.mark.asyncio
async def test_sem_chave_a_busca_e_vazia_e_nao_estoura():
    vazio = TmdbCatalog(api_key="", client=httpx.AsyncClient())

    assert await vazio.buscar_para_escolha("lanterna verde") == []


@pytest.mark.asyncio
async def test_consulta_vazia_nao_vira_requisicao():
    caminhos: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        caminhos.append(request.url.path)
        return httpx.Response(200, json={"results": []})

    catalogo = TmdbCatalog(
        api_key="chave",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    assert await catalogo.buscar_para_escolha("   ") == []
    assert caminhos == []


# ── O alargamento, isolado ────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("query", "esperado"),
    [
        ("lanterna verde", ["lanterna"]),
        # Uma palavra só já É a consulta larga.
        ("batman", []),
        # Ligações não contam como palavra.
        ("o senhor dos aneis", ["senhor"]),
        # Palavra curta demais não identifica nada: alargar por ela traria o
        # catálogo inteiro.
        ("the it crowd", []),
    ],
)
def test_o_alargamento_da_consulta(query, esperado):
    assert TmdbCatalog(api_key="k")._alargamentos(query) == esperado


@pytest.mark.asyncio
async def test_o_resolver_continua_com_o_rigor_de_antes():
    """A regressão proibida.

    `lookup_options` decide o pôster do histórico, e lá errar põe a capa do
    filme de 1989 numa série. Ele NÃO pode ter ganhado a generosidade da busca.
    """
    achados = await catalogo_da_lanterna().lookup_options("lanterna verde")

    assert len(achados) <= TmdbCatalog.OPCOES_MAXIMAS
    # E o que ele escolhe continua sendo casamento de identidade, não fama.
    assert achados[0].title == "Lanterna Verde"
    assert "Lanternas" not in [a.title for a in achados]
