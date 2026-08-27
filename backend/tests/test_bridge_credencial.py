"""O segredo da ponte: autenticação de PROCESSO, não pareamento de aparelho.

O que se prova aqui é o que a decisão desta fase separou — este segredo não usa
o `PairingService`, não cria dispositivo, não aparece na lista de aparelhos
pareados do celular, e não vaza para lugar nenhum.
"""

from __future__ import annotations

import io
import json

import pytest

from app.bridge.credencial import CABECALHO, CredencialDaPonte
from app.bridge.native_host import responder, servir


@pytest.fixture()
def credencial(tmp_path):
    return CredencialDaPonte(tmp_path / "bridge" / "credencial")


# ── Geração e leitura ─────────────────────────────────────────────────────


def test_a_primeira_execucao_gera_o_segredo(credencial):
    assert credencial.existe() is False

    segredo = credencial.garantir()

    assert credencial.existe() is True
    assert len(segredo) >= 32


def test_garantir_duas_vezes_devolve_o_mesmo_segredo(credencial):
    """Gerar de novo desligaria a ponte: o host leria um segredo e o servidor
    esperaria outro."""
    assert credencial.garantir() == credencial.garantir()


def test_dois_ControlFawkes_diferentes_nao_compartilham_segredo(tmp_path):
    """Nada de constante no código: o segredo é desta máquina."""
    um = CredencialDaPonte(tmp_path / "a" / "credencial").garantir()
    outro = CredencialDaPonte(tmp_path / "b" / "credencial").garantir()

    assert um != outro


def test_sem_arquivo_a_leitura_e_ausencia_e_nao_erro(credencial):
    assert credencial.ler() is None


def test_um_arquivo_vazio_nao_vira_um_segredo_vazio(credencial):
    """Senão um cabeçalho vazio casaria com um arquivo vazio, e a tranca
    ficaria aberta justamente no estado mais quebrado."""
    credencial._caminho.parent.mkdir(parents=True, exist_ok=True)
    credencial._caminho.write_text("   \n", encoding="utf-8")

    assert credencial.ler() is None
    assert credencial.confere("") is False


# ── Conferência ───────────────────────────────────────────────────────────


def test_a_credencial_correta_passa(credencial):
    segredo = credencial.garantir()

    assert credencial.confere(segredo) is True


def test_a_credencial_ausente_nao_passa(credencial):
    credencial.garantir()

    assert credencial.confere(None) is False
    assert credencial.confere("") is False


def test_a_credencial_errada_nao_passa(credencial):
    credencial.garantir()

    assert credencial.confere("nao-e-o-segredo") is False


def test_quase_certa_tambem_nao_passa(credencial):
    segredo = credencial.garantir()

    assert credencial.confere(segredo[:-1]) is False
    assert credencial.confere(segredo + "x") is False


def test_o_que_nao_e_texto_nao_passa(credencial):
    """Um cabeçalho ausente chega como `None`; um corpo malformado pode chegar
    como qualquer coisa. Nada disso pode virar exceção não tratada."""
    credencial.garantir()

    for lixo in (None, 123, b"bytes", [], {}, True):
        assert credencial.confere(lixo) is False


def test_sem_credencial_no_disco_nada_passa(credencial):
    """Modo de falha fechado: arquivo apagado deixa a ponte muda, não aberta."""
    assert credencial.confere("qualquer-coisa") is False
    assert credencial.confere("") is False


# ── O segredo não vaza ────────────────────────────────────────────────────


def test_o_repr_nao_carrega_o_segredo(credencial):
    """`repr` cai em log de exceção sem ninguém pedir."""
    segredo = credencial.garantir()

    assert segredo not in repr(credencial)


def test_o_segredo_nao_aparece_no_log_do_host(credencial, tmp_path, monkeypatch):
    """A prova que interessa: uma rodada inteira do host — mensagem entrando,
    entrega saindo, resposta voltando — não escreve o segredo em lugar nenhum
    do arquivo de diagnóstico."""
    segredo = credencial.garantir()
    log = tmp_path / "host.log"

    import app.bridge.native_host as host

    monkeypatch.delenv(host.VARIAVEL_SEM_LOG, raising=False)
    monkeypatch.setattr(
        host, "anotar",
        lambda evento, detalhe=None: log.open("a", encoding="utf-8").write(
            f"{evento} {detalhe}\n",
        ),
    )

    evento = {
        "protocolVersion": 1,
        "messageType": "POSITION_SYNC",
        "timestamp": 0,
        "payload": {"sessionId": "s1", "currentTime": 10.0, "duration": 100.0},
    }
    entrada = io.BytesIO(_enquadrar(evento))
    servir(entrada, io.BytesIO(), entregar=lambda m: {"ok": True})

    assert segredo not in log.read_text(encoding="utf-8")


