"""Caracterização do pipeline de mídia atual — a rede de segurança da Fase 3.

Estes testes não descrevem o comportamento DESEJADO. Descrevem o comportamento
QUE EXISTE HOJE, incluindo as esquisitices, para que a separação de SMTC e
Window Title em fontes independentes (Fase 3 do Master Loop) seja provavelmente
não-regressiva em vez de esperançosamente não-regressiva.

Por que um arquivo novo, se já há testes de mídia: os que existem cobrem as
funções puras uma a uma — limpeza de título, plataforma pelo título, relógio.
O que NÃO tinha teste era justamente o que a Fase 3 vai desmontar: o caminho
combinado dentro de `WindowsNowPlayingReader._read_windows()`, onde a janela é
lida DENTRO da leitura da SMTC e o título resolvido volta a alimentar a decisão
de confiar na linha do tempo. As duas fontes estão entrelaçadas ali, e cada
entrelaçamento existe por causa de um bug medido.

Nenhuma linha de produção foi alterada para escrever isto. A SMTC é falsificada
injetando um `winsdk` de mentira em `sys.modules`, que é o que permite exercitar
a função real, com a composição real, sem abrir uma costura de teste antes da
hora.

Regra ao mexer aqui: se um destes testes falhar durante a Fase 3, a resposta
padrão NÃO é atualizar o teste. É descobrir qual heurística sumiu.
"""

from __future__ import annotations

from datetime import timedelta
import sys
import types

import pytest

from app.media.now_playing import (
    STATUS_PAUSED,
    STATUS_PLAYING,
    WindowsNowPlayingReader,
    da_janela,
    limpar_titulo_de_janela,
    plataforma_no_titulo,
)


# ── Falsificação da SMTC ──────────────────────────────────────────────────


class _Props:
    def __init__(self, title, artist=None):
        self.title = title
        self.artist = artist
        # `_ler_capa` faz `getattr(props, "thumbnail", None)`; None encerra ali
        # e o `DataReader` nunca é tocado.
        self.thumbnail = None


class _Info:
    def __init__(self, status):
        self.playback_status = status


class _Timeline:
    def __init__(self, position, end_time):
        self.position = position
        self.end_time = end_time
        # None faz a idade da medição valer zero, que é o que isola o teste do
        # relógio de parede.
        self.last_updated_time = None


class _Sessao:
    def __init__(
        self,
        app=None,
        title="",
        artist=None,
        status=STATUS_PLAYING,
        position=None,
        duration=None,
    ):
        self.source_app_user_model_id = app
        self._props = _Props(title, artist)
        self._info = _Info(status)
        self._timeline = _Timeline(
            None if position is None else timedelta(seconds=position),
            None if duration is None else timedelta(seconds=duration),
        )

    def get_playback_info(self):
        return self._info

    def get_timeline_properties(self):
        return self._timeline

    async def try_get_media_properties_async(self):
        return self._props


def _instalar_smtc(monkeypatch, sessao):
    """Põe um `winsdk` de mentira no lugar do real, só para este teste.

    A cadeia inteira de módulos é registrada para o teste não depender de o
    `winsdk` de verdade estar instalado na máquina.
    """

    class _Manager:
        @staticmethod
        async def request_async():
            class _Aberto:
                def get_current_session(self):
                    return sessao

            return _Aberto()

    controle = types.ModuleType("winsdk.windows.media.control")
    controle.GlobalSystemMediaTransportControlsSessionManager = _Manager
    streams = types.ModuleType("winsdk.windows.storage.streams")
    streams.DataReader = object

    for nome, modulo in (
        ("winsdk", types.ModuleType("winsdk")),
        ("winsdk.windows", types.ModuleType("winsdk.windows")),
        ("winsdk.windows.media", types.ModuleType("winsdk.windows.media")),
        ("winsdk.windows.media.control", controle),
        ("winsdk.windows.storage", types.ModuleType("winsdk.windows.storage")),
        ("winsdk.windows.storage.streams", streams),
    ):
        monkeypatch.setitem(sys.modules, nome, modulo)


