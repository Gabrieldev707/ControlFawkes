import pytest

from app.media.now_playing import (
    NowPlaying,
    plataforma_no_titulo,
    posicao_extrapolada,
    WindowsNowPlayingReader,
    limpar_titulo_de_janela,
)


# O serviço só era reconhecido pelo aplicativo, e o mapa de aplicativos conhece
# um só — o Spotify. Tudo que toca no navegador ficava sem plataforma, e o
# "mais usado" da tela de perfil soma exatamente o que tem plataforma. Medido no
# histórico real: 3530 dos 3650 segundos gravados não contavam para nada.
@pytest.mark.parametrize(
    ("titulo", "esperado"),
    [
        # A SMTC publica o serviço na frente; a janela, atrás.
        ("Prime Video: Batman: Caped Crusader", "PRIME_VIDEO"),
        ("The Gentlemen - Netflix - Google Chrome", "NETFLIX"),
        ("(2) Magnatas do Crime - Netflix - Google Chrome", "NETFLIX"),
        ("Interestelar | Max - Google Chrome", "MAX"),
        # "hbo max" tem de vencer "max", ou o serviço certo nunca é alcançado.
        ("Alguma Coisa - HBO Max - Google Chrome", "MAX"),
        ("Episódio - Disney+ - Google Chrome", "DISNEY_PLUS"),
        # Sozinho é a página de catálogo — e continua sendo o serviço.
        ("Netflix", "NETFLIX"),
        # Sem serviço nomeado não se inventa um.
        ("Interestelar", None),
        ("Duna - Google Chrome", None),
        (None, None),
        ("", None),
    ],
)
def test_the_service_is_read_from_the_title_when_the_app_does_not_say(titulo, esperado):
    assert plataforma_no_titulo(titulo) == esperado


@pytest.mark.parametrize(
    ("janela", "esperado"),
    [
        ("(2) Duna: Parte Dois - Netflix - Google Chrome", "Duna: Parte Dois"),
        ("Interestelar | Max - Google Chrome", "Interestelar"),
        ("Bohemian Rhapsody - YouTube - Google Chrome", "Bohemian Rhapsody"),
        ("The Boys - Prime Video — Google Chrome", "The Boys"),
        # Página de catálogo: não há conteúdo nomeado, e inventar um seria pior.
        ("Netflix - Google Chrome", "Netflix"),
        ("Netflix", "Netflix"),
        # Nome que contém o separador não pode ser picotado no meio.
        ("Spider-Man: Sem Volta Para Casa - Netflix", "Spider-Man: Sem Volta Para Casa"),
    ],
)
def test_the_window_title_becomes_the_content_name(janela, esperado):
    """O Chrome publica só "Netflix" na SMTC; o nome do conteúdo está na janela.

    Sem esta limpeza o cartão diria "Netflix - Google Chrome" para todo filme.
    """
    assert limpar_titulo_de_janela(janela) == esperado


def test_the_thumbnail_id_changes_only_when_the_cover_changes():
    """O celular só rebaixa a capa quando ela é outra; um id novo a cada
    atualização faria a imagem piscar a cada segundo."""
    base = dict(
        title="Duna", artist=None, app="Chrome", platform=None, playing=True,
        position_seconds=10.0, duration_seconds=100.0,
    )
    primeira = NowPlaying(**base, thumbnail=b"capa-a")
    igual = NowPlaying(**base, thumbnail=b"capa-a")
    outra = NowPlaying(**base, thumbnail=b"capa-b")

    assert primeira.thumbnail_id == igual.thumbnail_id
    assert primeira.thumbnail_id != outra.thumbnail_id


def test_without_a_cover_there_is_no_id():
    sem_capa = NowPlaying(
        title="Duna", artist=None, app="Chrome", platform=None, playing=True,
        position_seconds=None, duration_seconds=None, thumbnail=None,
    )

    assert sem_capa.thumbnail_id is None


@pytest.mark.asyncio
async def test_reading_never_raises_when_the_media_api_is_unavailable(monkeypatch):
    """Sem sessão de mídia o controle inteiro continua funcionando."""
    leitor = WindowsNowPlayingReader()

    async def explode():
        raise RuntimeError("SMTC indisponível")

    monkeypatch.setattr(leitor, "_read_windows", explode)

    assert await leitor.read() is None


