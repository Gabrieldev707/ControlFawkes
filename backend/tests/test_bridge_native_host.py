"""Spike A da Fase 1 — Native Messaging.

O que estes testes provam sem Chrome, sem registro do Windows e sem servidor no
ar: o enquadramento que o Chrome usa, o laço do host, e o relay até o
ControlFawkes. O que eles NÃO provam está registrado no Master Loop — carregar
a extensão descompactada é clique humano em `chrome://extensions`.

O valor de separar assim: quando o cano falhar em produção, dá para saber de
imediato se o defeito está no enquadramento (coberto aqui) ou na instalação
(não coberto, e por isso documentado passo a passo).
"""

from __future__ import annotations

import io
import json
import struct

import pytest

from app.bridge import framing
from app.bridge.native_host import PROTOCOL_VERSION, responder, servir


def _enquadrar(conteudo: dict) -> bytes:
    bruto = json.dumps(conteudo).encode("utf-8")
    return struct.pack("@I", len(bruto)) + bruto


def _desenquadrar(bruto: bytes) -> list[dict]:
    mensagens = []
    posicao = 0
    while posicao < len(bruto):
        (tamanho,) = struct.unpack("@I", bruto[posicao:posicao + 4])
        posicao += 4
        mensagens.append(json.loads(bruto[posicao:posicao + tamanho].decode("utf-8")))
        posicao += tamanho
    return mensagens


# ── Enquadramento ─────────────────────────────────────────────────────────


def test_ida_e_volta_do_enquadramento():
    saida = io.BytesIO()
    framing.escrever_mensagem(saida, {"messageType": "PING", "acentuação": "ção"})

    lido = framing.ler_mensagem(io.BytesIO(saida.getvalue()))

    assert lido == {"messageType": "PING", "acentuação": "ção"}


def test_o_tamanho_vai_na_ordem_nativa_e_nao_na_de_rede():
    """`@I` e não `!I`.

    Trocar por ordem de rede passaria em qualquer teste que use o mesmo
    `struct` dos dois lados e devolveria lixo em produção — porque quem escreve
    do outro lado é o Chrome, que usa a ordem da máquina.
    """
    saida = io.BytesIO()
    framing.escrever_mensagem(saida, {"a": 1})

    cabecalho = saida.getvalue()[:4]

    assert struct.unpack("@I", cabecalho)[0] == len(saida.getvalue()) - 4


def test_cano_fechado_e_fim_normal():
    with pytest.raises(framing.PonteFechada):
        framing.ler_mensagem(io.BytesIO(b""))


def test_mensagem_truncada_nao_passa_por_completa():
    completa = _enquadrar({"messageType": "PING"})

    with pytest.raises(framing.MensagemInvalida, match="truncada"):
        framing.ler_mensagem(io.BytesIO(completa[:-3]))


def test_leitura_em_pedacos_nao_trunca_a_mensagem():
    """`read(n)` pode devolver menos do que se pediu, e em cano quase sempre
    devolve. Um `read` solto funciona no teste e trunca em produção."""
    completa = _enquadrar({"messageType": "PING", "recheio": "x" * 500})

    class _AosPoucos(io.BytesIO):
        def read(self, tamanho=-1):
            # Nunca mais de 7 bytes por vez, que é o comportamento hostil.
            return super().read(min(tamanho, 7) if tamanho and tamanho > 0 else tamanho)

    assert framing.ler_mensagem(_AosPoucos(completa))["messageType"] == "PING"


def test_tamanho_absurdo_e_recusado_antes_de_alocar():
    cabecalho = struct.pack("@I", framing.MAXIMO_DE_ENTRADA + 1)

    with pytest.raises(framing.MensagemInvalida, match="acima do limite"):
        framing.ler_mensagem(io.BytesIO(cabecalho + b"x"))


