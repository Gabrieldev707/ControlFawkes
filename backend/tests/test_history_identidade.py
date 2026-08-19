"""A obra sobrevive à troca de episódio — as invariantes, travadas.

Séries inventadas de propósito. Os casos reais (Loki, Família Soprano, Batman:
Caped Crusader) entram no fim, como regressão, mas a regra tem de valer para a
CLASSE — uma correção que só funcionasse para os títulos usados no
desenvolvimento não seria correção, seria coincidência.

Os números dos casos reais foram medidos no histórico deste computador em
17/08/2026 e estão citados onde são usados.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.history.recorder import HistoryRecorder
from app.history.store import HistoryStore
from app.media.identidade import (
    IdentidadeDaObra,
    IdentidadeDaReproducao,
    chave_da_reproducao,
    de_multiplas_reproducoes,
)
from app.media.now_playing import NowPlaying


@pytest.fixture()
def store(tmp_path) -> HistoryStore:
    return HistoryStore(tmp_path / "historico.json")


def tocando(
    titulo: str,
    *,
    episodio: str | None = None,
    platform: str | None = "MAX",
    posicao: float | None = None,
    duracao: float | None = None,
    confiavel: bool = True,
) -> NowPlaying:
    return NowPlaying(
        title=titulo, artist=None, app=None, platform=platform, playing=True,
        position_seconds=posicao, duration_seconds=duracao, thumbnail=None,
        episode=episodio, trustworthy=confiavel,
    )


def assistir(rec: HistoryRecorder, sessao: NowPlaying, segundos: int) -> None:
    for _ in range(segundos):
        rec.observar(sessao, 1.0)


# ── As identidades ────────────────────────────────────────────────────────


def test_a_obra_e_a_reproducao_sao_coisas_diferentes():
    obra = IdentidadeDaObra(titulo="Série Inventada", platform="MAX")
    primeiro = IdentidadeDaReproducao(obra, episodio="Piloto", duracao=1800.0)
    segundo = IdentidadeDaReproducao(obra, episodio="O Segundo", duracao=1750.0)

    assert primeiro.obra == segundo.obra
    assert primeiro.chave != segundo.chave


def test_uma_obra_sem_nome_nao_e_identidade():
    with pytest.raises(ValueError):
        IdentidadeDaObra(titulo="   ", platform="MAX")


def test_a_mesma_reproducao_lida_duas_vezes_da_a_mesma_chave():
    """As casas decimais da SMTC oscilam entre leituras. Sem arredondar, cada
    leitura viraria uma reprodução nova e nada nunca herdaria nada."""
    assert chave_da_reproducao("Piloto", 1800.4) == chave_da_reproducao("Piloto", 1800.1)


def test_sem_nome_e_sem_duracao_nao_ha_reproducao_identificada():
    """Fingir uma chave faria duas reproduções desconhecidas passarem por
    iguais — e aí a posição de uma vazaria para a outra."""
    assert chave_da_reproducao(None, None) is None


def test_a_duracao_distingue_episodios_quando_o_nome_falta():
    """O nome do episódio só existe quando as DUAS fontes respondem. Quando só
    uma responde, a duração é o que sobra."""
    assert chave_da_reproducao(None, 1800.0) != chave_da_reproducao(None, 2400.0)


# ── episodeTitle nunca substitui workTitle ────────────────────────────────


def test_o_episodio_nunca_vira_a_chave_da_obra(store: HistoryStore):
    rec = HistoryRecorder(store)
    assistir(rec, tocando("Série Inventada", episodio="Piloto"), 300)
    rec.encerrar()

    chaves = [item.chave for item in store.listar()]
    assert chaves == ["MAX::serie inventada"]
    assert "piloto" not in chaves[0]


def test_o_titulo_guardado_e_o_da_obra_e_o_episodio_fica_a_parte(store: HistoryStore):
    rec = HistoryRecorder(store)
    assistir(rec, tocando("Série Inventada", episodio="Piloto"), 300)
    rec.encerrar()

    item = store.listar()[0]
    assert item.titulo == "Série Inventada"
    assert item.episodio == "Piloto"


def test_now_playing_representa_obra_E_episodio_sem_escolher(store: HistoryStore):
    """A invariante escrita como pergunta: dá para saber os dois ao mesmo
    tempo? O cartão do celular já mostra os dois — e o histórico agora também
    guarda os dois, em campos diferentes."""
    sessao = tocando("Série Inventada", episodio="Piloto")

    assert sessao.title == "Série Inventada"
    assert sessao.episode == "Piloto"

    rec = HistoryRecorder(store)
    assistir(rec, sessao, 300)
    rec.encerrar()
    guardado = store.listar()[0]

    assert (guardado.titulo, guardado.episodio) == ("Série Inventada", "Piloto")


# ── A obra é estável entre episódios ──────────────────────────────────────


def test_uma_serie_inteira_e_uma_linha_so(store: HistoryStore):
    rec = HistoryRecorder(store)
    for numero, nome in enumerate(("Piloto", "O Segundo", "O Terceiro", "O Quarto"), 1):
        assistir(
            rec,
            tocando("Série Inventada", episodio=nome, duracao=1800.0 + numero,
                    posicao=1700.0 + numero),
            200,
        )
    rec.encerrar()

    assert len(store.listar()) == 1


def test_trocar_de_episodio_nao_cria_nem_perde_a_obra(store: HistoryStore):
    rec = HistoryRecorder(store)
    assistir(rec, tocando("Série Inventada", episodio="Piloto", duracao=1800.0), 300)
    antes = store.listar()[0].chave

    assistir(rec, tocando("Série Inventada", episodio="O Segundo", duracao=1750.0), 300)
    rec.encerrar()
    depois = [item.chave for item in store.listar()]

    assert depois == [antes]


def test_o_tempo_de_qualquer_episodio_soma_na_obra(store: HistoryStore):
    """A invariante em números: quatro episódios de 200 segundos são 800
    segundos da OBRA, e não quatro obras de 200."""
    rec = HistoryRecorder(store)
    for nome in ("Piloto", "O Segundo", "O Terceiro", "O Quarto"):
        assistir(rec, tocando("Série Inventada", episodio=nome, duracao=1800.0), 200)
    rec.encerrar()

    item = store.listar()[0]
    assert item.segundos == pytest.approx(800.0, abs=5.0)


def test_terminar_um_episodio_nao_termina_a_serie(store: HistoryStore):
    """O bug do Loki, na forma geral. Acabar um episódio é o momento em que a
    pessoa MAIS quer o próximo — e era quando a série sumia da tela."""
    store.registrar(
        "Série Inventada", "MAX", segundos=1790,
        posicao=1790.0, duracao=1800.0, episodio="Piloto", agora=1,
    )

    item = store.listar()[0]
    assert item.terminado is False
    assert [i.titulo for i in store.continuar()] == ["Série Inventada"]


def test_um_filme_terminado_continua_saindo_da_lista(store: HistoryStore):
    """O par obrigatório: a correção não pode virar "nada nunca termina"."""
    store.registrar("Filme Inventado", "MAX", 6000, posicao=5900.0, duracao=6000.0, agora=1)

    assert store.listar()[0].terminado is True
    assert store.continuar() == []


# ── A armadilha: a posição de um episódio que acabou ──────────────────────


def test_a_posicao_de_um_episodio_nao_sobrevive_ao_proximo(store: HistoryStore):
    store.registrar(
        "Série Inventada", "MAX", 1790, posicao=1790.0, duracao=1800.0,
        episodio="Piloto", agora=1,
    )
    store.registrar(
        "Série Inventada", "MAX", 60, posicao=60.0, duracao=1750.0,
        episodio="O Segundo", agora=2,
    )

    item = store.listar()[0]
    assert item.posicao == 60.0
    assert item.episodio == "O Segundo"


def test_uma_leitura_que_nao_sabe_da_reproducao_nao_apaga_a_posicao(store: HistoryStore):
    """O outro lado, e ele é igualmente obrigatório: não saber não contradiz.

    Uma leitura em que a janela respondeu e a SMTC não vem sem posição nenhuma.
    Se isso apagasse o que já se sabia, "continuar de onde parou" pararia de
    funcionar em toda máquina com a SMTC pendurada — que é esta aqui.
    """
    store.registrar("Filme Inventado", "MAX", 600, posicao=100.0, duracao=9000.0, agora=1)
    store.registrar("Filme Inventado", "MAX", 600, posicao=None, duracao=None, agora=2)

    assert store.listar()[0].posicao == 100.0


def test_nenhuma_quantidade_de_episodios_desfazia_a_marca(store: HistoryStore):
    """A prova de que a armadilha era permanente, e de que não é mais.

    Medido antes da correção, com o arquivo real: dez minutos do episódio
    seguinte, depois uma hora, e a série continuava fora de "continuar
    assistindo" — porque a posição do episódio terminado era herdada de novo a
    cada gravação.
    """
    store.registrar(
        "Série Inventada", "MAX", 1790, posicao=1790.0, duracao=1800.0,
        episodio="Piloto", agora=1,
    )
    for minuto in range(6):
        store.registrar(
            "Série Inventada", "MAX", 600, posicao=None, duracao=None, agora=10 + minuto,
        )

    assert [i.titulo for i in store.continuar()] == ["Série Inventada"]


# ── lastActivity e ordenação ──────────────────────────────────────────────


def test_consumo_valido_atualiza_a_ultima_atividade(store: HistoryStore):
    store.registrar("Série Inventada", "MAX", 300, None, None, episodio="Piloto", agora=1000)
    antes = store.listar()[0].visto_em

    store.registrar("Série Inventada", "MAX", 300, None, None, episodio="O Segundo", agora=5000)
    depois = store.listar()[0].visto_em

    assert antes == 1000
    assert depois == 5000


def test_a_obra_de_agora_sobe_para_o_topo(store: HistoryStore):
    store.registrar("Vista Ontem", "MAX", 600, None, None, agora=1000)
    store.registrar("Vista Hoje Cedo", "MAX", 600, None, None, agora=2000)
    store.registrar("Série Inventada", "MAX", 600, None, None, episodio="Piloto", agora=3000)

    # E agora um episódio novo da primeira, que estava no fundo.
    store.registrar("Vista Ontem", "MAX", 600, None, None, episodio="Novo", agora=9000)

    assert [i.titulo for i in store.continuar()][0] == "Vista Ontem"


def test_continuar_assistindo_ordena_por_atividade_e_nao_por_tempo_total(
    store: HistoryStore,
):
    """Quem tem mais horas não é quem está assistindo agora."""
    store.registrar("Maratonada", "MAX", 100_000, None, None, agora=1000)
    store.registrar("Começada Agora", "MAX", 300, None, None, agora=9000)

    assert [i.titulo for i in store.continuar()] == ["Começada Agora", "Maratonada"]


# ── Episódio sem obra resolvida ───────────────────────────────────────────


def test_um_episodio_sem_obra_conhecida_nao_vira_obra(store: HistoryStore):
    """A invariante mais importante deste arquivo. O Max publica na janela o
    nome do EPISÓDIO; quando a SMTC não responde, ninguém sabe a série.

    Está no backup deste histórico o que acontecia sem esta regra: "46 Long",
    "Pilot", "Campo dos Sonhos" e "Acampamorty de Férias" viraram obras
    assistidas, cada uma com o seu pedaço do tempo.
    """
    rec = HistoryRecorder(store)
    assistir(rec, tocando("Members Only", confiavel=False), 400)
    rec.encerrar()

    assert store.listar() == []


def test_o_episodio_entra_na_obra_que_o_servico_ja_tinha_nomeado(store: HistoryStore):
    """E o outro lado da mesma invariante: não descartar a associação anterior
    em silêncio.

    A SMTC nomeou a série, depois pendurou. A janela do Max só sabe dizer o
    episódio. O tempo é da série — jogá-lo fora era o que fazia a obra parar de
    contar no meio da sessão.
    """
    rec = HistoryRecorder(store)
    assistir(rec, tocando("Série Inventada", episodio="Piloto"), 300)
    assistir(rec, tocando("O Segundo Episódio", confiavel=False), 300)
    rec.encerrar()

    itens = store.listar()
    assert [i.titulo for i in itens] == ["Série Inventada"]
    assert itens[0].segundos == pytest.approx(600.0, abs=5.0)
    assert itens[0].episodio == "O Segundo Episódio"


def test_a_obra_lembrada_e_por_servico(store: HistoryStore):
    """Lembrar "Série do Max" e atribuir a ela um episódio do Disney+ seria
    inventar uma associação que ninguém observou."""
    rec = HistoryRecorder(store)
    assistir(rec, tocando("Série do Max", episodio="Piloto", platform="MAX"), 300)
    assistir(rec, tocando("Episódio Solto", platform="NETFLIX", confiavel=False), 300)
    rec.encerrar()

    assert [i.titulo for i in store.listar()] == ["Série do Max"]


# ── A evidência indireta de que a linha é de uma série ────────────────────


def test_tempo_maior_que_a_duracao_denuncia_a_serie():
    """Sem nome de episódio nenhum: 7850 segundos não cabem em 1680."""
    assert de_multiplas_reproducoes(7850, 1680.0, viu_episodio=False) is True


def test_um_filme_visto_uma_vez_nao_e_confundido_com_serie():
    assert de_multiplas_reproducoes(5900, 6000.0, viu_episodio=False) is False


def test_sem_duracao_nao_se_conclui_nada_por_esse_caminho():
    assert de_multiplas_reproducoes(100_000, None, viu_episodio=False) is False


def test_ver_um_episodio_basta_como_prova_direta():
    assert de_multiplas_reproducoes(10, 99999.0, viu_episodio=True) is True


# ── Regressão: os casos reais medidos ─────────────────────────────────────


def test_regressao_loki_volta_para_continuar_assistindo(store: HistoryStore):
    """Medido em 17/08/2026: 30444 segundos acumulados, `posicao` 2226,5 de
    `duracao` 2241,2 — razão 0,9935, acima do corte de 0,94.

    Trinta mil segundos são a série; dois mil e duzentos são um episódio.
    """
    store.registrar(
        "Loki", "DISNEY_PLUS", segundos=30444,
        posicao=2226.529369, duracao=2241.166666, agora=1,
    )

    item = store.listar()[0]
    assert item.multiplas_reproducoes is True
    assert item.terminado is False
    assert [i.titulo for i in store.continuar()] == ["Loki"]


def test_regressao_um_registro_antigo_se_recupera_sem_migracao(store: HistoryStore):
    """O arquivo gravado ANTES da correção não tem os campos novos — e é nele
    que a série já está marcada como terminada. A recuperação acontece na
    LEITURA, senão a tela continuaria errada até alguém apagar o histórico."""
    store._gravar({
        "DISNEY_PLUS::loki": {
            "titulo": "Loki", "platform": "DISNEY_PLUS", "segundos": 30444.0,
            "posicao": 2226.529369, "duracao": 2241.166666, "vistoEm": 1.0,
            "posterUrl": None, "generos": [], "terminado": True,
        },
    })

    assert [i.titulo for i in store.continuar()] == ["Loki"]


def test_regressao_familia_soprano_continua_contando_com_a_smtc_pendurada(
    store: HistoryStore,
):
    """O caso do Max, com os títulos reais. "Members Only" e "46 Long" são
    episódios; a obra é "Família Soprano", e ela precisa continuar somando."""
    rec = HistoryRecorder(store)
    assistir(rec, tocando("Família Soprano", episodio="Members Only"), 300)
    assistir(rec, tocando("46 Long", confiavel=False), 300)
    rec.encerrar()

    itens = store.listar()
    assert [i.titulo for i in itens] == ["Família Soprano"]
    assert "MAX::46 long" not in {i.chave for i in itens}


def test_regressao_batman_nao_anuncia_progresso_de_episodio(store: HistoryStore):
    """Medido: 7850 segundos assistidos, `posicao` 484,9 de `duracao` 1680,0.
    A tela dizia "faltam 20 min" de uma série já terminada."""
    store.registrar(
        "Batman: Caped Crusader", "PRIME_VIDEO", segundos=7850,
        posicao=484.943334, duracao=1680.008, agora=1,
    )

    obra = store.continuar()[0].como_obra()
    assert obra["posicao"] is None
    assert obra["duracao"] is None


# ── Perda de dado x invisibilidade ────────────────────────────────────────
#
# A distinção que a auditoria de 17/08/2026 obrigou a fazer, e que muda tudo:
# os 19 registros do histórico real estavam TODOS no disco. Nenhum tinha sido
# apagado. O que a tela mostrava é que era outra coisa.
#
# Estes testes travam a diferença, para a próxima vez que "sumiu" for dito.


def test_reiniciar_o_servidor_nao_apaga_o_historico(tmp_path):
    """Cada `HistoryStore` lê o mesmo arquivo do zero. Não há estado em memória
    que um restart possa perder — e é isso que este teste garante que continue
    valendo."""
    caminho = tmp_path / "historico.json"
    HistoryStore(caminho).registrar("Obra Inventada", "MAX", 600, None, None, agora=1)

    # Outro processo, outra instância, mesmo arquivo.
    depois = HistoryStore(caminho).listar()

    assert [i.titulo for i in depois] == ["Obra Inventada"]


def test_nada_desaparece_do_arquivo_por_ficar_velho(store: HistoryStore):
    """Não existe expiração por tempo. O único corte é o teto de itens, e ele
    é por QUANTIDADE e explícito — ver `MAXIMO_DE_ITENS`."""
    store.registrar("Muito Antiga", "MAX", 600, None, None, agora=1)
    for numero in range(20):
        store.registrar(f"Recente {numero}", "MAX", 600, None, None, agora=1000 + numero)

    assert "Muito Antiga" in {i.titulo for i in store.listar()}


def test_o_que_sai_de_continuar_continua_existindo(store: HistoryStore):
    """A regra que separa "sumiu da tela" de "sumiu do disco".

    Medido no histórico real: `listar()` devolvia 17 obras e `continuar()`
    devolvia 10. As 7 diferenças estavam todas no arquivo — uma barrada por
    `terminado`, seis pelo limite da lista.
    """
    for numero in range(15):
        store.registrar(f"Obra {numero:02}", "MAX", 600, None, None, agora=1000 + numero)
    store.registrar("Filme Terminado", "MAX", 600, 5900.0, 6000.0, agora=2000)

    tudo = {i.titulo for i in store.listar()}
    na_tela = {i.titulo for i in store.continuar(limite=10)}

    assert len(na_tela) == 10
    assert na_tela < tudo
    # E o que ficou de fora não sumiu: continua inteiro, e ainda dá para dizer
    # por que cada um não está na tela.
    assert "Filme Terminado" in tudo
    assert "Filme Terminado" not in na_tela


def test_as_duas_telas_nunca_discordam_sobre_a_obra_existir(store: HistoryStore):
    """"Porque você assistiu Loki" achava Loki e "Continuar assistindo" não.

    Os dois blocos leem o MESMO arquivo com filtros diferentes — `listar()` sem
    corte, `continuar()` sem os terminados e com teto. A divergência é legítima,
    e a regra é a direção: tudo o que está em "continuar" está em `listar()`.
    O contrário é que pode faltar, e sempre por um motivo que se sabe dizer.
    """
    store.registrar("Série Inventada", "MAX", 30_000, 2226.0, 2241.0,
                    episodio="Piloto", agora=1)
    store.registrar("Filme Terminado", "MAX", 6000, 5900.0, 6000.0, agora=2)

    todas = {i.chave for i in store.listar()}
    na_tela = {i.chave for i in store.continuar()}

    assert na_tela <= todas
    for item in store.listar():
        if item.chave not in na_tela:
            # Só há um motivo possível, e ele é verificável.
            assert item.terminado is True


# ── Continuar assistindo, serviço a serviço ───────────────────────────────
#
# A faixa principal tem teto, e um teto único faz os serviços disputarem entre
# si. Medido em 17/08/2026: três vídeos do YouTube de 16/08 empurraram para
# fora do corte tudo o que era de 14/08 -- Família Soprano, A Casa do Dragão,
# Rick and Morty e Batman: Caped Crusader estavam no arquivo, inteiros, e não
# cabiam na tela.


def test_maratonar_um_servico_nao_enterra_os_outros(store: HistoryStore):
    """O caso real, reproduzido com serviços de verdade e obras inventadas."""
    store.registrar("Série do Max", "MAX", 4501, None, None, agora=1000)
    store.registrar("Filme do Prime", "PRIME_VIDEO", 7850, None, None, agora=1100)
    for numero in range(12):
        store.registrar(f"Obra nova {numero:02}", "DISNEY_PLUS", 600, None, None,
                        agora=5000 + numero)

    principal = {i.titulo for i in store.continuar(limite=10)}
    por_servico = dict(store.continuar_por_servico())

    # Na faixa principal as obras novas empurraram o resto para fora — e isso é
    # a lista fazendo o que foi pedida para fazer.
    assert "Série do Max" not in principal
    # Nas faixas por serviço, cada obra volta ao lugar dela.
    assert [i.titulo for i in por_servico["MAX"]] == ["Série do Max"]
    assert [i.titulo for i in por_servico["PRIME_VIDEO"]] == ["Filme do Prime"]


def test_cada_servico_tem_o_proprio_teto(store: HistoryStore):
    for numero in range(14):
        store.registrar(f"Obra {numero:02}", "MAX", 600, None, None, agora=1000 + numero)

    assert len(dict(store.continuar_por_servico(limite_por_servico=10))["MAX"]) == 10


def test_os_servicos_vem_pela_atividade_mais_recente(store: HistoryStore):
    store.registrar("Antiga", "MAX", 600, None, None, agora=1000)
    store.registrar("Do meio", "PRIME_VIDEO", 600, None, None, agora=2000)
    store.registrar("De agora", "DISNEY_PLUS", 600, None, None, agora=3000)

    ordem = [servico for servico, _ in store.continuar_por_servico()]

    assert ordem == ["DISNEY_PLUS", "PRIME_VIDEO", "MAX"]


def test_dentro_do_servico_a_ordem_tambem_e_por_atividade(store: HistoryStore):
    store.registrar("Vista antes", "MAX", 600, None, None, agora=1000)
    store.registrar("Vista agora", "MAX", 600, None, None, agora=9000)

    assert [i.titulo for i in dict(store.continuar_por_servico())["MAX"]] == [
        "Vista agora", "Vista antes",
    ]


def test_obra_terminada_nao_aparece_em_nenhuma_faixa(store: HistoryStore):
    store.registrar("Filme Terminado", "MAX", 6000, 5900.0, 6000.0, agora=1)

    assert store.continuar_por_servico() == []


def test_obra_sem_servico_reconhecido_nao_vira_secao(store: HistoryStore):
    """Não há em que seção pô-la, e inventar uma "outros" seria dar nome ao que
    não tem."""
    store.registrar("Sem Serviço", None, 600, None, None, agora=1)

    assert store.continuar_por_servico() == []


def test_uma_serie_aparece_na_faixa_do_servico_dela(store: HistoryStore):
    """O fecho entre as duas correções: a série que voltou a não terminar
    também precisa aparecer na seção certa."""
    store.registrar(
        "Loki", "DISNEY_PLUS", 30444, 2226.529369, 2241.166666, agora=1,
    )

    assert [i.titulo for i in dict(store.continuar_por_servico())["DISNEY_PLUS"]] == ["Loki"]


# ── Serviços que não viram histórico ──────────────────────────────────────


def test_youtube_nao_entra_no_historico(store: HistoryStore):
    """Pedido em 18/08/2026, e pelas razões que já estavam medidas: não se
    retoma um vlog, o TMDB não tem catálogo para ele, e cinco vídeos recentes
    empurravam para fora da tela tudo o que era de streaming."""
    rec = HistoryRecorder(store)
    assistir(rec, tocando("Um vídeo qualquer", platform="YOUTUBE"), 400)
    rec.encerrar()

    assert store.listar() == []


def test_o_que_ja_estava_gravado_tambem_some_da_tela(store: HistoryStore):
    """Barrar na gravação não basta: o que entrou antes da regra continua no
    arquivo, e uma correção só para o futuro deixaria a tela errada até alguém
    apagar o histórico."""
    store.registrar("Vídeo antigo", "YOUTUBE", 600, None, None, agora=1)
    store.registrar("Filme", "MAX", 600, None, None, agora=2)

    assert [i.titulo for i in store.listar()] == ["Filme"]


def test_e_sai_do_arquivo_de_verdade_quando_se_pede(store: HistoryStore):
    """"Pode tirar do histórico" pede remoção, não ocultação — eles ocupavam o
    teto de itens e apareciam para quem abrisse o arquivo."""
    store.registrar("Vídeo antigo", "YOUTUBE", 600, None, None, agora=1)
    store.registrar("Faixa", "SPOTIFY", 600, None, None, agora=2)
    store.registrar("Filme", "MAX", 600, None, None, agora=3)

    assert store.podar_fora_do_historico() == 2

    import json
    gravado = json.loads(store._caminho.read_text(encoding="utf-8"))
    assert list(gravado) == ["MAX::filme"]


def test_podar_um_arquivo_ja_limpo_nao_reescreve(store: HistoryStore):
    """Roda a cada partida do servidor: reescrever sem motivo é trocar um risco
    de escrita por nada."""
    store.registrar("Filme", "MAX", 600, None, None, agora=1)

    assert store.podar_fora_do_historico() == 0


def test_o_spotify_continua_de_fora(store: HistoryStore):
    """A regra nova não pode ter revogado a antiga sem querer."""
    rec = HistoryRecorder(store)
    assistir(rec, tocando("Uma faixa", platform="SPOTIFY"), 400)
    rec.encerrar()

    assert store.listar() == []