@pytest.mark.parametrize(
    ("posicao", "duracao", "idade", "tocando", "esperado"),
    [
        # Tocando: a posição anda com o relógio a partir da medição.
        (100.0, 3600.0, 5.0, True, 105.0),
        # Pausado não anda, por mais antiga que seja a medição.
        (100.0, 3600.0, 90.0, False, 100.0),
        # Sem duração conhecida (rádio, ao vivo) a projeção segue valendo.
        (100.0, None, 5.0, True, 105.0),
        # No limite exato ainda vale.
        (3595.0, 3600.0, 5.0, True, 3600.0),
    ],
)
def test_the_position_advances_from_when_it_was_measured(
    posicao, duracao, idade, tocando, esperado,
):
    """A SMTC guarda a posição e o instante da medição; quem consome projeta."""
    assert posicao_extrapolada(posicao, duracao, idade, tocando) == esperado


def test_a_frozen_timeline_produces_no_bar_instead_of_a_wrong_one():
    """Medido no Chrome: depois de trocar de vídeo ele seguia dizendo
    "tocando" com a posição congelada em minutos atrás. Projetar aquilo daria
    uma barra passando de 100%, e barra errada é pior que barra nenhuma."""
    assert posicao_extrapolada(1376.8, 2633.5, 4000.0, True) is None


def test_a_negative_position_is_discarded():
    assert posicao_extrapolada(-1.0, 100.0, 0.0, True) is None


def test_the_focuser_can_name_the_media_window():
    """Este caminho só é exercitado pelo cartão de "tocando agora", e um erro
    de atributo aqui era engolido pelo `except` largo do leitor: o cartão
    simplesmente sumia, sem nenhum sinal de por quê."""
    from app.windows.focus import DesktopWindow, WindowFocuser

    janelas = [
        DesktopWindow(handle=1, process="code.exe", title="projeto - VS Code"),
        DesktopWindow(handle=2, process="chrome.exe", title="Duna - Netflix - Google Chrome"),
    ]
    focuser = WindowFocuser(window_lister=lambda: janelas)

    assert focuser.media_window_title() == "Duna - Netflix - Google Chrome"


def test_o_editor_de_codigo_nunca_e_um_servico():
    """Medido em 25/08/2026, no `historico.json` real deste computador:

        NETFLIX::netflix problemas de int... - fawkes-control - visual studio code

    A janela do VS Code, com "netflix" no título porque havia um arquivo aberto
    sobre o assunto. O padrão casava em qualquer janela; e como esse título
    PARECE um nome de obra, `media_window` ainda o preferia à aba de verdade —
    o cartão anunciava o editor como o que estava tocando, e o play/pause mirava
    nele.
    """
    from app.windows.focus import DesktopWindow, WindowFocuser, platform_of

    editor = DesktopWindow(
        handle=1,
        process="code.exe",
        title="netflix problemas de int... - Fawkes-Control - Visual Studio Code",
    )
    assert platform_of(editor) is None

    aba = DesktopWindow(handle=2, process="chrome.exe", title="Duna - Netflix")
    focuser = WindowFocuser(window_lister=lambda: [editor, aba])
    assert focuser.media_window("NETFLIX") == aba
    # E o botão mira no mesmo lugar que o cartão mostra.
    assert focuser.find("NETFLIX") == aba


def test_so_o_editor_aberto_nao_inventa_servico_nenhum():
    """O par: sem aba de verdade, a resposta é "nada", e não "o editor"."""
    from app.windows.focus import DesktopWindow, WindowFocuser

    focuser = WindowFocuser(window_lister=lambda: [
        DesktopWindow(handle=1, process="code.exe", title="netflix.md - Visual Studio Code"),
    ])

    assert focuser.media_window("NETFLIX") is None
    assert focuser.find("NETFLIX") is None


def test_processo_desconhecido_nao_e_motivo_para_recusar():
    """A consulta do processo pode falhar por permissão e devolver "".

    Recusar aí calaria uma janela legítima. O que se recusa é o processo
    CONHECIDO que não é navegador — aí não é "não sei", é "não é".
    """
    from app.windows.focus import DesktopWindow, platform_of

    assert platform_of(DesktopWindow(handle=1, process="", title="Duna - Netflix")) == "NETFLIX"


def test_o_spotify_continua_pelo_processo_dele():
    """Regressão proibida do Master Loop: o Spotify não é navegador."""
    from app.windows.focus import DesktopWindow, platform_of

    janela = DesktopWindow(handle=1, process="spotify.exe", title="Artista - Música")
    assert platform_of(janela) == "SPOTIFY"


