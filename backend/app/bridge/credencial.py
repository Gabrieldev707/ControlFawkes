"""O segredo que separa o Native Host de qualquer outra coisa que fale HTTP.

## Por que NÃO é pareamento

O ControlFawkes já tem `security/pairing.py`, e ele foi feito para o celular:
PIN de seis dígitos que a pessoa lê na tela e digita no aparelho, com
expiração, bloqueio progressivo e um `DeviceStore` que lembra o aparelho pelo
nome. Isso modela um dispositivo EXTERNO que chega pela rede e precisa de um
humano para aprovar.

O Native Host não é nada disso. Ele é uma peça interna do próprio
ControlFawkes, rodando na mesma máquina, spawnada pelo Chrome. Não há segundo
aparelho, não há humano no meio, não há tela para mostrar PIN. Forçar a
semântica de pareamento aqui inventaria um dispositivo que não existe e
encheria a lista de aparelhos pareados do celular com uma entrada que a pessoa
não reconheceria.

O que existe é autenticação de PROCESSO: dois programas locais, o mesmo dono,
um segredo compartilhado gerado pela máquina e lido do disco pelos dois.

## O que este segredo protege, e o que não

Protege de: qualquer página aberta no navegador. Uma aba pode fazer `fetch`
para `127.0.0.1:8100` — isso não é hipótese, é o motivo pelo qual o WebSocket
em localhost foi descartado no Spike B. O que ela não consegue é ler um arquivo
em `backend/data/bridge/`.

NÃO protege de: outro processo do mesmo usuário nesta máquina, que pode ler o
arquivo. Isso é aceito e está escrito aqui de propósito — no modelo de ameaça
deste projeto, um processo hostil com o seu usuário já perdeu o jogo por vias
muito mais diretas do que forjar um evento de `<video>`.

## As três regras que não se negociam

1. **Nunca chega ao content script nem ao manifest.** A extensão fala com o
   host por stdio, e é o HOST que autentica no backend. Um segredo no
   `manifest.json` estaria legível em `chrome://extensions` para qualquer um.
2. **Nunca é registrado.** Nem em log, nem em mensagem de erro, nem em
   `repr()`. Ver `test_bridge_credencial.py`.
3. **Conferido em toda mensagem.** Não há sessão, não há "já autenticou antes".
   Cada POST carrega o segredo e cada POST é conferido.
"""

from __future__ import annotations

from pathlib import Path
import os
import secrets


ARQUIVO_PADRAO = (
    Path(__file__).resolve().parent.parent.parent / "data" / "bridge" / "credencial"
)

# Move o arquivo de lugar. Existe para a suíte: ela sobe a aplicação inteira em
# processo, e sem isto cada rodada gera — ou pior, SOBRESCREVE — a credencial de
# verdade da máquina, desconectando o host que estiver rodando.
#
# Mesma forma da trava de instância e do log do host: variável de ambiente, e
# não detecção de pytest dentro do código de produção. Quem desvia diz isso em
# voz alta.
VARIAVEL_DE_CAMINHO = "CONTROLFAWKES_BRIDGE_CREDENCIAL"

# O cabeçalho que carrega o segredo. Nome próprio e não `Authorization`: este
# não é o esquema de token do celular, e usar o mesmo cabeçalho convidaria a
# confundir os dois — que é exatamente o que a decisão desta fase separou.
CABECALHO = "X-ControlFawkes-Bridge"

# 32 bytes de entropia. Sem prazo de validade: girar um segredo que só dois
# processos locais conhecem não protege de nada e cria uma falha nova — a de
# host e servidor discordarem depois de uma rotação malfeita.
BYTES = 32


class CredencialDaPonte:
    """Lê, gera e confere o segredo. Nunca o devolve para lugar nenhum além de
    quem vai usá-lo para autenticar."""

    def __init__(self, caminho: Path | None = None) -> None:
        desviado = os.environ.get(VARIAVEL_DE_CAMINHO, "").strip()
        self._caminho = caminho or (Path(desviado) if desviado else ARQUIVO_PADRAO)

    def existe(self) -> bool:
        return self._caminho.is_file()

    def ler(self) -> str | None:
        """O segredo guardado, ou `None`.

        `None` e string vazia dão no mesmo para quem chama, mas um arquivo vazio
        NÃO pode virar um segredo vazio que casa com um cabeçalho vazio.
        """
        try:
            guardado = self._caminho.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return guardado or None

    def garantir(self) -> str:
        """O segredo, gerando um na primeira vez.

        Chamado pelo servidor ao subir e pelo host ao falar. Os dois lendo o
        mesmo arquivo é o que dispensa qualquer troca de mensagens para
        combinar a credencial.
        """
        atual = self.ler()
        if atual is not None:
            return atual

        novo = secrets.token_urlsafe(BYTES)
        self._caminho.parent.mkdir(parents=True, exist_ok=True)
        # Cria com permissão restrita ANTES de escrever. No Windows o modo é
        # praticamente decorativo — quem protege lá é a ACL do perfil do
        # usuário —, mas o arquivo nasce fechado onde o modo vale.
        descritor = os.open(
            self._caminho, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600,
        )
        with os.fdopen(descritor, "w", encoding="utf-8") as arquivo:
            arquivo.write(novo)
        return novo

    def confere(self, apresentado: object) -> bool:
        """O que veio no cabeçalho é o segredo?

        `compare_digest` e não `==`: a comparação byte a byte do Python
        interrompe no primeiro caractere diferente, e o tempo que ela leva conta
        quantos casaram. Contra um atacante local isso é teórico — e é barato o
        bastante para não valer discutir.

        Sem credencial no disco, NADA passa. O modo de falha é fechado: um
        arquivo apagado deixa a ponte muda, não deixa a ponte aberta.
        """
        esperado = self.ler()
        if esperado is None or not isinstance(apresentado, str) or not apresentado:
            return False
        return secrets.compare_digest(apresentado, esperado)

    def __repr__(self) -> str:
        """Sem o segredo. Um `repr` cai em log de exceção sem ninguém pedir."""
        return f"<CredencialDaPonte {self._caminho.name} presente={self.existe()}>"