def test_o_segredo_nao_volta_na_resposta_para_a_extensao(credencial):
    """A extensão não pode aprender o segredo nem por acidente: ela é quem NÃO
    deve tê-lo. Quem autentica é o host."""
    segredo = credencial.garantir()
    evento = {
        "protocolVersion": 1,
        "messageType": "PLAY",
        "timestamp": 0,
        "payload": {"sessionId": "s1"},
    }

    resposta = responder(evento, entregar=lambda m: {"ok": True})

    assert segredo not in json.dumps(resposta)


def test_a_mensagem_entregue_nao_carrega_o_segredo_no_corpo(credencial):
    """Ele vai no cabeçalho. No corpo ele acabaria em qualquer log de request."""
    segredo = credencial.garantir()
    entregues: list[dict] = []
    evento = {
        "protocolVersion": 1,
        "messageType": "PLAY",
        "timestamp": 0,
        "payload": {"sessionId": "s1"},
    }

    responder(evento, entregar=lambda m: entregues.append(m) or {"ok": True})

    assert segredo not in json.dumps(entregues)


# ── A extensão nunca vê o segredo ─────────────────────────────────────────


def test_nem_o_manifest_nem_o_content_script_mencionam_a_credencial():
    """Um segredo no `manifest.json` fica legível em `chrome://extensions` para
    qualquer um que abra a página. Esta é a regra mais fácil de quebrar por
    conveniência, e por isso ela é um teste e não um comentário."""
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent.parent / "browser-extension"
    if not raiz.is_dir():  # pragma: no cover - só se a extensão sair do repo
        pytest.skip("extensão ausente")

    proibidos = (CABECALHO.lower(), "credencial", "bridge-secret", "shared-secret")
    for arquivo in list(raiz.rglob("*.js")) + list(raiz.rglob("*.json")):
        if "node_modules" in arquivo.parts:
            continue
        texto = arquivo.read_text(encoding="utf-8", errors="ignore").lower()
        for termo in proibidos:
            assert termo not in texto, f"{arquivo.name} menciona {termo!r}"


def test_o_segredo_nunca_entra_no_repositorio():
    """`backend/data/` é ignorado pelo git, e é lá que o segredo mora. Um
    `git add -A` distraído não pode publicá-lo."""
    import subprocess
    from pathlib import Path

    from app.bridge.credencial import ARQUIVO_PADRAO

    raiz = Path(__file__).resolve().parent.parent.parent
    resultado = subprocess.run(
        ["git", "check-ignore", str(ARQUIVO_PADRAO)],
        cwd=raiz, capture_output=True, text=True, check=False,
    )

    assert resultado.returncode == 0, "a credencial da ponte NÃO está ignorada"


# ── Não é pareamento ──────────────────────────────────────────────────────


def test_a_ponte_nao_usa_o_pareamento_do_celular():
    """A decisão desta fase, virada teste: o Native Host é peça interna, e
    forçar semântica de dispositivo sobre ele inventaria um aparelho que não
    existe — que apareceria na lista de pareados do celular."""
    from pathlib import Path

    import app.api.bridge as rota
    import app.bridge.credencial as modulo

    for arquivo in (modulo.__file__, rota.__file__):
        fonte = Path(arquivo).read_text(encoding="utf-8")
        # Nas docstrings os nomes aparecem para EXPLICAR a separação; o que não
        # pode existir é import.
        for linha in fonte.splitlines():
            if linha.startswith(("import ", "from ")):
                assert "pairing" not in linha
                assert "device_store" not in linha


def test_a_ponte_nao_cria_dispositivo_pareado(tmp_path):
    """A prova pelo efeito, e não pela leitura do código: gerar e conferir a
    credencial não mexe em aparelho nenhum."""
    from app.security.device_store import DeviceStore

    loja = DeviceStore(tmp_path / "devices.json")
    antes = loja.list_devices()

    credencial = CredencialDaPonte(tmp_path / "credencial")
    credencial.confere(credencial.garantir())

    assert loja.list_devices() == antes


def _enquadrar(mensagem: dict) -> bytes:
    import struct

    dados = json.dumps(mensagem).encode("utf-8")
    return struct.pack("@I", len(dados)) + dados