def test_sem_winsdk_a_janela_ainda_socorre(monkeypatch):
    """A SMTC AUSENTE é o mesmo caso da SMTC pendurada, e o código só conhecia um.

    Medido em 25/08/2026: o servidor subiu pelo Python do sistema, sem `winsdk`
    instalado. `read()` devolvia None na hora — o ImportError é engolido de
    propósito — então a chamada nunca chegava a pendurar e `travada` ficava
    False. O socorro pela janela exigia `travada`, não entrava, e o resultado
    era "nada tocando" para sempre: nenhum cartão, nenhum histórico, nenhum
    erro. Três reinícios não mudaram nada, porque não era o servidor.
    """
    import asyncio
    from unittest.mock import AsyncMock

    from app.protocol import dispatcher as modulo
    from app.protocol.dispatcher import Dispatcher
    from app.windows.focus import DesktopWindow, WindowFocuser

    # Esta máquina TEM `winsdk` no venv; o caso a reproduzir é o de quem não tem.
    monkeypatch.setattr(modulo, "smtc_disponivel", lambda: False)

    janelas = [DesktopWindow(
        handle=1, process="chrome.exe",
        title="Duna - Netflix - Google Chrome",
    )]
    dispatcher = Dispatcher(window_focuser=WindowFocuser(window_lister=lambda: janelas))
    # A SMTC não respondeu e NÃO está pendurada: ela simplesmente não existe.
    dispatcher._leitura = AsyncMock()
    dispatcher._leitura.ler = AsyncMock(return_value=None)
    dispatcher._leitura.travada = False

    mensagem = asyncio.run(dispatcher._read_now_playing())

    # Fora do Windows (e num Windows sem `winsdk`) o socorro tem de entrar.
    assert mensagem["session"] is not None
    assert mensagem["session"]["title"] == "Duna"
    assert mensagem["session"]["platform"] == "NETFLIX"


def test_no_media_window_is_a_clean_none():
    from app.windows.focus import DesktopWindow, WindowFocuser

    focuser = WindowFocuser(
        window_lister=lambda: [DesktopWindow(handle=1, process="code.exe", title="VS Code")],
    )

    assert focuser.media_window_title() is None


def test_a_moving_timeline_is_trusted():
    from app.media.now_playing import RelogioDaMidia

    relogio = RelogioDaMidia()

    assert relogio.confiavel(10.0, tocando=True, agora=0.0) is True
    assert relogio.confiavel(11.0, tocando=True, agora=1.0) is True
    assert relogio.confiavel(12.0, tocando=True, agora=2.0) is True


def test_a_frozen_timeline_stops_being_trusted():
    """Medido no Chrome: ele agrega as abas numa sessão só e seguia publicando
    a linha do tempo de um filme fechado minutos antes, enquanto o título já
    era de outro vídeo. A posição projetada cabia na duração e parecia
    plausível — a barra andava mostrando um lugar que não existe."""
    from app.media.now_playing import RelogioDaMidia

    relogio = RelogioDaMidia()
    relogio.confiavel(1376.8, tocando=True, agora=0.0)

    # A posição bruta do Chrome dá saltos a cada poucos segundos; ficar
    # parada nesse intervalo é normal e não pode apagar a barra.
    assert relogio.confiavel(1376.8, tocando=True, agora=4.0) is True
    # Parada por muito mais que isso é congelamento de verdade.
    assert relogio.confiavel(1376.8, tocando=True, agora=30.0) is False


def test_a_paused_timeline_is_supposed_to_stand_still():
    from app.media.now_playing import RelogioDaMidia

    relogio = RelogioDaMidia()
    relogio.confiavel(50.0, tocando=True, agora=0.0)

    assert relogio.confiavel(50.0, tocando=False, agora=60.0) is True


def test_the_timeline_is_trusted_again_after_it_starts_moving():
    """Sair do congelamento não pode exigir reiniciar o servidor."""
    from app.media.now_playing import RelogioDaMidia

    relogio = RelogioDaMidia()
    relogio.confiavel(100.0, tocando=True, agora=0.0)
    assert relogio.confiavel(100.0, tocando=True, agora=30.0) is False

    assert relogio.confiavel(101.0, tocando=True, agora=31.0) is True