def _leitor(monkeypatch, sessao, titulo_da_janela=None):
    _instalar_smtc(monkeypatch, sessao)
    return WindowsNowPlayingReader(
        window_title_reader=lambda _plataforma=None: titulo_da_janela,
    )


# ── A SMTC sozinha ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_smtc_resposta_normal(monkeypatch):
    leitor = _leitor(monkeypatch, _Sessao(
        app="SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify",
        title="Verdade",
        artist="Zeca Pagodinho",
        position=30.0,
        duration=258.0,
    ))

    atual = await leitor._read_windows()

    assert atual.title == "Verdade"
    assert atual.artist == "Zeca Pagodinho"
    assert atual.platform == "SPOTIFY"
    assert atual.playing is True
    assert atual.position_seconds == 30.0
    assert atual.duration_seconds == 258.0
    assert atual.position_stale is False
    assert atual.trustworthy is True


@pytest.mark.asyncio
async def test_smtc_ausente(monkeypatch):
    """Sem sessão não há o que dizer — e "nada tocando" é estado legítimo."""
    leitor = _leitor(monkeypatch, None)

    assert await leitor._read_windows() is None


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [0, 1, 2, 3])
async def test_smtc_status_que_nao_e_reproducao(monkeypatch, status):
    """Só PLAYING e PAUSED viram cartão. Fechado, parando ou trocando, não."""
    leitor = _leitor(monkeypatch, _Sessao(title="Duna", status=status))

    assert await leitor._read_windows() is None


@pytest.mark.asyncio
async def test_smtc_pausada_continua_sendo_sessao(monkeypatch):
    leitor = _leitor(monkeypatch, _Sessao(
        title="Duna", status=STATUS_PAUSED, position=10.0, duration=9000.0,
    ))

    atual = await leitor._read_windows()

    assert atual.playing is False
    assert atual.position_seconds == 10.0


@pytest.mark.asyncio
async def test_smtc_metadata_parcial(monkeypatch):
    """Sem artista, sem posição, sem duração: o cartão ainda existe.

    E sem título nenhum o nome do aplicativo assume — a última linha de
    `_read_windows`, que evita um cartão com nome vazio.
    """
    leitor = _leitor(monkeypatch, _Sessao(app="algum.app", title="", artist=None))

    atual = await leitor._read_windows()

    assert atual.title == "algum.app"
    assert atual.artist is None
    assert atual.position_seconds is None
    assert atual.duration_seconds is None


@pytest.mark.asyncio
async def test_smtc_duracao_zero_nao_e_duracao(monkeypatch):
    """Transmissão ao vivo publica fim zerado; zero não é uma duração."""
    leitor = _leitor(monkeypatch, _Sessao(
        title="Jogo ao vivo", position=120.0, duration=0.0,
    ))

    atual = await leitor._read_windows()

    assert atual.position_seconds == 120.0
    assert atual.duration_seconds is None


@pytest.mark.asyncio
async def test_smtc_que_pendura_e_abandonada_e_marca_travada(monkeypatch):
    """O timeout da SMTC — e a costura exata onde o Browser Bridge entra.

    A chamada NUNCA é cancelada: cancelar uma operação WinRT no meio a deixa
    tentando concluir numa future morta, e isso matava o laço de atualização
    inteiro. Ela é abandonada, e a rodada passa a vez.

    `travada` é o que faz o dispatcher cair para `da_janela`. Se este contrato
    mudar, o socorro do navegador para de existir sem nenhum erro aparecer.
    """
    import asyncio

    from app.media.now_playing import LeituraEmVoo

    class _Pendurado:
        async def read(self):
            await asyncio.Event().wait()

    leitura = LeituraEmVoo(_Pendurado())
    monkeypatch.setattr(
        LeituraEmVoo, "SEGUNDOS_ATE_DESISTIR", 0.0,
    )

    assert await leitura.ler() is None
    assert await leitura.ler() is None
    assert leitura.travada is True


# ── A linha do tempo congelada ────────────────────────────────────────────


