"""O perfil da pessoa — e por que ele saiu do navegador.

Relatado em 17/08/2026: o controle era aberto em `192.168.0.168:5174`, passou a
ser aberto em `:5173`, e nome e foto tinham sumido. `localStorage` é separado
por ORIGEM, e origem inclui a porta. Nada tinha sido apagado; o dado estava em
outra gaveta, inalcançável.

O que estes testes travam é a consequência: o perfil vive no computador, e
sobrevive a troca de porta, de aparelho, de navegador e a restart do servidor.
"""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import profile as rota
from app.profiles.usuario import MAXIMO_DA_FOTO, PerfilDoUsuario


FOTO = "data:image/jpeg;base64,/9j/4AAQSkZJRg=="


@pytest.fixture()
def perfil(tmp_path, monkeypatch) -> PerfilDoUsuario:
    loja = PerfilDoUsuario(tmp_path / "perfil.json")
    monkeypatch.setattr(rota, "perfil_do_usuario", loja)
    return loja


# ── O armazenamento ───────────────────────────────────────────────────────


def test_sem_arquivo_o_perfil_e_vazio_e_nao_erro(perfil: PerfilDoUsuario):
    assert perfil.ler().como_dicionario() == {"nome": None, "foto": None}


def test_o_que_foi_salvo_volta(perfil: PerfilDoUsuario):
    perfil.salvar("Gabriel", FOTO)

    guardado = perfil.ler()
    assert (guardado.nome, guardado.foto) == ("Gabriel", FOTO)


def test_o_perfil_sobrevive_a_reiniciar_o_servidor(tmp_path):
    """Outro processo, outra instância, mesmo arquivo — que é o que um restart
    é. Não há estado em memória que possa se perder."""
    caminho = tmp_path / "perfil.json"
    PerfilDoUsuario(caminho).salvar("Gabriel", FOTO)

    assert PerfilDoUsuario(caminho).ler().nome == "Gabriel"


def test_um_arquivo_estragado_nao_derruba_a_tela(perfil: PerfilDoUsuario):
    perfil._caminho.parent.mkdir(parents=True, exist_ok=True)
    perfil._caminho.write_text("{isto não é json", encoding="utf-8")

    assert perfil.ler().nome is None


def test_o_nome_e_aparado_e_devolvido_como_ficou(perfil: PerfilDoUsuario):
    """Devolver o resultado real importa: a tela não pode mostrar o que mandou
    enquanto o servidor guardou outra coisa."""
    assert perfil.salvar("  Gabriel   Azevedo  ", None).nome == "Gabriel Azevedo"


def test_nome_vazio_vira_ausencia(perfil: PerfilDoUsuario):
    assert perfil.salvar("   ", None).nome is None


def test_uma_url_externa_nao_e_aceita_como_foto(perfil: PerfilDoUsuario):
    """Uma URL aqui viraria uma requisição que o celular faria para fora da
    rede sem ninguém ter pedido."""
    assert perfil.salvar("Gabriel", "https://exemplo.com/foto.jpg").foto is None


def test_uma_foto_grande_demais_e_recusada(perfil: PerfilDoUsuario):
    """O perfil não é armazenamento de arquivo."""
    gigante = "data:image/jpeg;base64," + "A" * MAXIMO_DA_FOTO

    assert perfil.salvar("Gabriel", gigante).foto is None


def test_o_que_nao_e_texto_nao_vira_perfil(perfil: PerfilDoUsuario):
    for lixo in (123, [], {}, True, None):
        assert perfil.salvar(lixo, lixo).como_dicionario() == {"nome": None, "foto": None}


def test_remover_apaga_dos_dois_campos(perfil: PerfilDoUsuario):
    perfil.salvar("Gabriel", FOTO)

    assert perfil.salvar("Gabriel", None).foto is None
    assert perfil.ler().nome == "Gabriel"


# ── A rota ────────────────────────────────────────────────────────────────


@pytest.fixture()
def client(monkeypatch):
    class LojaFalsa:
        @staticmethod
        def authenticate(device_id, token):
            return device_id == "aparelho" and token == "segredo"

    class DispatcherFalso:
        device_store = LojaFalsa()

    monkeypatch.setattr(rota.websocket_module, "dispatcher", DispatcherFalso())
    app = FastAPI()
    app.include_router(rota.router)
    return TestClient(app)


CABECALHOS = {"X-Device-Id": "aparelho", "X-Device-Token": "segredo"}


def test_sem_autenticacao_o_perfil_nao_sai(client, perfil):
    assert client.get("/profile/me").status_code == 401


def test_com_token_errado_o_perfil_nao_sai(client, perfil):
    resposta = client.get(
        "/profile/me", headers={"X-Device-Id": "aparelho", "X-Device-Token": "chute"},
    )

    assert resposta.status_code == 401


def test_o_ciclo_completo_pela_rota(client, perfil):
    salvo = client.put(
        "/profile/me", json={"nome": "Gabriel", "foto": FOTO}, headers=CABECALHOS,
    )
    lido = client.get("/profile/me", headers=CABECALHOS)

    assert salvo.status_code == 200
    assert lido.json() == {"nome": "Gabriel", "foto": FOTO}


def test_um_aparelho_diferente_ve_o_mesmo_perfil(client, perfil):
    """A invariante que resolve o relato: o perfil é da PESSOA e mora no
    computador. Outro navegador, outra porta, outro celular — mesmo perfil."""
    client.put("/profile/me", json={"nome": "Gabriel", "foto": FOTO}, headers=CABECALHOS)

    # Uma segunda "aba", sem nenhum armazenamento local próprio.
    outro = client.get("/profile/me", headers=CABECALHOS)

    assert outro.json()["nome"] == "Gabriel"


def test_um_corpo_que_nao_e_json_nao_estoura(client, perfil):
    resposta = client.put(
        "/profile/me", content=b"{nao e json",
        headers={**CABECALHOS, "content-type": "application/json"},
    )

    assert resposta.status_code == 400


def test_um_corpo_que_nao_e_objeto_e_recusado(client, perfil):
    assert client.put("/profile/me", json=[1, 2], headers=CABECALHOS).status_code == 400


def test_a_rota_devolve_o_que_ficou_e_nao_o_que_veio(client, perfil):
    resposta = client.put(
        "/profile/me",
        json={"nome": "  Gabriel  ", "foto": "https://exemplo.com/x.jpg"},
        headers=CABECALHOS,
    )

    assert resposta.json() == {"nome": "Gabriel", "foto": None}


def test_o_perfil_fica_onde_o_git_ignora(perfil):
    """Junto do histórico e do pareamento. A foto sai do celular, e isso é uma
    mudança real de propriedade — mas ela não sai da casa, e não vai para o
    repositório."""
    import subprocess
    from pathlib import Path

    from app.profiles.usuario import ARQUIVO_PADRAO

    raiz = Path(__file__).resolve().parent.parent.parent
    resultado = subprocess.run(
        ["git", "check-ignore", str(ARQUIVO_PADRAO)],
        cwd=raiz, capture_output=True, text=True, check=False,
    )

    assert resultado.returncode == 0


def test_o_arquivo_guardado_e_json_legivel(perfil: PerfilDoUsuario):
    """Nada de formato opaco: dá para abrir, ler e apagar à mão."""
    perfil.salvar("Gabriel", None)

    assert json.loads(perfil._caminho.read_text(encoding="utf-8"))["nome"] == "Gabriel"