def test_a_frozen_timeline_under_the_same_title_only_stopped():
    """Travar não é o mesmo que mentir, e tratar os dois igual custava a
    minutagem de quem estava assistindo direito.

    Medido: um serviço que simplesmente demora a publicar o próximo valor
    deixava a posição parada por mais de doze segundos, e o cartão perdia a
    minutagem INTEIRA no meio do filme — não a barra, o bloco todo. O número
    velho era desta reprodução; velho não é errado.
    """
    from app.media.now_playing import RelogioDaMidia

    relogio = RelogioDaMidia()
    relogio.avaliar(600.0, tocando=True, agora=0.0, titulo="A Casa do Dragão")

    assert relogio.avaliar(
        600.0, tocando=True, agora=30.0, titulo="A Casa do Dragão",
    ) == "PARADA"


def test_a_frozen_timeline_under_a_new_title_belongs_to_the_old_one():
    """O caso que a desconfiança existe para pegar: a sessão do Chrome ficou
    para trás e o número publicado é da reprodução ANTERIOR.

    O título é o que separa os dois: se ele mudou depois que a posição travou,
    aquele número não descreve o que está tocando agora.
    """
    from app.media.now_playing import RelogioDaMidia

    relogio = RelogioDaMidia()
    relogio.avaliar(1376.8, tocando=True, agora=0.0, titulo="Duna")

    assert relogio.avaliar(
        1376.8, tocando=True, agora=30.0, titulo="Rick and Morty",
    ) == "SUSPEITA"


def test_a_stopped_position_is_never_projected_forward():
    """A posição parada vai como está, sem projeção.

    Projetar aqui inventaria um avanço que ninguém mediu — que é justamente o
    defeito que fez a barra passar de 100% e sumir.
    """
    from datetime import timedelta

    from app.media.now_playing import _linha_do_tempo, RelogioDaMidia

    class Linha:
        # A SMTC devolve durações do WinRT; o que o código usa delas é
        # `total_seconds()`, que o `timedelta` tem igual.
        position = timedelta(seconds=600)
        end_time = timedelta(seconds=3600)
        last_updated_time = None

    class Sessao:
        def get_timeline_properties(self):
            return Linha()

    relogio = RelogioDaMidia()
    relogio.avaliar(600.0, tocando=True, agora=0.0, titulo="Duna")
    # Empurra o relógio para além do limite de desconfiança, mesmo título.
    relogio._vista_em = -3600.0

    posicao, duracao, parada = _linha_do_tempo(
        Sessao(), tocando=True, relogio=relogio, titulo="Duna",
    )

    assert parada is True
    assert posicao == 600.0
    assert duracao == 3600.0


@pytest.mark.asyncio
async def test_a_slow_read_never_blocks_the_next_round():
    """Passar a vez em vez de esperar: o laço precisa seguir solto para o
    batimento continuar saindo mesmo com a leitura de mídia lenta."""
    import asyncio

    from app.media.now_playing import LeituraEmVoo

    liberar = asyncio.Event()

    class LeitorLento:
        async def read(self):
            await liberar.wait()
            return "pronto"

    leitura = LeituraEmVoo(LeitorLento())

    assert await leitura.ler() is None      # dispara e ainda não terminou
    assert await leitura.ler() is None      # segue em voo, sem travar

    liberar.set()
    await asyncio.sleep(0)
    assert await leitura.ler() == "pronto"


@pytest.mark.asyncio
async def test_the_read_is_never_cancelled():
    """Cancelar uma operação assíncrona do WinRT no meio a deixa tentando
    concluir numa future morta — medido, com `InvalidStateError` no log e o
    laço de atualização morrendo logo depois."""
    import asyncio

    from app.media.now_playing import LeituraEmVoo

    cancelada = False

    class LeitorObservado:
        async def read(self):
            nonlocal cancelada
            try:
                await asyncio.sleep(0.05)
            except asyncio.CancelledError:
                cancelada = True
                raise
            return "pronto"

    leitura = LeituraEmVoo(LeitorObservado())
    await leitura.ler()
    await leitura.ler()
    await asyncio.sleep(0.1)
    await leitura.ler()

    assert cancelada is False


@pytest.mark.asyncio
async def test_a_failed_read_becomes_nothing_playing():
    from app.media.now_playing import LeituraEmVoo

    class LeitorQuebrado:
        async def read(self):
            raise RuntimeError("SMTC caiu")

    leitura = LeituraEmVoo(LeitorQuebrado())
    await leitura.ler()
    import asyncio
    await asyncio.sleep(0)

    assert await leitura.ler() is None


