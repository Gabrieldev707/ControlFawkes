"""O que este computador andou assistindo.

O laço de "tocando agora" já lê título, plataforma e posição de segundo em
segundo — e jogava tudo fora. Guardar o mínimo disso é o que permite o controle
responder "continuar de onde parou" e "com base no que você assistiu", em vez de
recomeçar do zero toda vez.

O que fica registrado é o que dá para ver na tela: nome do título, serviço,
quanto tempo ficou tocando e onde parou. Sem identificador de conta, sem quem
estava assistindo — o controle não sabe e não precisa saber.

Fica em `backend/data/`, a pasta que o Git ignora, junto do pareamento e da
chave do catálogo. Some inteiro com um toque em Ajustes.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
import os
import time
import unicodedata
from pathlib import Path

from app.catalog.tmdb import PLATAFORMAS_COM_CATALOGO
from app.media.identidade import (
    chave_da_reproducao,
    como_temporada_e_episodio,
    de_multiplas_reproducoes,
)
from app.media.now_playing import _titulo_generico
from app.schemas.platform import Platform


ARQUIVO_PADRAO = Path(__file__).resolve().parent.parent.parent / "data" / "historico.json"

# Abaixo disso não foi assistido, foi passado. Sem um piso, passar por três
# títulos encheria o histórico de coisas que ninguém viu.
SEGUNDOS_PARA_CONTAR = 90.0

# Teto de itens guardados. O histórico serve para "o que eu estava vendo" e
# "do que eu gosto"; nenhuma das duas melhora com dois anos de registro.
MAXIMO_DE_ITENS = 120

# Serviços que o controle opera mas não registra como assistidos.
#
# Mora aqui e não no gravador porque a LEITURA também precisa dela: barrar na
# gravação não basta, já que o que entrou antes da regra continua no arquivo, e
# uma correção que só valesse para o futuro deixaria a tela errada até alguém
# apagar o histórico. Ver `listar` e `podar_fora_do_historico`, e o gravador
# para o porquê de cada serviço.
PLATAFORMAS_FORA_DO_HISTORICO: frozenset[str] = frozenset({"SPOTIFY", "YOUTUBE"})


def _chave(titulo: str, platform: Platform | None) -> str:
    """Mesma obra no mesmo serviço é a mesma linha, escrita como for."""
    limpo = unicodedata.normalize("NFKD", titulo.strip().lower())
    sem_acento = "".join(c for c in limpo if not unicodedata.combining(c))
    return f"{platform or SEM_SERVICO}::{' '.join(sem_acento.split())}"


# O serviço que não foi reconhecido. Não é um serviço: é a ausência de um, e a
# diferença importa na hora de decidir se duas linhas são a mesma obra.
SEM_SERVICO = "-"


def _mesma_obra(uma: str, outra: str) -> bool:
    """Duas chaves da mesma obra, quando pelo menos uma não sabe o serviço.

    Existe porque o serviço nem sempre é reconhecido na mesma leitura em que o
    título é: quando a API de mídia responde e a janela não, sobra o nome sem o
    serviço. Medido no histórico real, A Casa do Dragão ocupava duas linhas —
    "MAX::a casa do dragao" e "-::a casa do dragao" — com o tempo dividido
    entre as duas e a mesma capa repetida nas duas. A pessoa viu uma série; a
    tela contava dois títulos.

    Serviços diferentes e ambos conhecidos continuam sendo obras diferentes, e
    isso não é detalhe: "O Justiceiro" é um filme de 2004 no Max e uma série da
    Marvel no Disney+. Só o desconhecido é coringa.
    """
    servico_de_uma, _, nome_de_uma = uma.partition("::")
    servico_de_outra, _, nome_de_outra = outra.partition("::")
    if nome_de_uma != nome_de_outra:
        return False
    return SEM_SERVICO in (servico_de_uma, servico_de_outra)


@dataclass(frozen=True)
class Assistido:
    chave: str
    titulo: str
    platform: Platform | None
    segundos: float
    posicao: float | None
    duracao: float | None
    visto_em: float
    poster_url: str | None = None
    generos: tuple[str, ...] = ()
    #: O episódio da ÚLTIMA reprodução, quando se soube o nome dele. A chave
    #: continua sendo a da obra: isto é detalhe de onde ela está, não identidade.
    episodio: str | None = None
    #: Qual reprodução `posicao` e `duracao` descrevem. Ver
    #: `IdentidadeDaReproducao.chave`.
    reproducao: str | None = None
    #: Esta linha já juntou mais de uma reprodução? Gruda uma vez descoberto:
    #: uma série não deixa de ser série porque a leitura seguinte foi pobre.
    multiplas_reproducoes: bool = False

    @property
    def terminado(self) -> bool:
        """A OBRA acabou — e não apenas a reprodução que estava tocando.

        A distinção não é sutil, é o bug. Medido no histórico real: Loki tinha
        `posicao` 2226,5 de `duracao` 2241,2 — a razão passava de 0,94 e a série
        inteira saía de "continuar assistindo". Só que 2241 segundos são trinta
        e sete minutos: um episódio. A pessoa tinha acabado UM episódio de oito
        horas e meia de série, que é o momento em que ela MAIS quer o próximo.

        Numa linha que junta várias reproduções, a posição não responde por
        obra nenhuma, e a resposta honesta é "não terminou".
        """
        if self.multiplas_reproducoes:
            return False
        if self.duracao is None or self.posicao is None or self.duracao <= 0:
            return False
        return self.posicao / self.duracao >= 0.94

    def como_dicionario(self) -> dict:
        return {
            "titulo": self.titulo,
            "platform": self.platform,
            "segundos": round(self.segundos, 1),
            "posicao": self.posicao,
            "duracao": self.duracao,
            "vistoEm": self.visto_em,
            "posterUrl": self.poster_url,
            "generos": list(self.generos),
            "terminado": self.terminado,
            "episodio": self.episodio,
            "reproducao": self.reproducao,
            "multiplasReproducoes": self.multiplas_reproducoes,
        }

    def como_obra(self) -> dict:
        """A visão de OBRA — a que vai para a tela de perfil.

        Diferente do que se persiste, e a diferença é o conserto do bug do
        Batman. No arquivo cabe tudo, inclusive a posição do último episódio,
        que serve para retomar a reprodução. Já numa lista de OBRAS, esse
        número não responde por obra nenhuma.

        Medido no histórico real: "Batman: Caped Crusader", 7850 segundos
        assistidos, `posicao` 484,9 de `duracao` 1680,0. A tela lia esses dois
        números como progresso da série e anunciava "faltam 20 min" para uma
        série que a pessoa já tinha terminado. Os números estavam certos — eles
        descrevem um episódio. Errada era a frase que a tela montava com eles.

        Então a obra multi-reprodução vai sem posição e sem duração. Ela tem o
        que de fato se sabe dela: quanto tempo somou, quando foi a última vez, e
        em que episódio parou.
        """
        dados = self.como_dicionario()
        if self.multiplas_reproducoes:
            dados["posicao"] = None
            dados["duracao"] = None
        # "T1 E4" quando o serviço publicou os números, e o nome do episódio
        # quando não publicou. Pedido em 19/08/2026 — e a honestidade do caso
        # comum vale dizer: o Max não põe número nenhum na janela, então o que
        # aparece é o nome. Quem sabe os números é a página, e chegar até ela é
        # o Browser Media Bridge. Ver `media/identidade.py`.
        numeros = como_temporada_e_episodio(self.episodio)
        if numeros is not None:
            dados["episodio"] = numeros
        return dados


class HistoryStore:
    def __init__(self, caminho: Path | None = None) -> None:
        self._caminho = caminho or ARQUIVO_PADRAO

    def _ler(self) -> dict[str, dict]:
        try:
            dados = json.loads(self._caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return dados if isinstance(dados, dict) else {}

    def _gravar(self, dados: dict[str, dict]) -> bool:
        try:
            self._caminho.parent.mkdir(parents=True, exist_ok=True)
            temporario = self._caminho.with_suffix(".tmp")
            temporario.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
            # Troca atômica: um desligamento no meio da escrita apagaria tudo.
            os.replace(temporario, self._caminho)
        except OSError:
            return False
        return True

    @staticmethod
    def _do_dicionario(chave: str, bruto: object) -> Assistido | None:
        if not isinstance(bruto, dict):
            return None
        titulo = bruto.get("titulo")
        if not isinstance(titulo, str) or not titulo:
            return None

        def numero(nome: str) -> float | None:
            valor = bruto.get(nome)
            return float(valor) if isinstance(valor, (int, float)) else None

        generos = bruto.get("generos")
        segundos = numero("segundos") or 0.0
        duracao = numero("duracao")
        episodio = bruto.get("episodio")
        return Assistido(
            chave=chave,
            titulo=titulo,
            platform=bruto.get("platform"),
            segundos=segundos,
            posicao=numero("posicao"),
            duracao=duracao,
            visto_em=numero("vistoEm") or 0.0,
            poster_url=bruto.get("posterUrl") if isinstance(bruto.get("posterUrl"), str) else None,
            generos=tuple(g for g in generos if isinstance(g, str)) if isinstance(generos, list) else (),
            episodio=episodio if isinstance(episodio, str) and episodio else None,
            reproducao=bruto.get("reproducao") if isinstance(bruto.get("reproducao"), str) else None,
            # Derivado na leitura, e não só lido do arquivo: os registros
            # gravados ANTES desta correção não têm o campo, e é justamente
            # neles que a série já está marcada como terminada. Recalcular aqui
            # desfaz o estrago sem migração e sem tocar no arquivo.
            multiplas_reproducoes=bool(bruto.get("multiplasReproducoes")) or de_multiplas_reproducoes(
                segundos, duracao, isinstance(episodio, str) and bool(episodio),
            ),
        )

    def _linha_da_obra(
        self, dados: dict[str, dict], titulo: str, platform: Platform | None,
    ) -> tuple[str, list[Assistido]]:
        """Sob que chave esta obra fica, e o que já existe dela no arquivo.

        A lista vem da mais recente para a mais antiga, que é a ordem em que a
        fusão deve olhar: quem viu por último é quem sabe onde a pessoa parou.

        A chave escolhida é sempre a que conhece o serviço. Sem isso, uma
        leitura sem serviço arrastaria a linha inteira de volta para
        "-::a casa do dragao" e o Max deixaria de contar como serviço usado.
        """
        chave = _chave(titulo, platform)
        candidatas = [c for c in dados if c == chave or _mesma_obra(c, chave)]
        anteriores = sorted(
            (
                item for item in (self._do_dicionario(c, dados[c]) for c in candidatas)
                if item is not None
            ),
            key=lambda item: item.visto_em,
            reverse=True,
        )
        if platform is not None:
            return chave, anteriores
        # Sem serviço nesta leitura: entra na linha que já tem um, se houver.
        com_servico = next((a for a in anteriores if a.platform is not None), None)
        return (com_servico.chave if com_servico else chave), anteriores

    def registrar(
        self,
        titulo: str,
        platform: Platform | None,
        segundos: float,
        posicao: float | None,
        duracao: float | None,
        poster_url: str | None = None,
        generos: tuple[str, ...] = (),
        agora: float | None = None,
        episodio: str | None = None,
    ) -> Assistido | None:
        """Soma este trecho ao que já havia deste título.

        Soma em vez de sobrescrever porque assistir é interrompido: meia hora
        hoje e meia hora amanhã são uma hora do mesmo filme, e é o total que diz
        se aquilo importou.

        A chave é a da OBRA, e sempre foi. O que mudou é que `posicao` e
        `duracao` agora sabem de QUAL reprodução falam — sem isso, o fim de um
        episódio marcava a série inteira como vista.
        """
        if not titulo.strip():
            return None

        dados = self._ler()
        chave, anteriores = self._linha_da_obra(dados, titulo, platform)
        # Tudo o que era a mesma obra sai do arquivo e volta como uma linha só.
        for antiga in anteriores:
            dados.pop(antiga.chave, None)

        acumulado = sum(a.segundos for a in anteriores) + max(0.0, segundos)
        anterior = anteriores[0] if anteriores else None

        # De qual reprodução esta leitura fala, e se é a mesma de antes.
        reproducao = chave_da_reproducao(episodio, duracao)
        mesma_reproducao = (
            anterior is not None
            and reproducao is not None
            and anterior.reproducao == reproducao
        )

        # AQUI estava a armadilha. A herança existe por um bom motivo — uma
        # leitura em que a janela não respondeu não pode apagar onde a pessoa
        # parou — mas ela era incondicional, e então a posição de um episódio
        # TERMINADO sobrevivia a todos os episódios seguintes. Medido: uma hora
        # do episódio seguinte, e a série continuava marcada como vista.
        #
        # A regra que separa os dois casos é sobre o que a leitura AFIRMA:
        #
        #   não sei de que reprodução falo   herda. Não saber não contradiz
        #                                    nada, e apagar por ignorância foi
        #                                    o que este teste de caracterização
        #                                    já protegia.
        #   falo de OUTRA reprodução         não herda. Aí há contradição, e a
        #                                    posição guardada é de algo que
        #                                    acabou.
        contradiz = (
            anterior is not None
            and reproducao is not None
            and anterior.reproducao is not None
            and not mesma_reproducao
        )
        pode_herdar = anterior is not None and not contradiz
        herdada_posicao = anterior.posicao if (pode_herdar and anterior) else None
        herdada_duracao = anterior.duracao if (pode_herdar and anterior) else None

        segundos_finais = acumulado
        duracao_final = duracao if duracao is not None else herdada_duracao
        item = Assistido(
            chave=chave,
            titulo=titulo.strip(),
            # O serviço conhecido vence o desconhecido, seja qual dos dois for o
            # mais recente: uma leitura em que a janela não respondeu não apaga
            # o serviço que outra já tinha identificado.
            platform=platform or next(
                (a.platform for a in anteriores if a.platform is not None), None,
            ),
            segundos=segundos_finais,
            posicao=posicao if posicao is not None else herdada_posicao,
            duracao=duracao_final,
            episodio=episodio or (anterior.episodio if mesma_reproducao and anterior else None),
            reproducao=reproducao if reproducao is not None else (
                anterior.reproducao if pode_herdar and anterior else None
            ),
            # Gruda: uma vez série, sempre série. E vale para trás — uma linha
            # antiga que já acumulou mais do que cabe numa reprodução é
            # reconhecida sem precisar ver outro episódio.
            multiplas_reproducoes=(
                any(a.multiplas_reproducoes for a in anteriores)
                # Uma reprodução contradizendo a anterior É a prova direta: a
                # obra teve mais de uma, logo é série.
                or contradiz
                or de_multiplas_reproducoes(
                    segundos_finais, duracao_final, bool(episodio),
                )
            ),
            visto_em=agora if agora is not None else time.time(),
            # O pôster e os gêneros chegam depois, pelo catálogo: uma vez
            # descobertos, não se perdem numa atualização sem eles — nem quando
            # quem os tinha era a outra linha da fusão.
            poster_url=poster_url or next(
                (a.poster_url for a in anteriores if a.poster_url), None,
            ),
            generos=generos or next(
                (a.generos for a in anteriores if a.generos), (),
            ),
        )
        dados[chave] = item.como_dicionario()

        if len(dados) > MAXIMO_DE_ITENS:
            ordenados = sorted(
                dados.items(),
                key=lambda par: par[1].get("vistoEm", 0) if isinstance(par[1], dict) else 0,
                reverse=True,
            )
            dados = dict(ordenados[:MAXIMO_DE_ITENS])

        return item if self._gravar(dados) else None

    def enriquecer(self, chave: str, poster_url: str | None, generos: tuple[str, ...]) -> bool:
        """Guarda o que o catálogo descobriu sobre um título já registrado."""
        dados = self._ler()
        item = self._do_dicionario(chave, dados.get(chave))
        if item is None:
            return False
        atualizado = replace(
            item,
            poster_url=poster_url or item.poster_url,
            generos=generos or item.generos,
        )
        dados[chave] = atualizado.como_dicionario()
        return self._gravar(dados)

    def listar(self) -> list[Assistido]:
        """Tudo o que foi assistido, do mais recente para o mais antigo.

        Sem o que nunca foi uma obra. Barrar isso na gravação não basta: o que
        entrou antes do filtro continua no arquivo, e uma correção que só vale
        para o futuro deixa a tela errada até alguém apagar o histórico.

        Medido no histórico real: uma linha "Netflix" de 120 segundos — a
        página de catálogo, não um filme — era a única com plataforma
        preenchida, e fazia a tela de perfil anunciar a Netflix como serviço
        mais usado com base em nada, enquanto 58 minutos de filme de verdade
        não contavam para nada.

        E sem as capas que o catálogo nunca teve como acertar. Todo pôster
        guardado aqui veio do TMDB, que é catálogo de filme e série: para um
        vídeo do YouTube ele devolve a capa de outra coisa. Medido — um vlog de
        viagem à Síria aparecia em "continuar assistindo" com pôster de filme.
        Descartar na leitura tira da tela também o que já está no arquivo.
        """
        itens = (self._do_dicionario(chave, bruto) for chave, bruto in self._ler().items())
        validos = []
        for item in itens:
            if item is None or _titulo_generico(item.titulo, None, item.platform):
                continue
            # O que não é para virar histórico não vira, nem se já estiver
            # gravado. Descartar na leitura tira da tela também o passado.
            if item.platform in PLATAFORMAS_FORA_DO_HISTORICO:
                continue
            if (
                item.poster_url
                and item.platform is not None
                and item.platform not in PLATAFORMAS_COM_CATALOGO
            ):
                item = replace(item, poster_url=None)
            validos.append(item)
        return sorted(validos, key=lambda item: item.visto_em, reverse=True)

    def continuar(self, limite: int = 10) -> list[Assistido]:
        """O que ficou pela metade, do mais recente para o mais antigo."""
        return [item for item in self.listar() if not item.terminado][:limite]

    def continuar_por_servico(
        self, limite_por_servico: int = 10,
    ) -> list[tuple[Platform, list[Assistido]]]:
        """O mesmo, separado por serviço — e é aqui que o que sumiu reaparece.

        A lista principal tem um teto, e um teto único faz os serviços
        disputarem entre si. Medido em 17/08/2026: três vídeos do YouTube de
        16/08 empurraram para fora do corte tudo o que era de 14/08 — Família
        Soprano, A Casa do Dragão, Rick and Morty e Batman: Caped Crusader
        estavam no arquivo, inteiros, e não cabiam na tela.

        Nenhuma obra é escondida por causa de outra de serviço diferente:
        maratonar YouTube não pode enterrar o que se assiste no Max.

        A ordem dos serviços é a da atividade mais recente, pelo mesmo motivo
        que a das obras: quem está assistindo agora quer ver isso primeiro.
        Obra sem serviço reconhecido não entra — não há em que seção pô-la, e
        inventar uma seção "outros" seria dar nome ao que não tem.
        """
        por_servico: dict[Platform, list[Assistido]] = {}
        for item in self.listar():
            if item.terminado or item.platform is None:
                continue
            por_servico.setdefault(item.platform, []).append(item)

        # `listar()` já vem do mais recente para o mais antigo, então o primeiro
        # de cada lista é o mais recente do serviço.
        return sorted(
            ((servico, itens[:limite_por_servico]) for servico, itens in por_servico.items()),
            key=lambda par: par[1][0].visto_em,
            reverse=True,
        )

    def consolidar(self, limpar_titulo) -> int:
        """Reaplica a limpeza de título ao que já está guardado.

        Quando a limpeza melhora, o passado não melhora junto: "Prime Video:
        Batman" e "Batman" ficam como duas linhas do mesmo filme, cada uma com
        um pedaço do tempo. Isto passa a régua nova sobre os registros antigos e
        soma os que viraram a mesma coisa.

        Devolve quantas linhas desapareceram na fusão.
        """
        dados = self._ler()
        if not dados:
            return 0

        refeito: dict[str, dict] = {}
        for chave, bruto in dados.items():
            item = self._do_dicionario(chave, bruto)
            if item is None:
                continue
            titulo = limpar_titulo(item.titulo).strip() or item.titulo
            nova_chave = _chave(titulo, item.platform)
            # A linha sem serviço entra na que tem serviço, e vice-versa: são a
            # mesma obra lida em passagens diferentes, e é esta fusão que junta
            # os dois pedaços de A Casa do Dragão que já estão no arquivo.
            nova_chave = next(
                (c for c in refeito if _mesma_obra(c, nova_chave) and not c.startswith(
                    f"{SEM_SERVICO}::",
                )),
                nova_chave,
            )
            existente = refeito.get(nova_chave)
            if existente is None and item.platform is not None:
                # O contrário: já havia uma linha sem serviço desta obra.
                sem_servico = _chave(titulo, None)
                if sem_servico in refeito:
                    existente = refeito.pop(sem_servico)
            if existente is None:
                refeito[nova_chave] = {**item.como_dicionario(), "titulo": titulo}
                continue
            # Duas linhas do mesmo título: o tempo soma, e o resto vem da
            # leitura mais recente, que é a que descreve onde a pessoa parou.
            recente = existente if existente["vistoEm"] >= item.visto_em else item.como_dicionario()
            refeito[nova_chave] = {
                **recente,
                "titulo": titulo,
                "segundos": round(existente["segundos"] + item.segundos, 1),
                "posterUrl": existente.get("posterUrl") or item.poster_url,
                "generos": existente.get("generos") or list(item.generos),
                # O serviço conhecido vence: a linha sem plataforma e a linha
                # com plataforma são a mesma obra, e é a fusão delas que devolve
                # A Casa do Dragão ao Max em vez de deixá-la sem serviço.
                "platform": recente.get("platform") or existente.get("platform") or item.platform,
            }

        removidas = len(dados) - len(refeito)
        if removidas <= 0 and len(refeito) == len(dados):
            # Nada mudou de nome: não vale reescrever o arquivo.
            if all(chave in dados for chave in refeito):
                return 0
        self._gravar(refeito)
        return removidas

    def podar_capas(self) -> int:
        """Apaga do arquivo as capas que o catálogo não tinha como acertar.

        `listar()` já descarta essas capas na leitura, e isso basta para a tela.
        Mas o arquivo continua guardando a URL errada, e guardar é o que a faz
        voltar: `_descobrir_capas` pula quem já tem pôster, então uma capa
        errada nunca é substituída pela certa — ela só fica lá, escondida,
        ocupando o lugar da resposta boa.

        Medido no histórico real deste computador: o vlog "CHEGUEI NA SÍRIA,
        PAÍS DE CONFLITO E RELIGIÃO" carregava o pôster de um filme qualquer, e
        a linha "Netflix" — a página de catálogo, não uma obra — carregava o de
        outro. Nenhum dos dois veio de erro do TMDB: veio de perguntar a um
        catálogo de filme por um nome que não é de filme.

        Só a capa é apagada. O tempo assistido continua inteiro, porque ele foi
        medido de verdade e não tem nada de errado.

        Devolve quantas capas saíram.
        """
        dados = self._ler()
        if not dados:
            return 0

        podadas = 0
        for chave, bruto in dados.items():
            item = self._do_dicionario(chave, bruto)
            if item is None or not item.poster_url:
                continue
            # O nome não é de uma obra: é a home do serviço, ou o próprio nome
            # dele. Qualquer capa aqui é a de um título que ninguém pediu.
            suspeita = _titulo_generico(item.titulo, None, item.platform)
            # Ou o serviço não é catálogo de filme — YouTube e Spotify — e o
            # TMDB respondeu com a obra mais parecida que encontrou.
            if item.platform is not None and item.platform not in PLATAFORMAS_COM_CATALOGO:
                suspeita = True
            if suspeita:
                dados[chave] = replace(item, poster_url=None).como_dicionario()
                podadas += 1

        # Nada suspeito: não vale reescrever o arquivo.
        if podadas == 0:
            return 0
        return podadas if self._gravar(dados) else 0

    def podar_fora_do_historico(self) -> int:
        """Apaga do arquivo os serviços que não são para virar histórico.

        `listar` já os descarta na leitura, e isso basta para a tela. Mas eles
        continuam ocupando o teto de `MAXIMO_DE_ITENS` e aparecendo para quem
        abrir o arquivo — e quando o pedido foi "pode tirar do histórico", meia
        remoção não é o que foi pedido.

        Devolve quantas linhas saíram.
        """
        dados = self._ler()
        sobreviventes = {
            chave: bruto for chave, bruto in dados.items()
            if not (
                isinstance(bruto, dict)
                and bruto.get("platform") in PLATAFORMAS_FORA_DO_HISTORICO
            )
        }
        removidas = len(dados) - len(sobreviventes)
        if removidas <= 0:
            return 0
        return removidas if self._gravar(sobreviventes) else 0

    def limpar(self) -> bool:
        try:
            self._caminho.unlink(missing_ok=True)
        except OSError:
            return False
        return True
