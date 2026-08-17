"""Resolução de identidade — geração, ranking e a recusa honesta de escolher.

Os casos reais viram teste PERMANENTE, nunca exceção de produção. Não há
nenhum "O Rei" → id fixo aqui dentro; o que se testa é a regra que faz o
candidato certo vencer, com os dados que o TMDB devolve de verdade.

Números medidos contra a API em 15/08/2026 e usados como fixture:

    O Rei / The King / 2019 ......... popularidade 6,63
    O Rei / (nacional) / 2014 ....... popularidade 2,01
    The Gentlemen (filme) / 2020 .... popularidade 16,81
    The Gentlemen (série) / 2024 .... popularidade 30,31
"""

from __future__ import annotations

import pytest

from app.catalog.resolver import (
    Ambiguo,
    Candidato,
    Escolhido,
    Nivel,
    Observado,
    SemCandidato,
    classificar,
    normalizar,
    resolver,
    sem_ligacoes,
    tem_candidato_forte,
)


# ── Fixtures com os dados reais ───────────────────────────────────────────

O_REI_2019 = Candidato(
    tmdb_id=522627, tipo="MOVIE", titulo="O Rei",
    nomes=("O Rei", "The King"), ano=2019, popularidade=6.63,
)
O_REI_2014 = Candidato(
    tmdb_id=999001, tipo="MOVIE", titulo="O Rei",
    nomes=("O Rei",), ano=2014, popularidade=2.01,
)
O_REI_LEAO = Candidato(
    tmdb_id=8587, tipo="MOVIE", titulo="O Rei Leão",
    nomes=("O Rei Leão", "The Lion King"), ano=1994, popularidade=32.61,
)
O_REI_DO_PEDACO = Candidato(
    tmdb_id=1871, tipo="TV", titulo="O Rei do Pedaço",
    nomes=("O Rei do Pedaço", "King of the Hill"), ano=1997, popularidade=97.73,
)

GENTLEMEN_FILME = Candidato(
    tmdb_id=522627, tipo="MOVIE", titulo="Magnatas do Crime",
    nomes=("Magnatas do Crime", "The Gentlemen"), ano=2020, popularidade=16.81,
)
GENTLEMEN_SERIE = Candidato(
    tmdb_id=209867, tipo="TV", titulo="Magnatas do Crime",
    nomes=("Magnatas do Crime", "The Gentlemen"), ano=2024, popularidade=30.31,
)
GENTLEMEN_2009 = Candidato(
    tmdb_id=111222, tipo="MOVIE", titulo="The Gentlemen",
    nomes=("The Gentlemen",), ano=2009, popularidade=1.00,
)


# ── Normalização ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        ("O Rei", "o rei"),
        ("  O   REI  ", "o rei"),
        ("Magnatas do Crime", "magnatas do crime"),
        ("Batman: Caped Crusader", "batman caped crusader"),
        ("A Casa do Dragão", "a casa do dragao"),
    ],
)
def test_normalizacao(bruto, esperado):
    assert normalizar(bruto) == esperado


def test_sem_ligacoes_aproxima_titulo_localizado_do_original():
    """"O Rei" e "The King" viram "rei" e "king" — ainda diferentes, mas sem o
    artigo, que é o que mais separa um título traduzido do original."""
    assert sem_ligacoes("O Rei") == "rei"
    assert sem_ligacoes("The King") == "king"
    assert sem_ligacoes("The Gentlemen") == "gentlemen"


# ── Localização: o caso O Rei / The King ──────────────────────────────────


def test_o_titulo_localizado_encontra_a_obra_de_titulo_original_estrangeiro():
    """A mídia é observada como "O Rei"; o catálogo guarda o original "The
    King". O casamento acontece porque o TMDB devolve os DOIS nomes, sem
    tradução manual em lugar nenhum."""
    avaliacao = classificar(O_REI_2019, Observado(titulo="O Rei"))

    assert avaliacao.nivel == Nivel.TITULO