def test_tamanho_zero_e_recusado():
    with pytest.raises(framing.MensagemInvalida, match="tamanho zero"):
        framing.ler_mensagem(io.BytesIO(struct.pack("@I", 0)))


def test_conteudo_que_nao_e_json_nao_derruba_o_host():
    bruto = b"nao sou json"

    with pytest.raises(framing.MensagemInvalida, match="JSON"):
        framing.ler_mensagem(io.BytesIO(struct.pack("@I", len(bruto)) + bruto))


def test_json_que_nao_e_objeto_e_recusado():
    """O envelope tem campos com nome. Aceitar uma lista aqui empurraria o erro
    para dentro de quem consome."""
    bruto = b'["ping"]'

    with pytest.raises(framing.MensagemInvalida, match="objeto JSON"):
        framing.ler_mensagem(io.BytesIO(struct.pack("@I", len(bruto)) + bruto))


def test_resposta_grande_demais_e_recusada():
    with pytest.raises(framing.MensagemInvalida, match="acima do limite"):
        framing.escrever_mensagem(
            io.BytesIO(), {"recheio": "x" * (framing.MAXIMO_DE_SAIDA + 1)},
        )


# ── O relay ───────────────────────────────────────────────────────────────


def test_ping_alcanca_o_controlfawkes_e_volta():
    resposta = responder(
        {"protocolVersion": 1, "messageType": "PING"},
        sonda=lambda: {"status": "ok", "service": "fawkes-remote"},
    )

    assert resposta["messageType"] == "PONG"
    assert resposta["ok"] is True
    assert resposta["controlfawkes"]["status"] == "ok"


def test_controlfawkes_fora_do_ar_e_dado_e_nao_silencio():
    """O Chrome pode abrir antes do servidor. Isso é estado normal, e a
    extensão precisa recebê-lo como resposta em vez de esperar para sempre."""
    def recusada():
        raise ConnectionRefusedError("connection refused")

    resposta = responder({"protocolVersion": 1, "messageType": "PING"}, sonda=recusada)

    assert resposta["ok"] is False
    assert resposta["code"] == "CONTROLFAWKES_UNREACHABLE"


def test_versao_de_protocolo_diferente_e_recusada():
    resposta = responder({"protocolVersion": 99, "messageType": "PING"}, sonda=dict)

    assert resposta["code"] == "PROTOCOL_VERSION_MISMATCH"


def test_tipo_desconhecido_e_recusado_explicitamente():
    """A Fase 1 conhece uma mensagem só. Recusar o resto é o que impede o spike
    de virar protocolo por acidente."""
    resposta = responder(
        {"protocolVersion": 1, "messageType": "POSITION_UPDATE"}, sonda=dict,
    )

    assert resposta["code"] == "UNKNOWN_MESSAGE_TYPE"


def test_o_host_nao_confia_na_extensao_so_porque_ela_e_nossa():
    """Mensagem sem nada dentro não pode virar exceção não tratada."""
    resposta = responder({}, sonda=dict)

    assert resposta["ok"] is False


# ── O laço ────────────────────────────────────────────────────────────────


def test_o_laco_responde_cada_mensagem_e_termina_quando_o_cano_fecha():
    entrada = io.BytesIO(
        _enquadrar({"protocolVersion": 1, "messageType": "PING"})
        + _enquadrar({"protocolVersion": 1, "messageType": "PING"}),
    )
    saida = io.BytesIO()

    servir(entrada, saida, sonda=lambda: {"status": "ok"})

    respostas = _desenquadrar(saida.getvalue())
    assert [r["messageType"] for r in respostas] == ["PONG", "PONG"]