def _congelar_relogio(monkeypatch, marcas):
    """Faz `time.monotonic` devolver os valores dados, em ordem."""
    from app.media import now_playing

    passos = iter(marcas)
    ultimo = [marcas[-1]]

    def falso():
        try:
            ultimo[0] = next(passos)
        except StopIteration:
            pass
        return ultimo[0]

    monkeypatch.setattr(now_playing.time, "monotonic", falso)


@pytest.mark.asyncio
async def test_timeline_congelada_com_o_mesmo_titulo_e_so_velha(monkeypatch):
    """O site demorou a publicar o próximo valor. O número continua sendo
    desta reprodução — velho não é errado.

    Antes existia só "confiável ou nada", e este caso caía no nada: a minutagem
    sumia inteira no meio do filme.
    """
    sessao = _Sessao(title="A Casa do Dragão", position=600.0, duration=4928.0)
    leitor = _leitor(monkeypatch, sessao)
    _congelar_relogio(monkeypatch, [0.0, 60.0])

    primeira = await leitor._read_windows()
    segunda = await leitor._read_windows()

    assert primeira.position_stale is False
    assert segunda.position_stale is True
    # O valor sobrevive, e sem projeção: ninguém mediu avanço nenhum.
    assert segunda.position_seconds == 600.0


@pytest.mark.asyncio
async def test_timeline_congelada_com_titulo_novo_pertence_a_outra_midia(monkeypatch):
    """O caso que a desconfiança existe para pegar.

    Medido no Chrome, que agrega todas as abas numa sessão só: ele seguia
    publicando a linha do tempo de um filme fechado minutos antes enquanto o
    título já era de outro vídeo. A posição projetada cabia na duração e
    parecia plausível.
    """
    sessao = _Sessao(title="Duna", position=1376.8, duration=9000.0)
    leitor = _leitor(monkeypatch, sessao)
    _congelar_relogio(monkeypatch, [0.0, 60.0])

    await leitor._read_windows()
    sessao._props.title = "Rick and Morty"
    depois = await leitor._read_windows()

    assert depois.title == "Rick and Morty"
    assert depois.position_seconds is None
    assert depois.position_stale is False


@pytest.mark.asyncio
async def test_timeline_que_volta_a_andar_volta_a_ser_confiavel(monkeypatch):
    """Sair do congelamento não pode exigir reiniciar o servidor."""
    sessao = _Sessao(title="A Casa do Dragão", position=600.0, duration=4928.0)
    leitor = _leitor(monkeypatch, sessao)
    _congelar_relogio(monkeypatch, [0.0, 60.0, 61.0])

    await leitor._read_windows()
    assert (await leitor._read_windows()).position_stale is True

    sessao._timeline.position = timedelta(seconds=612.0)
    voltou = await leitor._read_windows()

    assert voltou.position_stale is False
    assert voltou.position_seconds == 612.0


# ── O título da janela sozinho ────────────────────────────────────────────


@pytest.mark.parametrize(
    ("janela", "esperado"),
    [
        # Título correto, com o serviço no sufixo.
        ("Wandinha - Netflix - Google Chrome", "Wandinha"),
        # Serviço no prefixo, que é como o Prime Video nomeia.
        ("Prime Video: Batman: Caped Crusader - Google Chrome", "Batman: Caped Crusader"),
        # Serviço nos dois lados, que é a Netflix instalada como aplicativo.
        ("Netflix - Home - Netflix", "Home"),
        # Contagem de notificações que o Chrome prefixa.
        ("(2) O Justiceiro | Disney+ - Google Chrome", "O Justiceiro"),
        # A marca de janela travada, que é traduzida em todo Windows.
        ("46 Long • HBO Max - Google Chrome (Não está respondendo)", "46 Long"),
        # Parêntese que NÃO é marca de travamento continua inteiro.
        ("Duna (2021) - Netflix - Google Chrome", "Duna (2021)"),
        # Temporada diz menos que o nome da série e atrapalha o catálogo.
        ("Rick and Morty - Season 1 - Google Chrome", "Rick and Morty"),
        # Só o nome do serviço sobrevive como está: não há obra ali.
        ("Netflix", "Netflix"),
        # Só espaço vira vazio, não estoura. O `or titulo.strip()` do fim
        # devolve o original JÁ APARADO, então não há como sair espaço daqui —
        # o cartão nunca recebe um nome que parece existir e não existe.
        ("   ", ""),
    ],
)
def test_limpeza_do_titulo_da_janela(janela, esperado):
    assert limpar_titulo_de_janela(janela) == esperado