@pytest.mark.asyncio
async def test_a_hung_read_is_eventually_given_up_on():
    """Medido com o Disney+ tocando: `request_async()` da SMTC ficou pendurado
    por minutos. Como a chamada não pode ser cancelada sem corromper o WinRT,
    o que resta é parar de esperar por ela."""
    import asyncio

    from app.media.now_playing import LeituraEmVoo

    class LeitorPendurado:
        async def read(self):
            await asyncio.Event().wait()

    leitura = LeituraEmVoo(LeitorPendurado())
    leitura.SEGUNDOS_ATE_DESISTIR = 0.05

    await leitura.ler()
    assert leitura.travada is False

    await asyncio.sleep(0.1)
    await leitura.ler()
    assert leitura.travada is True


def test_the_window_alone_keeps_the_controls_alive():
    """Sem a SMTC não há posição nem pausa — mas há o que está na tela. Dizer
    "nada tocando" desligaria os controles de reprodução junto, que é como o
    controle inteiro parecia quebrado com o Disney+."""
    from app.media.now_playing import da_janela

    atual = da_janela("O Justiceiro | Disney+ - Google Chrome", "DISNEY_PLUS")

    assert atual is not None
    assert atual.title == "O Justiceiro"
    assert atual.platform == "DISNEY_PLUS"
    # O que a janela não sabe fica vazio em vez de inventado.
    assert atual.position_seconds is None
    assert atual.duration_seconds is None


def test_no_media_window_stays_no_media():
    from app.media.now_playing import da_janela

    assert da_janela(None, None) is None
    assert da_janela("", None) is None


def test_a_web_address_is_never_the_name_of_a_work():
    """Enquanto a página não define o título, e sempre que ninguém está logado,
    o Chrome mostra o domínio. Medido com o Max aberto: "play.hbomax.com"
    entraria no histórico como um filme assistido."""
    from app.media.now_playing import _titulo_generico

    assert _titulo_generico("play.hbomax.com", None, "MAX") is True
    assert _titulo_generico("www.primevideo.com", None, "PRIME_VIDEO") is True
    # E um título de verdade com ponto continua passando.
    assert _titulo_generico("Batman: Caped Crusader", None, "PRIME_VIDEO") is False
    assert _titulo_generico("S.W.A.T.", None, "NETFLIX") is False


def test_the_app_is_recognized_by_its_package_identifier():
    """A SMTC não devolve "Spotify": devolve o identificador do pacote. Medido
    nesta máquina, "SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify" — e a
    comparação exata deixava sem serviço tudo que tocava no Spotify da Loja."""
    from app.media.now_playing import _plataforma_do_app

    assert _plataforma_do_app("SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify") == "SPOTIFY"
    # A versão que se identifica pelo nome puro continua valendo.
    assert _plataforma_do_app("Spotify") == "SPOTIFY"
    assert _plataforma_do_app("chrome.exe") is None
    assert _plataforma_do_app(None) is None


def test_the_home_page_of_a_service_is_not_a_work():
    """Medido com o Prime Video aberto sem nada tocando: a janela diz "Prime
    Video: Watch movies, TV shows, sports, and live TV", a limpeza tira só o
    prefixo, e a frase de marketing que sobra entrava no histórico como um
    filme assistido — com direito a procurar capa no catálogo."""
    from app.media.now_playing import _titulo_generico

    nome = limpar_titulo_de_janela(
        "Prime Video: Watch movies, TV shows, sports, and live TV - Google Chrome",
    )

    assert nome == "Watch movies, TV shows, sports, and live TV"
    assert _titulo_generico(nome, None, "PRIME_VIDEO") is True
    # E um filme de verdade no mesmo serviço continua passando.
    assert _titulo_generico("Batman: Caped Crusader", None, "PRIME_VIDEO") is False


@pytest.mark.asyncio
async def test_the_smtc_gets_another_chance_after_it_hangs():
    """Uma leitura pendurada desligava a SMTC até alguém reiniciar o servidor.

    Medido nesta máquina: a SMTC parou de responder, o leitor desistiu — como
    deve — e nunca mais tentou. Dali em diante o cartão vinha só do título da
    janela, e com ele foram embora a capa, a duração, a posição e o nome da
    série. O usuário viu um aplicativo quebrado; o log não tinha nada.

    A trava é do serviço do Windows e passa sozinha. O que não passava era o
    aplicativo desistir para sempre da primeira vez.
    """
    import asyncio

    from app.media.now_playing import LeituraEmVoo

    responde = False

    class LeitorQueVolta:
        def __init__(self):
            self.tentativas = 0

        async def read(self):
            self.tentativas += 1
            if not responde:
                await asyncio.Event().wait()
            return "voltou"

    leitor = LeitorQueVolta()
    leitura = LeituraEmVoo(leitor)
    leitura.SEGUNDOS_ATE_DESISTIR = 0.05
    leitura.SEGUNDOS_ENTRE_TENTATIVAS = 0.05

    await leitura.ler()
    await asyncio.sleep(0.1)
    await leitura.ler()          # desiste da primeira
    assert leitura.travada is True

    responde = True
    await asyncio.sleep(0.1)
    await leitura.ler()          # pede outra
    await asyncio.sleep(0)

    assert leitor.tentativas == 2
    assert await leitura.ler() == "voltou"
    assert leitura.travada is False