def test_uma_mensagem_invalida_nao_mata_o_laco():
    """Derrubar o host daria à extensão o poder de matá-lo com um byte errado,
    e o Chrome respawnaria em seguida — um ciclo de processos invisível."""
    lixo = b"{{{"
    entrada = io.BytesIO(
        struct.pack("@I", len(lixo)) + lixo
        + _enquadrar({"protocolVersion": 1, "messageType": "PING"}),
    )
    saida = io.BytesIO()

    servir(entrada, saida, sonda=lambda: {"status": "ok"})

    respostas = _desenquadrar(saida.getvalue())
    assert respostas[0]["code"] == "INVALID_MESSAGE"
    assert respostas[1]["messageType"] == "PONG"


def test_o_host_se_recupera_de_um_restart_do_controlfawkes_sem_reiniciar():
    """O host não guarda conexão com o ControlFawkes: cada mensagem sonda de
    novo.

    É o que faz um restart do servidor ser transparente. Se ele mantivesse um
    cliente vivo, o primeiro restart deixaria a ponte morta até o Chrome
    resolver reconectar — e o Chrome não tem motivo para reconectar, porque do
    lado dele nada caiu.
    """
    tentativas = {"n": 0}

    def instavel():
        tentativas["n"] += 1
        if tentativas["n"] == 1:
            raise ConnectionRefusedError("servidor reiniciando")
        return {"status": "ok"}

    entrada = io.BytesIO(
        _enquadrar({"protocolVersion": 1, "messageType": "PING"})
        + _enquadrar({"protocolVersion": 1, "messageType": "PING"}),
    )
    saida = io.BytesIO()

    servir(entrada, saida, sonda=instavel)

    respostas = _desenquadrar(saida.getvalue())
    assert respostas[0]["code"] == "CONTROLFAWKES_UNREACHABLE"
    assert respostas[1]["messageType"] == "PONG"


def test_porta_fechada_sem_mensagem_nenhuma_sai_limpo():
    saida = io.BytesIO()

    servir(io.BytesIO(b""), saida, sonda=dict)

    assert saida.getvalue() == b""


# ── Identidade e instalação ───────────────────────────────────────────────


def test_o_id_da_extensao_sai_da_chave_e_nao_do_caminho():
    """Sem `key` no manifest, o ID vem do CAMINHO da pasta — muda de máquina
    para máquina e o `allowed_origins` deixa de casar, sem erro visível."""
    from scripts.gerar_identidade_da_extensao import id_da_extensao

    identificador = id_da_extensao(b"chave de teste")

    assert len(identificador) == 32
    # O alfabeto do Chrome é 'a'-'p', e não hexadecimal.
    assert set(identificador) <= set("abcdefghijklmnop")
    # Determinístico: a mesma chave sempre dá o mesmo ID.
    assert identificador == id_da_extensao(b"chave de teste")


def test_a_chave_do_manifesto_bate_com_a_identidade_gerada():
    """Se divergirem, o Chrome deriva outro ID e recusa a conexão em silêncio."""
    import scripts.instalar_native_host as instalador

    if not instalador.IDENTIDADE.exists():
        pytest.skip("identidade ainda não gerada nesta máquina")

    identidade = json.loads(instalador.IDENTIDADE.read_text(encoding="utf-8"))

    # Não levanta: é isso que o instalador confere antes de tocar no registro.
    instalador._conferir_o_manifesto_da_extensao(identidade)


def test_o_manifesto_do_host_aponta_para_caminho_absoluto():
    """Caminho relativo é ignorado em silêncio pelo Chrome."""
    import scripts.instalar_native_host as instalador

    if not instalador.IDENTIDADE.exists():
        pytest.skip("identidade ainda não gerada nesta máquina")

    identidade = json.loads(instalador.IDENTIDADE.read_text(encoding="utf-8"))
    destino = instalador.escrever_manifesto_do_host(identidade)
    conteudo = json.loads(destino.read_text(encoding="utf-8"))

    from pathlib import Path

    assert Path(conteudo["path"]).is_absolute()
    assert conteudo["type"] == "stdio"
    assert conteudo["allowed_origins"] == [
        f"chrome-extension://{identidade['extensionId']}/"
    ]