@pytest.mark.parametrize(
    ("janela", "esperado"),
    [
        ("Wandinha - Netflix - Google Chrome", "NETFLIX"),
        ("Prime Video: Batman: Caped Crusader", "PRIME_VIDEO"),
        ("O Justiceiro | Disney+ - Google Chrome", "DISNEY_PLUS"),
        ("46 Long • HBO Max - Google Chrome", "MAX"),
        ("CHEGUEI NA SÍRIA - YouTube - Google Chrome", "YOUTUBE"),
        ("Netflix", "NETFLIX"),
        # A marca de travamento não pode esconder o serviço.
        ("46 Long • HBO Max - Google Chrome (Não está respondendo)", "MAX"),
        # Sem serviço nomeado não há palpite.
        ("Alguma Coisa - Google Chrome", None),
    ],
)
def test_plataforma_reconhecida_no_titulo_da_janela(janela, esperado):
    assert plataforma_no_titulo(janela) == esperado


@pytest.mark.parametrize(
    ("plataforma", "conta"),
    [
        # Serviços que nomeiam a OBRA na janela: a leitura vale como histórico.
        ("PRIME_VIDEO", True),
        ("YOUTUBE", True),
        ("DISNEY_PLUS", True),
        # O Max nomeia o EPISÓDIO: mostrável, não afirmável como obra.
        ("MAX", False),
        # A Netflix nunca nomeia o conteúdo.
        ("NETFLIX", False),
        # Sem serviço não dá para saber qual dos dois casos é.
        (None, False),
    ],
)
def test_o_que_a_janela_sozinha_pode_afirmar(plataforma, conta):
    """`trustworthy` é a capability por serviço que a Fase 3 vai formalizar.

    Tratar todos igual custou os dois lados: com tudo confiável, uma tarde de
    Rick and Morty virou quatro "títulos assistidos" com nome de episódio; com
    nada confiável, uma hora de Batman no Prime Video não contou nada.
    """
    atual = da_janela("Alguma Obra - Google Chrome", plataforma)

    assert atual.trustworthy is conta


def test_a_janela_sozinha_nunca_sabe_posicao_nem_duracao():
    """O que se perde ao cair para a janela, e que a extensão vai devolver."""
    atual = da_janela("Prime Video: Batman - Google Chrome", "PRIME_VIDEO")

    assert atual.position_seconds is None
    assert atual.duration_seconds is None
    assert atual.thumbnail is None


def test_a_janela_vazia_nao_vira_sessao():
    assert da_janela(None, "NETFLIX") is None
    assert da_janela("", "NETFLIX") is None


# ── SMTC e Window Title COMBINADOS — o que a Fase 3 vai separar ───────────


@pytest.mark.asyncio
async def test_smtc_generica_cede_o_titulo_para_a_janela(monkeypatch):
    """O navegador publica só o nome do site na API de mídia; o nome do
    conteúdo está na janela. Sem esta troca, o cartão diria "Netflix" para todo
    filme assistido pelo navegador."""
    leitor = _leitor(
        monkeypatch,
        _Sessao(app="Chrome", title="Netflix", position=60.0, duration=3600.0),
        titulo_da_janela="Wandinha - Netflix - Google Chrome",
    )

    atual = await leitor._read_windows()

    assert atual.title == "Wandinha"
    assert atual.platform == "NETFLIX"
    # A posição continua vindo da SMTC: cada fonte entrega a metade que sabe.
    assert atual.position_seconds == 60.0
    # E o episódio fica vazio: a SMTC não nomeou nada, então não há série da
    # qual este nome seria um episódio.
    assert atual.episode is None