def test_com_o_ano_o_filme_de_2019_vence_deterministicamente():
    """O ano é o sinal que resolve. Medido contra a API: com
    `primary_release_year=2019` o filme certo sobe da página 2 para a 3ª
    posição da primeira."""
    resultado = resolver(
        [O_REI_LEAO, O_REI_2014, O_REI_2019, O_REI_DO_PEDACO],
        Observado(titulo="O Rei", ano=2019, tipo="MOVIE"),
    )

    assert isinstance(resultado, Escolhido)
    assert resultado.candidato is O_REI_2019
    assert resultado.nivel == Nivel.TITULO_ANO_TIPO


def test_sem_ano_a_fama_decide_e_acerta_porque_a_diferenca_e_grande():
    """O achado contra-intuitivo do diagnóstico: a popularidade NÃO era a
    culpada do bug. O de 2019 (6,63) é mais popular que o homônimo de 2014
    (2,01) — 3,3x. Se ele estivesse na lista, o desempate já acertava. O
    defeito era ele nunca entrar."""
    resultado = resolver(
        [O_REI_2014, O_REI_2019],
        Observado(titulo="O Rei"),
    )

    assert isinstance(resultado, Escolhido)
    assert resultado.candidato is O_REI_2019
    assert "popularidade" in resultado.motivo


def test_o_rei_leao_nunca_vence_o_rei_por_ser_famoso():
    """A trava que importa: `O Rei Leão` tem popularidade 32,61 contra 6,63 —
    cinco vezes mais. E perde, porque casamento exato de título é um NÍVEL
    acima, e nível não se compra com fama."""
    resultado = resolver(
        [O_REI_LEAO, O_REI_2019],
        Observado(titulo="O Rei"),
    )

    assert isinstance(resultado, Escolhido)
    assert resultado.candidato is O_REI_2019


def test_o_rei_do_pedaco_com_popularidade_altissima_tambem_perde():
    """97,73 de popularidade, e continua perdendo para um casamento exato."""
    resultado = resolver(
        [O_REI_DO_PEDACO, O_REI_LEAO, O_REI_2019],
        Observado(titulo="O Rei"),
    )

    assert isinstance(resultado, Escolhido)
    assert resultado.candidato is O_REI_2019


# ── The Gentlemen: ambiguidade real de tipo e ano ─────────────────────────


def test_the_gentlemen_sem_tipo_nem_ano_e_ambiguo():
    """Filme de 2020 e série de 2024, mesmo nome, popularidades próximas
    (16,81 e 30,31 = 1,8x). Não dá para saber qual está tocando, e inventar
    seria contaminar o histórico com o pôster errado."""
    resultado = resolver(
        [GENTLEMEN_FILME, GENTLEMEN_SERIE, GENTLEMEN_2009],
        Observado(titulo="The Gentlemen"),
    )

    assert isinstance(resultado, Ambiguo)
    assert len(resultado.candidatos) >= 2


def test_the_gentlemen_com_o_tipo_observado_deixa_de_ser_ambiguo():
    resultado = resolver(
        [GENTLEMEN_FILME, GENTLEMEN_SERIE, GENTLEMEN_2009],
        Observado(titulo="The Gentlemen", tipo="TV"),
    )

    assert isinstance(resultado, Escolhido)
    assert resultado.candidato is GENTLEMEN_SERIE


def test_the_gentlemen_com_ano_e_tipo_escolhe_o_filme_certo():
    resultado = resolver(
        [GENTLEMEN_FILME, GENTLEMEN_SERIE, GENTLEMEN_2009],
        Observado(titulo="The Gentlemen", ano=2020, tipo="MOVIE"),
    )

    assert isinstance(resultado, Escolhido)
    assert resultado.candidato is GENTLEMEN_FILME
    assert resultado.nivel == Nivel.TITULO_ANO_TIPO


