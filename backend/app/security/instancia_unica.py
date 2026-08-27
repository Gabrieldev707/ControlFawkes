"""Um ControlFawkes por computador.

Por que isto existe: no Windows, dois processos conseguem escutar a mesma porta.
O `SO_REUSEADDR` que o uvicorn liga tem semântica diferente da do Linux — lá o
segundo processo leva "endereço em uso" e morre; aqui ele sobe calado, e só um
dos dois recebe as conexões.

Os dois, porém, rodam o laço de "tocando agora", e os dois gravam no mesmo
`historico.json`. O resultado é tempo contado em dobro, sem nenhum sinal de que
algo está errado: medido nesta máquina, três minutos de relógio viraram seis
minutos no catálogo, e a pessoa que olhou a tela viu um número errado sem ter
como desconfiar de onde ele veio.

Um número errado é pior do que um servidor que não sobe. Este módulo garante
que o segundo não suba.

A trava é um bloqueio exclusivo de arquivo, e não um arquivo com o PID dentro:
o bloqueio morre junto com o processo, seja qual for o motivo. Com PID gravado,
um desligamento abrupto deixaria uma trava eterna e o servidor nunca mais
subiria — trocaríamos um problema silencioso por outro pior.
"""

from __future__ import annotations

from pathlib import Path
import os
import sys


ARQUIVO_PADRAO = Path(__file__).resolve().parent.parent.parent / "data" / "instancia.lock"

# Desliga a trava. Existe para a suíte de testes, que sobe a aplicação inteira
# em processo com o `TestClient` — muitas vezes com o servidor de verdade no ar.
# Sem esta saída, a suíte passava ou falhava conforme o servidor estivesse ou
# não rodando, que é o pior tipo de teste que existe.
#
# Variável de ambiente, e não detecção de pytest dentro do código de produção:
# quem desliga uma proteção tem de dizer isso em voz alta.
VARIAVEL_DE_DESLIGAMENTO = "CONTROLFAWKES_SEM_TRAVA_DE_INSTANCIA"


def trava_desligada() -> bool:
    return os.environ.get(VARIAVEL_DE_DESLIGAMENTO, "").strip() not in ("", "0")


class JaEstaRodando(RuntimeError):
    """Outro ControlFawkes já está no ar neste computador."""


class TravaDeInstancia:
    def __init__(self, caminho: Path | None = None) -> None:
        self._caminho = caminho or ARQUIVO_PADRAO
        self._arquivo = None

    def tomar(self) -> None:
        """Toma a trava, ou levanta `JaEstaRodando`.

        Em caso de imprevisto — sem permissão de escrita, sistema sem bloqueio
        de arquivo — a trava é dispensada e o servidor sobe. Vale a pena: a
        alternativa é um controle que não liga por causa do mecanismo que
        deveria protegê-lo, e o problema que ele evita não é fatal.
        """
        if trava_desligada():
            return

        try:
            self._caminho.parent.mkdir(parents=True, exist_ok=True)
            arquivo = open(self._caminho, "a+b")
        except OSError:
            return

        try:
            _bloquear(arquivo)
        except JaEstaRodando:
            arquivo.close()
            raise
        except OSError:
            # Sem bloqueio disponível: segue sem trava.
            arquivo.close()
            return

        self._arquivo = arquivo

    def soltar(self) -> None:
        if self._arquivo is None:
            return
        try:
            _desbloquear(self._arquivo)
        except OSError:
            pass
        finally:
            self._arquivo.close()
            self._arquivo = None


def _bloquear(arquivo) -> None:
    if sys.platform == "win32":
        import msvcrt

        try:
            # Um byte basta: o que interessa é a exclusividade, não a região.
            msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as erro:
            # EACCES/EDEADLOCK aqui significa "outro processo tem a trava".
            raise JaEstaRodando(MENSAGEM) from erro
        return

    import fcntl

    try:
        fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as erro:
        raise JaEstaRodando(MENSAGEM) from erro


def _desbloquear(arquivo) -> None:
    if sys.platform == "win32":
        import msvcrt

        arquivo.seek(0)
        msvcrt.locking(arquivo.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(arquivo.fileno(), fcntl.LOCK_UN)


MENSAGEM = (
    "Já existe um ControlFawkes rodando neste computador.\n"
    "Dois servidores contam o tempo assistido duas vezes — feche o outro "
    "antes de subir este."
)