@pytest.mark.asyncio
async def test_a_smtc_nomeia_a_serie_e_a_janela_nomeia_o_episodio(monkeypatch):
    """Medido com A Casa do Dragão no Max: a SMTC publica o nome da SÉRIE e a
    janela publica o do EPISÓDIO. É a mesma reprodução vista de dois lugares, e
    cada lugar sabe uma metade."""
    leitor = _leitor(
        monkeypatch,
        _Sessao(app="Chrome", title="A Casa do Dragão", position=100.0, duration=4928.0),
        titulo_da_janela="The Treasons at Tumbleton • HBO Max - Google Chrome",
    )

    atual = await leitor._read_windows()

    # A obra manda no título: é ela que vira uma linha só no histórico e acha o
    # pôster certo no catálogo.
    assert atual.title == "A Casa do Dragão"
    assert atual.episode == "The Treasons at Tumbleton"
    assert atual.platform == "MAX"


@pytest.mark.asyncio
async def test_a_janela_generica_nao_rouba_o_titulo_da_smtc(monkeypatch):
    """Navegando o catálogo enquanto algo toca: a janela diz "Home", que não é
    obra nenhuma, e a SMTC continua mandando."""
    leitor = _leitor(
        monkeypatch,
        _Sessao(app="Chrome", title="Batman: Caped Crusader"),
        titulo_da_janela="Home - Netflix - Google Chrome",
    )

    atual = await leitor._read_windows()

    assert atual.title == "Batman: Caped Crusader"
    assert atual.episode is None


@pytest.mark.asyncio
async def test_o_prefixo_do_servico_sai_do_titulo_da_propria_smtc(monkeypatch):
    """O Prime Video publica "Prime Video: <obra>" na própria API de mídia.

    Sem passar pela limpeza, esse prefixo entra no histórico e vai parar na
    busca do pôster — que, encurtada, achou um evento de boxe chamado "Prime
    Video Boxing".
    """
    leitor = _leitor(
        monkeypatch,
        _Sessao(app="Chrome", title="Prime Video: Batman: Caped Crusader"),
    )

    atual = await leitor._read_windows()

    assert atual.title == "Batman: Caped Crusader"
    assert atual.platform == "PRIME_VIDEO"


@pytest.mark.asyncio
async def test_a_plataforma_vem_do_aplicativo_antes_do_titulo(monkeypatch):
    """Ordem de resolução: o aplicativo que publica sabe quem é; o título da
    SMTC costuma dizer; a janela é o último recurso.

    A comparação é por conteúdo porque a SMTC não devolve "Spotify", devolve o
    identificador do pacote.
    """
    leitor = _leitor(
        monkeypatch,
        _Sessao(app="SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify", title="Verdade"),
        titulo_da_janela="Wandinha - Netflix - Google Chrome",
    )

    atual = await leitor._read_windows()

    assert atual.platform == "SPOTIFY"


@pytest.mark.asyncio
async def test_sem_janela_a_leitura_da_smtc_continua_inteira(monkeypatch):
    """A janela é opcional: sem ela o cartão perde o nome do conteúdo do
    navegador, não a sessão."""
    leitor = _leitor(
        monkeypatch,
        _Sessao(app="Chrome", title="Batman: Caped Crusader", position=10.0),
        titulo_da_janela=None,
    )

    atual = await leitor._read_windows()

    assert atual.title == "Batman: Caped Crusader"
    assert atual.position_seconds == 10.0


@pytest.mark.asyncio
async def test_o_titulo_resolvido_e_o_que_julga_a_linha_do_tempo(monkeypatch):
    """O entrelaçamento mais fino das duas fontes, e o que mais corre risco na
    Fase 3.

    Quem decide se a linha do tempo congelada é velha ou é de outra mídia é o
    título RESOLVIDO, não o cru da SMTC. No navegador o cru é sempre o nome do
    site — "Netflix" antes, "Netflix" depois — então julgar por ele nunca
    perceberia a troca de conteúdo.
    """
    sessao = _Sessao(app="Chrome", title="Netflix", position=500.0, duration=3600.0)
    leitor = _leitor(
        monkeypatch, sessao, titulo_da_janela="Wandinha - Netflix - Google Chrome",
    )
    _congelar_relogio(monkeypatch, [0.0, 60.0])

    await leitor._read_windows()

    # A SMTC não mudou de título; só a janela mudou. Ainda assim é outra mídia.
    leitor._window_title_reader = lambda _p=None: "Round 6 - Netflix - Google Chrome"
    depois = await leitor._read_windows()

    assert depois.title == "Round 6"
    assert depois.position_seconds is None