@pytest.mark.asyncio
async def test_a_second_hang_is_given_up_on_too():
    """A tentativa nova pode pendurar igual. Uma condição que só perguntasse
    "já abandonei alguma?" deixaria essa pendurada para sempre — o mesmo defeito
    de antes, uma tentativa depois."""
    import asyncio

    from app.media.now_playing import LeituraEmVoo

    class LeitorSemprePendurado:
        def __init__(self):
            self.tentativas = 0

        async def read(self):
            self.tentativas += 1
            await asyncio.Event().wait()

    leitor = LeitorSemprePendurado()
    leitura = LeituraEmVoo(leitor)
    leitura.SEGUNDOS_ATE_DESISTIR = 0.05
    leitura.SEGUNDOS_ENTRE_TENTATIVAS = 0.05

    for _ in range(4):
        await leitura.ler()
        await asyncio.sleep(0.06)

    assert leitor.tentativas >= 2
    assert leitura.travada is True


def test_the_window_alone_is_not_trustworthy_enough_to_be_a_work():
    """Numa série, o título da janela é o do EPISÓDIO. Medido no histórico
    real: uma tarde de Rick and Morty com a SMTC pendurada virou quatro
    "títulos assistidos" com nome de episódio."""
    from app.media.now_playing import da_janela

    atual = da_janela("Campo dos Sonhos • HBO Max - Google Chrome", "MAX")

    assert atual is not None
    assert atual.title == "Campo dos Sonhos"
    # Mostrável, sim; afirmável como obra, não.
    assert atual.trustworthy is False


def test_the_smtc_names_the_series_and_the_window_names_the_episode():
    """Medido com A Casa do Dragão no Max: a SMTC publica "A Casa do Dragão" e
    a janela, "The Treasons at Tumbleton". Cada fonte sabe uma metade, e o
    código usava uma de cada vez — então a outra metade era jogada fora."""
    from app.media.now_playing import episodio_da_janela

    assert episodio_da_janela(
        "A Casa do Dragão", "The Treasons at Tumbleton", None, "MAX",
    ) == "The Treasons at Tumbleton"


@pytest.mark.parametrize(
    ("obra", "janela"),
    [
        # Filme: as duas fontes dizem a mesma coisa, e não há episódio.
        ("Duna: Parte Dois", "Duna: Parte Dois"),
        ("Interestelar", "interestelar"),
        # A janela no catálogo do serviço não nomeia episódio nenhum.
        ("Rick and Morty", "Home"),
        ("Rick and Morty", "Netflix"),
        ("Rick and Morty", "play.hbomax.com"),
        # A série repetida com enfeite não é o nome de um episódio.
        ("A Casa do Dragão", "A Casa do Dragão - T2"),
        # Sem uma das duas pontas não há o que comparar.
        ("", "Campo dos Sonhos"),
        ("Rick and Morty", ""),
    ],
)
def test_what_is_not_an_episode_does_not_become_one(obra, janela):
    from app.media.now_playing import episodio_da_janela

    assert episodio_da_janela(obra, janela, None, "MAX") is None


def test_the_media_window_is_the_one_naming_something():
    """Medido com três abas de serviço abertas — Max no Chrome, Netflix no Edge,
    Netflix no Chrome: "a primeira que aparecer" devolvia a home da Netflix, e o
    cartão ficava mudo enquanto o Max tocava logo ali do lado."""
    from app.windows.focus import DesktopWindow, WindowFocuser

    janelas = [
        DesktopWindow(handle=1, process="msedge.exe", title="Home - Netflix"),
        DesktopWindow(handle=2, process="chrome.exe", title="Netflix - Google Chrome"),
        DesktopWindow(handle=3, process="chrome.exe", title="Família Soprano • HBO Max"),
    ]
    focuser = WindowFocuser(window_lister=lambda: janelas)

    assert focuser.media_window_title() == "Família Soprano • HBO Max"


