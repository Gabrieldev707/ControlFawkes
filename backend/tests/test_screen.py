"""Tocar na foto da tela, e os perfis guardados a partir dela."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api import websocket as websocket_module
from app.main import app
from app.profiles.store import MAXIMO_POR_PLATAFORMA, ProfileStore
from app.windows.focus import DesktopWindow, WindowFocuser
from app.windows.screen import (
    Quadro,
    Retangulo,
    WindowCapture,
    _recorte_do_avatar,
    ponto_na_tela,
)


# ── A conta que traduz dedo em pixel ──────────────────────────────────────

JANELA = Retangulo(esquerda=1536, topo=0, largura=1280, altura=720)


def test_the_corners_of_the_photo_are_the_corners_of_the_window():
    assert ponto_na_tela(JANELA, 0.0, 0.0) == (1536, 0)
    assert ponto_na_tela(JANELA, 0.5, 0.5) == (2176, 360)
    # O extremo cai no último pixel de dentro. Um a mais seria a janela vizinha
    # — e nesta máquina a janela realmente está encostada na borda do monitor.
    assert ponto_na_tela(JANELA, 1.0, 1.0) == (2815, 719)


def test_a_tap_outside_the_photo_is_pinned_to_the_edge():
    """Arredondamento de dedo não pode virar clique fora da janela."""
    assert ponto_na_tela(JANELA, -0.4, 2.0) == (1536, 719)


def test_the_window_can_move_between_monitors_without_breaking_the_profile():
    """A fração é o que sobrevive: foi medindo isto que a janela mudou de lugar."""
    antes = Retangulo(0, 0, 1920, 1080)
    depois = Retangulo(1536, 120, 1280, 720)

    assert ponto_na_tela(antes, 0.25, 0.5) == (480, 540)
    assert ponto_na_tela(depois, 0.25, 0.5) == (1856, 480)


def test_the_avatar_crop_stays_inside_the_image():
    """Perfil colado no canto não pode gerar recorte com coordenada negativa."""
    for x, y in ((0.0, 0.0), (1.0, 1.0), (0.5, 0.5)):
        esquerda, topo, direita, baixo = _recorte_do_avatar(1280, 720, x, y)
        assert 0 <= esquerda < direita <= 1280
        assert 0 <= topo < baixo <= 720


# ── O que fica guardado ───────────────────────────────────────────────────


@pytest.fixture
def store(tmp_path: Path) -> ProfileStore:
    return ProfileStore(tmp_path / "perfis.json")


def test_profiles_are_kept_per_platform(store: ProfileStore):
    store.adicionar("NETFLIX", "Gabriel", 0.3, 0.45, None)
    store.adicionar("DISNEY_PLUS", "Infantil", 0.7, 0.5, None)

    assert [p.nome for p in store.listar("NETFLIX")] == ["Gabriel"]
    assert [p.nome for p in store.listar("DISNEY_PLUS")] == ["Infantil"]
    assert store.listar("MAX") == []


def test_a_profile_survives_a_restart(tmp_path: Path):
    caminho = tmp_path / "perfis.json"
    criado = ProfileStore(caminho).adicionar("NETFLIX", "Gabriel", 0.3, 0.45, b"\xff\xd8jpeg")

    relido = ProfileStore(caminho).buscar("NETFLIX", criado.id)

    assert relido.nome == "Gabriel"
    assert relido.x == 0.3
    assert relido.avatar == b"\xff\xd8jpeg"


def test_a_corrupted_file_means_no_profiles_not_a_crash(tmp_path: Path):
    caminho = tmp_path / "perfis.json"
    caminho.write_text("{isto não é json", encoding="utf-8")

    assert ProfileStore(caminho).listar("NETFLIX") == []


def test_the_name_is_trimmed_and_the_empty_one_is_refused(store: ProfileStore):
    assert store.adicionar("NETFLIX", "  Gabriel  ", 0.3, 0.4, None).nome == "Gabriel"
    assert store.adicionar("NETFLIX", "   ", 0.3, 0.4, None) is None


def test_there_is_a_ceiling_per_platform(store: ProfileStore):
    for indice in range(MAXIMO_POR_PLATAFORMA):
        assert store.adicionar("NETFLIX", f"Perfil {indice}", 0.1, 0.1, None) is not None

    assert store.adicionar("NETFLIX", "Um a mais", 0.1, 0.1, None) is None


def test_removing_the_last_profile_leaves_no_empty_platform_behind(store: ProfileStore):
    perfil = store.adicionar("NETFLIX", "Gabriel", 0.3, 0.4, None)

    assert store.remover("NETFLIX", perfil.id) is True
    assert store.tudo() == {}
    assert store.remover("NETFLIX", perfil.id) is False


def test_the_avatar_never_reaches_the_phone_inside_the_listing(store: ProfileStore):
    """A imagem tem endereço próprio: no JSON ela só viraria peso."""
    perfil = store.adicionar("NETFLIX", "Gabriel", 0.3, 0.4, b"\xff\xd8jpeg")

    assert perfil.sem_avatar() == {"id": perfil.id, "nome": "Gabriel", "temAvatar": True}


# ── A porta HTTP ──────────────────────────────────────────────────────────


JANELA_NETFLIX = DesktopWindow(handle=42, process="chrome.exe", title="Netflix - Google Chrome")


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    """O app com uma janela de mentira e uma captura de mentira.

    Sem isto o teste dependeria do que estiver aberto na máquina — e a captura
    de verdade só existe no Windows.
    """
    from app.protocol.dispatcher import Dispatcher
    from app.security.device_store import DeviceStore
    from app.security.pairing import PairingService

    focuser = Mock(spec=WindowFocuser)
    focuser.find.return_value = JANELA_NETFLIX
    focuser.focus.return_value = True

    captura = Mock(spec=WindowCapture)
    captura.retangulo.return_value = JANELA
    captura.capturar.return_value = Quadro(b"\xff\xd8jpeg-do-quadro", 960, 540)
    captura.recortar_avatar.return_value = b"\xff\xd8jpeg-do-avatar"

    store = DeviceStore(
        filepath=tmp_path / "paired_devices.json",
        lockpath=tmp_path / "paired_devices.lock",
    )
    dispatcher = Dispatcher(
        device_store=store,
        pairing_service=PairingService(store),
        window_focuser=focuser,
        window_capture=captura,
        profile_store=ProfileStore(tmp_path / "perfis.json"),
    )
    monkeypatch.setattr(websocket_module, "dispatcher", dispatcher)

    with TestClient(app) as cliente:
        cliente.dispatcher = dispatcher
        cliente.focuser = focuser
        cliente.captura = captura
        yield cliente


def credenciais(cliente) -> dict[str, str]:
    servico = cliente.dispatcher.pairing_service
    resultado = servico.attempt(servico.initialize(), "Celular")
    assert resultado.success
    return {"X-Device-Id": resultado.device_id, "X-Device-Token": resultado.token}


def test_the_frame_needs_authentication(cliente):
    assert cliente.get("/screen/frame/NETFLIX").status_code == 401


def test_the_frame_comes_back_as_a_photo(cliente):
    resposta = cliente.get("/screen/frame/NETFLIX", headers=credenciais(cliente))

    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "image/jpeg"
    assert resposta.content == b"\xff\xd8jpeg-do-quadro"
    # Guardar o quadro seria mostrar o passado na próxima vez.
    assert resposta.headers["cache-control"] == "no-store"


def test_a_closed_platform_says_so_instead_of_failing(cliente):
    cliente.focuser.find.return_value = None

    resposta = cliente.get("/screen/frame/MAX", headers=credenciais(cliente))

    assert resposta.status_code == 404


def test_a_platform_that_does_not_exist_is_refused(cliente):
    assert cliente.get("/screen/frame/PIRATE_TV", headers=credenciais(cliente)).status_code == 422


def test_registering_a_profile_crops_the_avatar_from_the_window(cliente):
    cabecalhos = credenciais(cliente)

    criado = cliente.post(
        "/screen/profiles",
        json={"platform": "NETFLIX", "nome": "Gabriel", "x": 0.32, "y": 0.45},
        headers=cabecalhos,
    )

    assert criado.status_code == 201
    assert criado.json()["profile"]["temAvatar"] is True
    cliente.captura.recortar_avatar.assert_called_once_with(JANELA_NETFLIX, 0.32, 0.45)

    identificador = criado.json()["profile"]["id"]
    avatar = cliente.get(
        f"/screen/profiles/NETFLIX/{identificador}/avatar", headers=cabecalhos,
    )
    assert avatar.status_code == 200
    assert avatar.content == b"\xff\xd8jpeg-do-avatar"


def test_a_profile_is_still_saved_when_the_window_is_closed(cliente):
    """Sem janela não há recorte, mas a posição é o que faz o clique funcionar."""
    cliente.focuser.find.return_value = None
    cabecalhos = credenciais(cliente)

    criado = cliente.post(
        "/screen/profiles",
        json={"platform": "NETFLIX", "nome": "Gabriel", "x": 0.32, "y": 0.45},
        headers=cabecalhos,
    )

    assert criado.status_code == 201
    assert criado.json()["profile"]["temAvatar"] is False


def test_the_listing_groups_by_platform(cliente):
    cabecalhos = credenciais(cliente)
    for plataforma, nome in (("NETFLIX", "Gabriel"), ("NETFLIX", "Visitante"), ("MAX", "Casa")):
        cliente.post(
            "/screen/profiles",
            json={"platform": plataforma, "nome": nome, "x": 0.3, "y": 0.4},
            headers=cabecalhos,
        )

    listagem = cliente.get("/screen/profiles", headers=cabecalhos).json()["platforms"]

    assert [p["nome"] for p in listagem["NETFLIX"]] == ["Gabriel", "Visitante"]
    assert [p["nome"] for p in listagem["MAX"]] == ["Casa"]


def test_a_profile_can_be_removed(cliente):
    cabecalhos = credenciais(cliente)
    criado = cliente.post(
        "/screen/profiles",
        json={"platform": "NETFLIX", "nome": "Gabriel", "x": 0.3, "y": 0.4},
        headers=cabecalhos,
    ).json()["profile"]

    apagado = cliente.delete(f"/screen/profiles/NETFLIX/{criado['id']}", headers=cabecalhos)

    assert apagado.status_code == 200
    assert cliente.get("/screen/profiles", headers=cabecalhos).json()["platforms"] == {}


# ── Reconhecer de quem é a janela ─────────────────────────────────────────


@pytest.mark.parametrize(
    ("titulo", "esperado"),
    [
        # O domínio cru é o que o Chrome mostra enquanto a página não define o
        # título — e, sem login, ela nunca define. Medido com as quatro abertas
        # ao mesmo tempo: só o Max não era reconhecido, porque "max" vem colado
        # em "hbo" e não sobra fronteira de palavra.
        ("play.hbomax.com - Google Chrome", "MAX"),
        ("www.max.com - Google Chrome", "MAX"),
        ("www.primevideo.com - Google Chrome", "PRIME_VIDEO"),
        ("www.disneyplus.com - Google Chrome", "DISNEY_PLUS"),
        ("www.netflix.com - Google Chrome", "NETFLIX"),
        ("www.youtube.com - Google Chrome", "YOUTUBE"),
        # E os títulos já carregados seguem valendo.
        ("Interestelar | Max - Google Chrome", "MAX"),
        ("Prime Video: Batman - Google Chrome", "PRIME_VIDEO"),
        ("Para Você | Disney+ - Google Chrome", "DISNEY_PLUS"),
        ("Netflix - Google Chrome", "NETFLIX"),
        # Sem serviço nenhum não se inventa um.
        ("Fawkes-Control - Visual Studio Code", None),
    ],
)
def test_every_service_is_recognized_by_its_window(titulo, esperado):
    from app.windows.focus import platform_of

    janela = DesktopWindow(handle=1, process="chrome.exe", title=titulo)

    assert platform_of(janela) == esperado


# ── A unidade em que se fala de pixel ─────────────────────────────────────


def test_the_server_declares_dpi_awareness_before_touching_coordinates():
    """Sem isto o Windows mente sobre o tamanho da janela em tela com escala.

    Medido nesta máquina: tela 1920x1200 a 125%, `GetWindowRect` devolvia
    1550x926 e a foto saía recortada em 20% — o toque num perfil acertava o
    vizinho. É um estado de processo, não dá para testar o efeito aqui; o que
    dá para garantir é que a subida do servidor faz a declaração.
    """
    import app.main as main

    assert "declarar_consciencia_de_dpi()" in Path(main.__file__).read_text(encoding="utf-8")