# ── Consumo: o bug do Batman ──────────────────────────────────────────────


def test_o_enum_de_sessao_de_audio_e_o_do_core_audio():
    """`Active` é 1. Já esteve em 2, que é `Expired` — sessão morta.

    Medido ao vivo com o Disney+ reproduzindo: `chrome.exe` em State=1 e a
    função respondendo False. Com a SMTC travada é esta função que decide se há
    reprodução, então tudo no navegador era contado como pausado.
    """
    from app.windows.audio_activity import ATIVO

    assert ATIVO == 1


def test_janela_aberta_sem_som_nao_esta_tocando():
    """O palpite antigo era "tocando", porque a janela está aberta e o usuário
    está assistindo. Medido: o Chrome sem som nenhum saindo e "Batman: Caped
    Crusader" somando um segundo por segundo até 129 minutos no catálogo."""
    atual = da_janela("Prime Video: Batman - Google Chrome", "PRIME_VIDEO", tocando=False)

    assert atual.playing is False


def test_sem_forma_de_medir_o_palpite_continua_otimista():
    """Um controle que diz "pausado" para quem está assistindo é pior do que um
    que conta tempo demais."""
    atual = da_janela("Prime Video: Batman - Google Chrome", "PRIME_VIDEO", tocando=None)

    assert atual.playing is True


def test_tempo_nao_aumenta_sem_evidencia_de_consumo(tmp_path):
    """A regressão do Batman, ponta a ponta no gravador.

    Uma hora inteira de laço com o player tecnicamente em cena mas sem som não
    pode virar um segundo de histórico.
    """
    from app.history.recorder import HistoryRecorder
    from app.history.store import HistoryStore

    store = HistoryStore(tmp_path / "historico.json")
    gravador = HistoryRecorder(store)
    calado = da_janela(
        "Prime Video: Batman: Caped Crusader - Google Chrome",
        "PRIME_VIDEO",
        tocando=False,
    )

    for _ in range(3600):
        gravador.observar(calado, 1.0)
    gravador.encerrar()

    assert store.listar() == []


def test_com_som_o_mesmo_laco_vira_historico(tmp_path):
    """O outro lado da mesma regra: com evidência de consumo, conta.

    Sem este par, "nunca conta nada" passaria no teste de cima.
    """
    from app.history.recorder import HistoryRecorder
    from app.history.store import HistoryStore

    store = HistoryStore(tmp_path / "historico.json")
    gravador = HistoryRecorder(store)
    tocando = da_janela(
        "Prime Video: Batman: Caped Crusader - Google Chrome",
        "PRIME_VIDEO",
        tocando=True,
    )

    for _ in range(300):
        gravador.observar(tocando, 1.0)
    gravador.encerrar()

    assert [item.titulo for item in store.listar()] == ["Batman: Caped Crusader"]


def test_leitura_degradada_de_servico_que_nomeia_episodio_nao_vira_historico(tmp_path):
    """Com a SMTC pendurada e o Max tocando, o que sobra é o nome do EPISÓDIO.

    Medido no histórico real: uma tarde de Rick and Morty virou quatro "títulos
    assistidos" com nome de episódio, um deles ("Campo dos Sonhos") com o pôster
    do filme de 1989 que se chama igual.

    Continua aparecendo no cartão e continua controlável. Só não conta como
    obra assistida.
    """
    from app.history.recorder import HistoryRecorder
    from app.history.store import HistoryStore

    store = HistoryStore(tmp_path / "historico.json")
    gravador = HistoryRecorder(store)
    episodio = da_janela("Campo dos Sonhos • HBO Max - Google Chrome", "MAX", tocando=True)

    for _ in range(300):
        gravador.observar(episodio, 1.0)
    gravador.encerrar()

    assert store.listar() == []