def test_find_and_the_card_choose_the_same_window():
    """O botão e o cartão têm de falar da MESMA janela.

    Medido pelo usuário em 25/08/2026: "botões em determinado streaming
    funciona e depois não funciona mais". Não era intermitência — eram dois
    seletores. `find` pegava a primeira da ordem do `EnumWindows` (que é a
    ordem Z) e `media_window` pegava a que nomeia alguma coisa. Bastava algo
    ganhar o foco para os dois discordarem, e o `SPACE` do play/pause ia para a
    aba de catálogo enquanto o cartão mostrava o episódio da outra.
    """
    from app.windows.focus import DesktopWindow, WindowFocuser

    janelas = [
        DesktopWindow(handle=1, process="chrome.exe", title="Home - Netflix"),
        DesktopWindow(handle=2, process="chrome.exe", title="Duna - Netflix"),
    ]
    focuser = WindowFocuser(window_lister=lambda: janelas)

    assert focuser.find("NETFLIX") == focuser.media_window("NETFLIX")
    assert focuser.find("NETFLIX").title == "Duna - Netflix"


def test_the_window_choice_survives_the_z_order_changing():
    """A ordem do `EnumWindows` muda quando algo ganha o foco; a escolha não.

    É o mecanismo exato do "funciona e depois para": apertar tela cheia foca
    uma janela, a ordem vira, e o comando seguinte mudava de alvo sozinho.
    """
    from app.windows.focus import DesktopWindow, WindowFocuser

    catalogo = DesktopWindow(handle=1, process="chrome.exe", title="Home - Netflix")
    tocando = DesktopWindow(handle=2, process="chrome.exe", title="Duna - Netflix")

    antes = WindowFocuser(window_lister=lambda: [catalogo, tocando])
    depois = WindowFocuser(window_lister=lambda: [tocando, catalogo])

    assert antes.find("NETFLIX") == depois.find("NETFLIX") == tocando


def test_the_control_page_is_never_the_target():
    """A página do controle aberta no computador não pode virar alvo.

    `find` já a excluía; `media_window` não. Agora que os dois são o mesmo
    seletor, a exclusão vale para os dois — senão unificar teria dado à
    `media_window` uma candidata que ela nunca teve.
    """
    from app.windows.focus import DesktopWindow, WindowFocuser

    janelas = [
        DesktopWindow(handle=1, process="chrome.exe", title="Control Fawkes - Netflix"),
        DesktopWindow(handle=2, process="chrome.exe", title="Duna - Netflix"),
    ]
    focuser = WindowFocuser(window_lister=lambda: janelas)

    assert focuser.find("NETFLIX").title == "Duna - Netflix"
    assert focuser.media_window("NETFLIX").title == "Duna - Netflix"


def test_the_media_window_can_be_asked_for_one_service():
    """Quem já sabe pela SMTC quem está tocando não pode receber o nome da aba
    de outro serviço — era assim que "Família Soprano" aparecia como episódio de
    uma série que estava em outro lugar."""
    from app.windows.focus import DesktopWindow, WindowFocuser

    janelas = [
        DesktopWindow(handle=1, process="chrome.exe", title="Família Soprano • HBO Max"),
        DesktopWindow(handle=2, process="msedge.exe", title="Campo dos Sonhos - Netflix"),
    ]
    focuser = WindowFocuser(window_lister=lambda: janelas)

    assert focuser.media_window_title("NETFLIX") == "Campo dos Sonhos - Netflix"
    assert focuser.media_window_title("MAX") == "Família Soprano • HBO Max"
    assert focuser.media_window_title("DISNEY_PLUS") is None


@pytest.mark.parametrize(
    ("janela", "esperado"),
    [
        # Medido com o Chrome pendurado tocando um episódio.
        ("46 Long • HBO Max - Google Chrome (Não está respondendo)", "46 Long"),
        ("Duna - Netflix - Google Chrome (Not Responding)", "Duna"),
        # Um parêntese que faz parte do nome não pode ser confundido com a marca.
        ("Duna (2021) - Netflix - Google Chrome", "Duna (2021)"),
        ("Duna (2021)", "Duna (2021)"),
    ],
)
def test_the_not_responding_mark_is_not_part_of_the_name(janela, esperado):
    """O Windows cola "(Não está respondendo)" no fim do título. Com ele lá, o
    sufixo do navegador deixa de ser o fim do texto e nada mais é reconhecido —
    a frase inteira, marca inclusive, virava o título no cartão do celular."""
    assert limpar_titulo_de_janela(janela) == esperado