def test_o_homonimo_de_2009_nao_vence_por_ter_o_titulo_principal_igual():
    """`The Gentlemen` (2009) casa exato pelo título PRINCIPAL, enquanto o de
    2020 casa pelo original. Os dois estão no mesmo nível — e aí a fama decide,
    16,81 contra 1,00."""
    resultado = resolver(
        [GENTLEMEN_2009, GENTLEMEN_FILME],
        Observado(titulo="The Gentlemen", tipo="MOVIE"),
    )

    assert isinstance(resultado, Escolhido)
    assert resultado.candidato is GENTLEMEN_FILME


# ── Provider content id ───────────────────────────────────────────────────


def test_a_associacao_guardada_ganha_de_tudo():
    """`(netflix, 81043710) → TMDB X` é identidade, não palpite. Uma vez
    resolvida com segurança, não se refaz a busca por título — que é justamente
    a etapa frágil."""
    observado = Observado(
        titulo="O Rei", provider="netflix", providerContentId="81043710",
    )

    resultado = resolver(
        [O_REI_LEAO, O_REI_2014, O_REI_2019],
        observado,
        associado=O_REI_2019.tmdb_id,
    )

    assert isinstance(resultado, Escolhido)
    assert resultado.candidato is O_REI_2019
    assert resultado.nivel == Nivel.PROVIDER_ID


# ── Ambiguidade e ausência ────────────────────────────────────────────────


def test_dois_homonimos_com_fama_parecida_ficam_sem_resolucao():
    """Melhor "O Rei" sem enriquecimento do que "O Rei" com pôster errado."""
    gemeo = Candidato(
        tmdb_id=777, tipo="MOVIE", titulo="O Rei", nomes=("O Rei",),
        ano=2001, popularidade=6.00,
    )

    resultado = resolver([O_REI_2019, gemeo], Observado(titulo="O Rei"))

    assert isinstance(resultado, Ambiguo)


def test_nenhum_candidato_responde_ao_titulo():
    resultado = resolver([O_REI_LEAO], Observado(titulo="Duna"))

    assert isinstance(resultado, SemCandidato)


def test_lista_vazia_nao_estoura():
    assert isinstance(resolver([], Observado(titulo="O Rei")), SemCandidato)


# ── Freio da expansão progressiva ─────────────────────────────────────────


def test_titulo_confirmado_por_tipo_basta_para_parar():
    avaliacoes = [classificar(O_REI_2019, Observado(titulo="O Rei", tipo="MOVIE"))]

    assert tem_candidato_forte(avaliacoes) is True


def test_titulo_sozinho_nao_basta_e_a_busca_continua():
    """O freio da primeira versão parava em `Nivel.TITULO` e recriava o bug que
    devia evitar.

    Medido contra a API: para "O Rei" a página 1 já traz um "O Rei" (2014)
    exato, o freio disparava, e o filme de 2019 — que está na página 2 — nunca
    entrava no pool. Um nome sozinho não é identidade, e num título genérico
    ele é quase nada.
    """
    avaliacoes = [classificar(O_REI_2014, Observado(titulo="O Rei"))]

    assert avaliacoes[0].nivel == Nivel.TITULO
    assert tem_candidato_forte(avaliacoes) is False


def test_so_parecidos_nao_bastam_e_a_busca_continua():
    parecido = Candidato(
        tmdb_id=1, tipo="MOVIE", titulo="O Reis", nomes=("O Reis",),
        ano=2000, popularidade=1.0,
    )
    avaliacoes = [classificar(parecido, Observado(titulo="O Rei"))]

    assert avaliacoes[0].nivel == Nivel.SIMILAR
    assert tem_candidato_forte(avaliacoes) is False


# ── Os degraus fracos, e o que impede que eles decidam errado ─────────────