def test_the_service_is_still_read_from_a_hung_window():
    """E o serviço também: sem tirar a marca, "… - Google Chrome (Não está
    respondendo)" não terminava em nome de serviço nenhum."""
    assert plataforma_no_titulo(
        "46 Long • HBO Max - Google Chrome (Não está respondendo)",
    ) == "MAX"


@pytest.mark.asyncio
async def test_abandoning_a_cancelled_read_stays_quiet():
    """`Task.exception()` RELANÇA o CancelledError de uma tarefa cancelada, e o
    log enchia de "Exception in callback" vindo do abandono."""
    import asyncio

    from app.media.now_playing import _engolir_o_resultado

    async def pendurada():
        await asyncio.Event().wait()

    tarefa = asyncio.ensure_future(pendurada())
    await asyncio.sleep(0)
    tarefa.cancel()
    try:
        await tarefa
    except asyncio.CancelledError:
        pass

    _engolir_o_resultado(tarefa)  # não pode levantar


@pytest.mark.parametrize(
    ("janela", "esperado"),
    [
        # Serviço instalado como aplicativo: o nome vem na frente E atrás.
        ("Netflix - Home - Netflix", "Home"),
        ("Netflix - Netflix", "Netflix"),
        ("Max • Início • HBO Max", "Início"),
        # E o que já funcionava não pode mudar.
        ("Prime Video: Batman: Caped Crusader - Google Chrome", "Batman: Caped Crusader"),
        ("Duna: Parte Dois - Netflix - Google Chrome", "Duna: Parte Dois"),
    ],
)
def test_the_service_name_in_front_is_not_the_content(janela, esperado):
    """Medido com a Netflix instalada: a janela diz "Netflix - Home - Netflix".
    Cortando só o sufixo sobra "Netflix - Home", que não bate com página
    conhecida nenhuma e passava por obra — e essa janela GANHAVA da janela do
    Prime Video na escolha de quem está tocando. O cartão anunciava
    "Netflix - Home" enquanto o usuário assistia Batman no Prime Video."""
    assert limpar_titulo_de_janela(janela) == esperado


def test_the_app_home_page_loses_to_a_window_naming_content():
    """O caso inteiro, de ponta a ponta: com a Netflix instalada parada na home
    e o Prime Video tocando, quem tem de ser escolhido é o Prime Video."""
    from app.windows.focus import DesktopWindow, WindowFocuser

    janelas = [
        DesktopWindow(handle=1, process="msedge.exe", title="Netflix - Home - Netflix"),
        DesktopWindow(
            handle=2, process="chrome.exe",
            title="Prime Video: Batman: Caped Crusader - Google Chrome",
        ),
    ]
    focuser = WindowFocuser(window_lister=lambda: janelas)

    janela = focuser.media_window()
    assert janela is not None
    assert janela.handle == 2


@pytest.mark.parametrize(
    ("janela", "plataforma", "titulo", "conta"),
    [
        # O título da janela É a obra: conta.
        ("Prime Video: Batman: Caped Crusader - Google Chrome", "PRIME_VIDEO",
         "Batman: Caped Crusader", True),
        ("CHEGUEI NA SÍRIA - YouTube - Google Chrome", "YOUTUBE",
         "CHEGUEI NA SÍRIA", True),
        # Medido com a série tocando: o Disney+ põe o nome da SÉRIE na janela,
        # não o do episódio. E é com ele que a SMTC pendura, então esta é a
        # única leitura que sobra — fora da lista, uma série inteira assistida
        # no Disney+ não entrava no histórico.
        ("O Justiceiro | Disney+ - Google Chrome", "DISNEY_PLUS",
         "O Justiceiro", True),
        # O título da janela é o EPISÓDIO: não conta.
        ("46 Long • HBO Max - Google Chrome", "MAX", "46 Long", False),
        # Sem serviço reconhecido não dá para saber qual dos dois casos é.
        ("Alguma Coisa", None, "Alguma Coisa", False),
    ],
)
def test_whether_the_window_name_counts_depends_on_the_service(
    janela, plataforma, titulo, conta,
):
    """Cada serviço nomeia a janela do jeito dele, e tratar todos igual custou
    os dois lados: com tudo confiável, Rick and Morty virou quatro títulos com
    nome de episódio; com nada confiável, uma hora de Batman no Prime Video não
    contou nada e o cartão ficou sem pôster."""
    from app.media.now_playing import da_janela

    atual = da_janela(janela, plataforma)

    assert atual is not None
    assert atual.title == titulo
    assert atual.trustworthy is conta