def test_o_comeco_do_nome_vale_quando_sobra_subtitulo():
    """"Duna" e "Duna: Parte Dois". O serviço mostra um, o catálogo guarda o
    outro — e nenhuma comparação de texto inteiro aproxima os dois."""
    duna = Candidato(
        tmdb_id=693134, tipo="MOVIE", titulo="Duna: Parte Dois",
        nomes=("Duna: Parte Dois", "Dune: Part Two"), ano=2024, popularidade=80.0,
    )

    assert classificar(duna, Observado(titulo="Duna")).nivel == Nivel.SUBTITULO


def test_a_palavra_que_sobrevive_a_traducao_vale_como_ultimo_recurso():
    """"Caped Crusader" virou "Cruzado Encapuzado". Só "Batman" atravessou."""
    batman = Candidato(
        tmdb_id=1, tipo="TV", titulo="Batman: Cruzado Encapuzado",
        nomes=("Batman: Cruzado Encapuzado",), ano=2024, popularidade=50.0,
    )
    avaliacao = classificar(batman, Observado(titulo="Batman: Caped Crusader"))

    assert avaliacao.nivel == Nivel.PALAVRA_FORTE


def test_o_nome_do_servico_nunca_liga_duas_obras():
    """Aconteceu na tela: o histórico guardou "Prime Video: Batman: Caped
    Crusader" e a capa que apareceu foi a de um evento de boxe japonês. As duas
    dividem DUAS palavras longas — e as duas nomeiam o serviço, não a obra."""
    boxe = Candidato(
        tmdb_id=9, tipo="TV", titulo="Prime Video Boxing 11",
        nomes=("Prime Video Boxing 11",), ano=2024, popularidade=90.0,
    )
    observado = Observado(titulo="Prime Video: Batman: Caped Crusader")

    assert classificar(boxe, observado).nivel == Nivel.NENHUM
    assert isinstance(resolver([boxe], observado), SemCandidato)


def test_o_comeco_em_comum_precisa_dizer_alguma_coisa():
    """"Prime Video" é o começo de "Prime Video Boxing 11" — e não identifica
    obra nenhuma. Começo só conta quando o que se divide é o nome da obra."""
    boxe = Candidato(
        tmdb_id=9, tipo="TV", titulo="Prime Video Boxing 11",
        nomes=("Prime Video Boxing 11",), ano=2024, popularidade=90.0,
    )

    assert classificar(boxe, Observado(titulo="Prime Video")).nivel == Nivel.NENHUM


def test_o_degrau_fraco_nunca_ganha_do_titulo_exato():
    """A trava que faz os degraus novos serem seguros: eles são um NÍVEL abaixo,
    e nível não se compra com fama. `O Rei Leão` divide "rei" com `O Rei` e tem
    cinco vezes mais popularidade — e continua perdendo."""
    resultado = resolver([O_REI_LEAO, O_REI_2019], Observado(titulo="O Rei"))

    assert isinstance(resultado, Escolhido)
    assert resultado.candidato is O_REI_2019
    assert resultado.nivel == Nivel.TITULO


# ── O motivo é sempre registrável ─────────────────────────────────────────


def test_toda_escolha_diz_por_que_venceu():
    """O critério de sucesso que você definiu: a arquitetura tem de explicar
    deterministicamente por que este candidato venceu."""
    resultado = resolver(
        [O_REI_LEAO, O_REI_2019],
        Observado(titulo="O Rei", ano=2019, tipo="MOVIE"),
    )

    assert isinstance(resultado, Escolhido)
    assert resultado.motivo
    assert resultado.nivel.name == "TITULO_ANO_TIPO"


def test_toda_ambiguidade_diz_por_que_ninguem_venceu():
    resultado = resolver(
        [GENTLEMEN_FILME, GENTLEMEN_SERIE],
        Observado(titulo="The Gentlemen"),
    )

    assert isinstance(resultado, Ambiguo)
    assert "falta ano ou tipo" in resultado.motivo
