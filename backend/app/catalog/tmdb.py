"""Onde o título está disponível, pelo catálogo do TMDB.

O que isto resolve: até aqui a busca era "abrir uma URL de resultados". O
controle não sabia nada sobre o conteúdo, então "harry potter" virava uma lista
das seis plataformas para o usuário adivinhar — e a resposta certa, Max, era
justamente uma das que não apareciam.

Com o catálogo, a pergunta muda de "onde você quer procurar?" para "está no
Max, abro?".

Opcional de propósito: sem `CONTROLFAWKES_TMDB_KEY` o controle segue exatamente
como antes. Nenhuma funcionalidade existente depende desta chamada, e uma
falha de rede aqui nunca pode impedir a busca manual.
"""

import asyncio
from dataclasses import dataclass
from difflib import SequenceMatcher
import os
import re
import unicodedata

import httpx

from app.catalog.identidades import IdentidadeStore
from app.catalog.resolver import (
    Candidato,
    Escolhido,
    Nivel,
    Observado,
    Avaliacao,
    classificar,
    normalizar,
    resolver,
    sem_ligacoes,
    tem_candidato_forte,
    tem_casamento_exato,
)
from app.catalog.store import TmdbKeyStore
from app.schemas.ws import Platform


API_BASE = "https://api.themoviedb.org/3"
# w342 e não w185: o cartão tem 132px de largura e a tela do celular
# desenha a 3x, então w185 chegava esticado e borrado.
IMAGE_BASE = "https://image.tmdb.org/t/p/w342"

KEY_VARIABLE = "CONTROLFAWKES_TMDB_KEY"
REGION_VARIABLE = "CONTROLFAWKES_TMDB_REGION"
LANGUAGE_VARIABLE = "CONTROLFAWKES_TMDB_LANGUAGE"

DEFAULT_REGION = "BR"
DEFAULT_LANGUAGE = "pt-BR"
# Curto de propósito: isto entra no caminho de um comando que o usuário está
# esperando. Melhor cair na escolha manual do que deixar a tela parada.
DEFAULT_TIMEOUT = 4.0


# O casamento é pelo nome normalizado, não pelo id numérico: os ids do TMDB
# mudam por região e o do Max já mudou uma vez quando a HBO renomeou o serviço.
PROVIDER_ALIASES: tuple[tuple[Platform, tuple[str, ...]], ...] = (
    ("NETFLIX", ("netflix",)),
    ("PRIME_VIDEO", ("amazon prime video", "prime video", "amazon video")),
    ("DISNEY_PLUS", ("disney plus", "disney+")),
    ("MAX", ("max", "hbo max")),
    ("YOUTUBE", ("youtube", "youtube premium")),
)


# Serviços cujo catálogo responde "onde assisto este filme?".
#
# O YouTube e o Spotify ficam de fora de propósito. Assistir futebol ao vivo no
# YouTube é assistir, e conta no histórico — mas o TMDB praticamente nunca marca
# um filme como disponível por assinatura no YouTube, então usar o YouTube para
# filtrar recomendações não estreita a lista: zera. Medido, e foi exatamente o
# que aconteceu quando o histórico passou a reconhecer a plataforma do YouTube.
PLATAFORMAS_COM_CATALOGO: frozenset[Platform] = frozenset(
    {"NETFLIX", "PRIME_VIDEO", "DISNEY_PLUS", "MAX"},
)


# Palavras que nomeiam o serviço, não a obra.
_NOMES_DE_SERVICO = {
    "prime", "video", "netflix", "disney", "plus", "hbo", "youtube", "spotify",
    "amazon", "star", "globoplay",
}


# "harry potter 5" -> franquia "harry potter", posição 5.
_NUMERO_NO_FIM = re.compile(r"(?P<franquia>.+?)\s+(?P<numero>\d{1,2})")


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower().strip())
    return " ".join(
        "".join(c for c in decomposed if not unicodedata.combining(c)).split()
    )


def platform_for_provider(provider_name: str) -> Platform | None:
    normalized = _normalize(provider_name)
    for platform, aliases in PROVIDER_ALIASES:
        if normalized in aliases:
            return platform
    return None


@dataclass(frozen=True)
class Destaque:
    """Um título em cartaz num serviço, para a tela de plataformas."""

    title: str
    year: int | None
    poster_url: str | None


@dataclass(frozen=True)
class TitleAvailability:
    title: str
    year: int | None
    poster_url: str | None
    platforms: list[Platform]
    # "MOVIE" ou "TV": é o que permite a tela perguntar "filme ou série?"
    # quando as duas respondem igualmente bem à consulta.
    kind: str = "MOVIE"


def catalog_enabled() -> bool:
    return bool(os.environ.get(KEY_VARIABLE, "").strip())


class TmdbCatalog:
    def __init__(
        self,
        api_key: str | None = None,
        region: str | None = None,
        language: str | None = None,
        client: httpx.AsyncClient | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        key_store: TmdbKeyStore | None = None,
        identidades: IdentidadeStore | None = None,
    ) -> None:
        self._key_store = key_store or TmdbKeyStore()
        self._identidades = identidades or IdentidadeStore()
        # A variável de ambiente vence a chave guardada: quem configurou o
        # servidor assim não pode ter isso sobrescrito pelo celular.
        self._fixed_key = api_key if api_key is not None else None
        self.api_key = self._resolve_key()
        self.region = (region or os.environ.get(REGION_VARIABLE, DEFAULT_REGION)).upper()
        self.language = language or os.environ.get(LANGUAGE_VARIABLE, DEFAULT_LANGUAGE)
        self._client = client
        self._timeout = timeout
        # Os ids não mudam durante a execução; resolver uma vez basta.
        self._provider_ids: dict[Platform, int] | None = None
        self._generos: dict[int, str] | None = None

    def _resolve_key(self) -> str:
        if self._fixed_key is not None:
            return self._fixed_key.strip()
        do_ambiente = os.environ.get(KEY_VARIABLE, "").strip()
        return do_ambiente or self._key_store.load()

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    @property
    def key_source(self) -> str:
        """De onde veio a chave em uso, para a tela poder dizer a verdade."""
        if not self.api_key:
            return "NENHUMA"
        if self._fixed_key is not None:
            return "FIXA"
        return "AMBIENTE" if os.environ.get(KEY_VARIABLE, "").strip() else "GUARDADA"

    @property
    def env_key_wins(self) -> bool:
        """Com a variável de ambiente definida, colar chave no celular não teria
        efeito — e a tela precisa dizer isso em vez de fingir que salvou."""
        return self._fixed_key is None and bool(os.environ.get(KEY_VARIABLE, "").strip())

    def save_key(self, chave: str) -> bool:
        if not self._key_store.save(chave):
            return False
        self.api_key = self._resolve_key()
        return True

    def forget_key(self) -> bool:
        if not self._key_store.clear():
            return False
        self.api_key = self._resolve_key()
        return True

    async def check_key(self, chave: str) -> bool:
        """A chave é aceita pelo TMDB?

        O endpoint `/authentication` existe exatamente para isso e responde
        sobre a chave, não sobre o conteúdo. Separar as duas perguntas é o que
        permite dizer "a chave está errada" sem confundir com "não achei o
        título de teste".
        """
        provisorio = TmdbCatalog(
            api_key=chave,
            region=self.region,
            language=self.language,
            client=self._client,
            timeout=self._timeout,
        )
        if self._client is not None:
            resposta = await provisorio._get(self._client, "/authentication")
        else:
            async with httpx.AsyncClient() as client:
                resposta = await provisorio._get(client, "/authentication")
        return bool(resposta and resposta.get("success") is True)

    async def verify(self, chave: str) -> TitleAvailability | None:
        """Busca de teste com a chave, sem adotá-la.

        Provar o caminho inteiro — busca e provedores — é o que dá o veredito
        útil: uma chave válida ainda pode não devolver nada de útil se a região
        estiver configurada errada.
        """
        provisorio = TmdbCatalog(
            api_key=chave,
            region=self.region,
            language=self.language,
            client=self._client,
            timeout=self._timeout,
        )
        return await provisorio.lookup("Interestelar")

    async def provider_ids(self) -> dict[Platform, int]:
        """Id de cada serviço na região, resolvido pelo nome.

        Pelo nome e não por número fixo: os ids mudam por região, e o do Max já
        mudou quando a HBO renomeou o serviço. Medido na região BR hoje —
        Netflix 8, Prime 119, Disney+ 337, Max 1899 —, mas nada disso está
        escrito no código.
        """
        if self._provider_ids is not None:
            return self._provider_ids
        if not self.enabled:
            return {}

        async def resolver(client: httpx.AsyncClient) -> dict[Platform, int]:
            resposta = await self._get(
                client,
                "/watch/providers/movie",
                language=self.language,
                watch_region=self.region,
            )
            if resposta is None:
                return {}
            encontrados: dict[Platform, int] = {}
            for provedor in resposta.get("results") or []:
                if not isinstance(provedor, dict):
                    continue
                plataforma = platform_for_provider(provedor.get("provider_name") or "")
                identificador = provedor.get("provider_id")
                if plataforma and isinstance(identificador, int):
                    encontrados.setdefault(plataforma, identificador)
            return encontrados

        if self._client is not None:
            achados = await resolver(self._client)
        else:
            async with httpx.AsyncClient() as client:
                achados = await resolver(client)

        if achados:
            self._provider_ids = achados
        return achados

    async def highlights(self, platform: Platform, limit: int = 12) -> list[Destaque]:
        """Os títulos em alta num serviço, com pôster.

        Só assinatura (`flatrate`): a tela é para escolher o que assistir hoje,
        não para descobrir o que dá para alugar.
        """
        if not self.enabled:
            return []
        identificador = (await self.provider_ids()).get(platform)
        if identificador is None:
            return []

        async def buscar(client: httpx.AsyncClient) -> list[Destaque]:
            resposta = await self._get(
                client,
                "/discover/movie",
                language=self.language,
                watch_region=self.region,
                with_watch_providers=identificador,
                watch_monetization_types="flatrate",
                sort_by="popularity.desc",
                include_adult="false",
            )
            if resposta is None:
                return []
            saida: list[Destaque] = []
            for item in (resposta.get("results") or [])[: limit * 2]:
                if not isinstance(item, dict):
                    continue
                poster = self._poster_of(item)
                # Sem pôster o cartão vira um retângulo vazio; a tela é feita
                # de capas, então um título sem capa não tem o que mostrar.
                if poster is None:
                    continue
                saida.append(Destaque(
                    title=self._title_of(item),
                    year=self._year_of(item),
                    poster_url=poster,
                ))
                if len(saida) >= limit:
                    break
            return saida

        if self._client is not None:
            return await buscar(self._client)
        async with httpx.AsyncClient() as client:
            return await buscar(client)

    async def _get(self, client: httpx.AsyncClient, path: str, **params) -> dict | None:
        try:
            response = await client.get(
                f"{API_BASE}{path}",
                params={"api_key": self.api_key, **params},
                timeout=self._timeout,
            )
        except httpx.HTTPError:
            return None
        if response.status_code != 200:
            return None
        try:
            payload = response.json()
        except ValueError:
            return None
        return payload if isinstance(payload, dict) else None

    # ── Geração progressiva de candidatos ─────────────────────────────────
    #
    # Mais recall NÃO é varrer o TMDB. É pedir na ordem certa e parar cedo:
    #
    #   1. /search/movie + /search/tv, página 1, com ano quando houver
    #   2. só se ainda não houver candidato forte: página 2
    #   3. só então, e só se o título original diferir: busca por ele
    #
    # Medido em 15/08/2026: `/search/multi` — o endpoint que era usado — não
    # trazia "O Rei"/"The King" (2019) nem na página 3 de 57. Em
    # `/search/movie` ele está na página 2, posição 6; com `primary_release_year`
    # sobe para a 3ª da página 1. Não faltava varrer mais: faltava perguntar
    # direito.
    PAGINAS_MAXIMAS = 2

    async def gerar_candidatos(
        self,
        client: httpx.AsyncClient,
        observado: Observado,
        associado: int | None = None,
    ) -> list[Candidato]:
        achados: dict[tuple[str, int], Candidato] = {}

        async def colher(consulta: str, caminho: str, tipo: str, pagina: int, **extra) -> None:
            resposta = await self._get(
                client, caminho,
                query=consulta, language=self.language,
                include_adult="false", page=pagina, **extra,
            )
            for item in (resposta or {}).get("results") or []:
                if not isinstance(item, dict) or not isinstance(item.get("id"), int):
                    continue
                achados.setdefault(
                    (tipo, item["id"]), self._como_candidato(item, tipo),
                )

        async def rodada(consulta: str, pagina: int) -> None:
            # O ano só entra na busca de FILME: em série a data de estreia é a
            # da primeira temporada, que raramente é o ano que o serviço mostra.
            ano = (
                {"primary_release_year": observado.ano}
                if observado.ano is not None else {}
            )
            await colher(consulta, "/search/movie", "MOVIE", pagina, **ano)
            await colher(consulta, "/search/tv", "TV", pagina)

        def avaliar() -> list:
            # Com a identidade guardada em mãos, ela entra já na avaliação: se o
            # id associado aparecer na primeira página, a expansão para aí. É
            # exatamente o ponto de guardar a associação — não repetir a busca
            # frágil por título.
            return [classificar(c, observado, associado) for c in achados.values()]

        def ja_basta() -> bool:
            return tem_candidato_forte(avaliar())

        for pagina in range(1, self.PAGINAS_MAXIMAS + 1):
            await rodada(observado.titulo, pagina)
            if ja_basta():
                return list(achados.values())

        # Estágio final: o recuo por encurtamento, que já existia e continua
        # ganhando o que ganhava. A busca do TMDB é literal — medido, "Batman:
        # Cruzado e Encapuzado" (com o "e", que é como o serviço mostra) não
        # devolve nada, e "Batman: Cruzado Encapuzado" devolve.
        #
        # Encurtar era perigoso: foi assim que "Prime Video: Batman" virou a
        # consulta "Prime Video" e trouxe um evento de boxe. Antes o perigo era
        # contido por uma checagem à parte (`_fala_do_mesmo_item`); agora ele é
        # contido pela ESTRUTURA — o que vier de uma consulta encurtada ainda
        # tem de responder ao título ORIGINAL para sair de `Nivel.NENHUM`. O
        # ranking é o guarda, e ele não pode ser esquecido como uma checagem
        # pode.
        for tentativa in self._tentativas(observado.titulo)[1:]:
            # A grafia literal já achou alguém pelo nome inteiro: encurtar daqui
            # em diante só acrescenta ruído.
            if tem_casamento_exato(avaliar()):
                break
            await rodada(tentativa, 1)

        return list(achados.values())

    # Quantas opções a tela oferece. Duas, e não uma: "The Gentlemen" é um
    # filme de 2020 E uma série de 2024, e escolher por conta própria acerta
    # metade das vezes. Quem sabe qual quer é quem digitou.
    OPCOES_MAXIMAS = 2

    def _melhores_candidatos(
        self, candidatos: list[Candidato], observado: Observado,
    ) -> list[Candidato]:
        """As melhores opções para oferecer — no máximo uma de cada tipo.

        Diferente de `resolver`, e a diferença é o propósito. `resolver`
        responde "qual é esta obra?" e tem o direito de recusar quando não dá
        para saber; aqui a pergunta é "o que mostrar para a pessoa escolher?", e
        recusar seria devolver uma tela vazia para uma busca que tem resposta.

        Então a ambiguidade, que lá é motivo de recusa, aqui é o resultado: as
        duas obras vão para a tela e quem decide é quem digitou.
        """
        avaliados = [
            a for a in (classificar(c, observado) for c in candidatos)
            if a.nivel != Nivel.NENHUM
        ]
        if not avaliados:
            return []

        # Nível primeiro, fama depois — a mesma ordem do resolver. Sem isso "O
        # Rei Leão", cinco vezes mais popular, ganharia de "O Rei".
        avaliados.sort(key=lambda a: (a.nivel, -a.candidato.popularidade))

        # A primeira vaga é do melhor casamento. A segunda é do mais FAMOSO
        # entre o resto — e as duas perguntas são diferentes de propósito.
        #
        # Medido em 19/08/2026: "Capitão América" casa exato com o filme de
        # 1990, que por nível ganha do "Capitão América: O Primeiro Vingador"
        # da Marvel. E o de 1990 é uma resposta legítima: é literalmente o
        # nome. Mas quase ninguém quer ele.
        #
        # Deixar a fama mandar na primeira vaga estragaria o caso oposto: "O
        # Rei" devolveria "O Rei Leão", cinco vezes mais popular. Então a fama
        # não desempata quem vence — ela decide o que mais aparece ao lado.
        primeiro = avaliados[0].candidato
        escolhidos = [primeiro]

        # Qualquer um que ainda RESPONDA à consulta — `avaliados` já descartou
        # os que não respondem. Sem corte de nível: medido, "Marvel - O
        # Justiceiro" casa só pela palavra que os dois dividem, e é exatamente
        # a segunda opção que a pessoa quer ver ao lado do filme de 2004.
        restantes = [
            a.candidato for a in avaliados
            if a.candidato.tmdb_id != primeiro.tmdb_id
        ]
        if restantes:
            escolhidos.append(max(restantes, key=lambda c: c.popularidade))
        return escolhidos[:self.OPCOES_MAXIMAS]

    def _como_item(self, candidato: Candidato) -> dict:
        """De volta ao formato de item da API, que é o que o resto espera."""
        return {
            "media_type": "tv" if candidato.tipo == "TV" else "movie",
            "id": candidato.tmdb_id,
            "title": candidato.titulo,
            "name": candidato.titulo,
            "poster_path": candidato.poster_path,
            "genre_ids": list(candidato.genre_ids),
            "popularity": candidato.popularidade,
            **(
                {"release_date": f"{candidato.ano}-01-01"}
                if candidato.ano and candidato.tipo == "MOVIE" else {}
            ),
            **(
                {"first_air_date": f"{candidato.ano}-01-01"}
                if candidato.ano and candidato.tipo == "TV" else {}
            ),
        }

    def _como_candidato(self, item: dict, tipo: str) -> Candidato:
        return Candidato(
            tmdb_id=item["id"],
            tipo=tipo,
            titulo=self._title_of(item),
            nomes=self._nomes_de(item),
            ano=self._year_of(item),
            popularidade=float(item.get("popularity") or 0.0),
            poster_path=item.get("poster_path") if isinstance(
                item.get("poster_path"), str,
            ) else None,
            genre_ids=tuple(
                i for i in (item.get("genre_ids") or []) if isinstance(i, int)
            ),
        )

    #: Quantas temporadas vale a pena varrer atrás do episódio. Séries com mais
    #: do que isto são raras, e o custo é uma requisição por temporada.
    TEMPORADAS_MAXIMAS = 30

    async def temporada_do_episodio(
        self,
        serie: str,
        episodio_nome: str | None = None,
        episodio_numero: int | None = None,
        duracao: float | None = None,
    ) -> int | None:
        """De que temporada é este episódio, quando o serviço não diz.

        ## Por que isto existe

        A Netflix publica "E1" e nada mais quando já se sabe em que temporada se
        está — medido em 26/08/2026 com Breaking Bad, e confirmado pelo usuário:
        a temporada não está em lugar nenhum da página. Inventar "T1" erraria
        justamente para quem está na quinta.

        Mas o catálogo SABE. Ele conhece a série inteira, e o que está tocando
        deixa pistas suficientes para achar a linha certa. Medido contra a API:

            T1 E1  runtime=59min  nome='Piloto'
            T2 E1  runtime=48min  nome='Seven Thirty-Seven'
            T3 E1  runtime=48min  nome='Chega!'
            T4 E1  runtime=48min  nome='Estilete'
            T5 E1  runtime=43min  nome='Viva Livre ou Morra'

        ## A regra: responder só quando a resposta é ÚNICA

        Isto NÃO é palpite disfarçado, e a diferença está no critério de saída.
        Um palpite escolhe o mais provável; aqui, se sobrar mais de um
        candidato, a resposta é `None` e a tela continua mostrando só "E1".

            nome do episódio    o sinal forte. "Piloto" aparece em UMA linha da
                                série inteira. Quando o nome isola um episódio,
                                a temporada dele é a resposta.

            duração             desempata só quando isola. 58min contra 59/48/
                                48/48/43 aponta a T1 sem dúvida; mas se a pessoa
                                estivesse na T2, as três de 48min seriam
                                indistinguíveis — e aí a resposta é `None`.

        `None` também quando o catálogo está desligado, a série não é achada, ou
        a rede falha. Não saber a temporada é o estado normal, não um erro.
        """
        achado = await self.numeros_do_episodio(
            serie, episodio_nome, episodio_numero, duracao,
        )
        return achado[0] if achado is not None else None

    async def numeros_do_episodio(
        self,
        serie: str,
        episodio_nome: str | None = None,
        episodio_numero: int | None = None,
        duracao: float | None = None,
    ) -> tuple[int, int] | None:
        """(temporada, episódio) do que está tocando, quando dá para isolar.

        O irmão mais útil de `temporada_do_episodio`, e a razão é que a maioria
        dos serviços NÃO publica número nenhum.

            Netflix                 publica "E1" — falta a temporada
            Max, Prime, Disney+     publicam só o NOME — "46 Long", "Ozymandias"

        Para os segundos, o nome sozinho responde as duas perguntas: achado o
        episódio na série, temporada e número vêm juntos. É o mesmo lookup, com
        a resposta inteira em vez de metade.

        As mesmas regras de recusa valem: nome repetido em duas temporadas sem
        duração que desempate devolve `None`, e não o primeiro.
        """
        if not self.enabled or not serie.strip():
            return None
        if episodio_nome is None and episodio_numero is None:
            return None
        if self._client is not None:
            return await self._temporada_com(
                self._client, serie, episodio_nome, episodio_numero, duracao,
            )
        async with httpx.AsyncClient() as client:
            return await self._temporada_com(
                client, serie, episodio_nome, episodio_numero, duracao,
            )

    async def _temporada_com(
        self,
        client: httpx.AsyncClient,
        serie: str,
        episodio_nome: str | None,
        episodio_numero: int | None,
        duracao: float | None,
    ) -> tuple[int, int] | None:
        identificador = await self._id_da_serie(client, serie)
        if identificador is None:
            return None

        episodios = await self._episodios_da_serie(client, identificador)
        if not episodios:
            return None

        def resposta(episodio: dict) -> tuple[int, int]:
            return episodio["temporada"], episodio["episodio"]

        candidatos = episodios
        if episodio_numero is not None:
            candidatos = [e for e in candidatos if e["episodio"] == episodio_numero]

        # O nome isola melhor do que qualquer outra coisa, e por isso vem antes.
        if episodio_nome is not None:
            alvo = normalizar(episodio_nome)
            por_nome = [e for e in candidatos if normalizar(e["nome"]) == alvo]
            if len(por_nome) == 1:
                return resposta(por_nome[0])
            if por_nome:
                candidatos = por_nome

        if len(candidatos) == 1:
            return resposta(candidatos[0])

        # A duração desempata SÓ quando isola. Dois episódios de 48 minutos
        # continuam sendo dois, e responder ali seria escolher por sorte.
        if duracao is not None and candidatos:
            minutos = duracao / 60.0
            perto = [
                e for e in candidatos
                if e["duracao"] is not None and abs(e["duracao"] - minutos) <= 2.0
            ]
            if len(perto) == 1:
                return resposta(perto[0])
        return None

    async def _id_da_serie(self, client: httpx.AsyncClient, serie: str) -> int | None:
        resposta = await self._get(
            client, "/search/tv", query=serie.strip(), language=self.language,
        )
        alvo = normalizar(serie)
        resultados = (resposta or {}).get("results") or []
        # Casamento de nome antes de fama: "The Office" tem versões, e a mais
        # popular não é necessariamente a que está tocando. Sem casamento
        # exato, o primeiro — que é o palpite do próprio TMDB.
        for item in resultados:
            nomes = (item.get("name"), item.get("original_name"))
            if any(n and normalizar(n) == alvo for n in nomes):
                return item.get("id") if isinstance(item.get("id"), int) else None
        primeiro = resultados[0].get("id") if resultados else None
        return primeiro if isinstance(primeiro, int) else None

    async def _episodios_da_serie(
        self, client: httpx.AsyncClient, identificador: int,
    ) -> list[dict]:
        """Todos os episódios, com temporada, número, nome e duração.

        Uma requisição por temporada. Cara o bastante para o chamador ter de
        guardar o resultado — ver `Dispatcher._temporada_para`, que faz isso
        fora do laço e uma vez por série.
        """
        detalhe = await self._get(client, f"/tv/{identificador}", language=self.language)
        total = (detalhe or {}).get("number_of_seasons")
        if not isinstance(total, int) or total < 1:
            return []

        episodios: list[dict] = []
        for numero in range(1, min(total, self.TEMPORADAS_MAXIMAS) + 1):
            temporada = await self._get(
                client, f"/tv/{identificador}/season/{numero}", language=self.language,
            )
            for episodio in (temporada or {}).get("episodes") or []:
                if not isinstance(episodio, dict):
                    continue
                numero_do_episodio = episodio.get("episode_number")
                if not isinstance(numero_do_episodio, int):
                    continue
                duracao = episodio.get("runtime")
                episodios.append({
                    "temporada": numero,
                    "episodio": numero_do_episodio,
                    "nome": episodio.get("name") or "",
                    "duracao": float(duracao) if isinstance(duracao, (int, float)) else None,
                })
        return episodios

    #: Quantas opções a BUSCA oferece. Diferente de `OPCOES_MAXIMAS`, que serve
    #: para resolver o pôster de uma obra já conhecida — lá duas bastam porque a
    #: pergunta tem uma resposta certa. Aqui a pergunta é "o que você quis
    #: dizer?", e duas é pouco: medido com "lanterna verde", havia SEIS
    #: candidatos válidos e a tela mostrava dois.
    RESULTADOS_DA_BUSCA = 8

    async def buscar_para_escolha(
        self, query: str, limite: int | None = None,
    ) -> list[TitleAvailability]:
        """A busca da TELA — que é outra pergunta, e por isso outro caminho.

        ## As duas perguntas

            resolver / lookup      "qual é ESTA obra?" Tem uma resposta certa, e
                                   errar põe a capa do filme de 1989 no
                                   histórico de uma série. Rigor é o correto:
                                   `classificar` descarta quem não casa, e
                                   recusar é uma saída legítima.

            buscar_para_escolha    "o que você quis dizer?" Não tem resposta
                                   certa — tem uma LISTA, e quem decide é quem
                                   digitou. Descartar aqui é esconder.

        Usar o filtro de identidade como porteiro da busca foi o defeito.
        Medido em 25/08/2026 com "lanterna verde", contra a API real:

            Lanterna Verde (2011)               TITULO         mostrado
            Lanterna Verde: A Série Animada     SUBTITULO      mostrado
            Lanterna Verde: Primeiro Voo        SUBTITULO      descartado (corte em 2)
            Lanterna Verde: Cavaleiros Esmeralda SUBTITULO     descartado
            Lanterna Verde: Cuidado Com Meu Poder SUBTITULO    descartado
            Lanterna Mágica (1984)              PALAVRA_FORTE  descartado
            Lanternas (2026, HBO)               NENHUM         nem gerado

        A série da HBO que a pessoa queria chama-se "Lanternas" — o nome não
        contém "lanterna verde", então nem entrava na lista de candidatos, e se
        entrasse seria classificada NENHUM. Enquanto isso "Lanterna Mágica", um
        filme de 1984 sem relação, passava no filtro. O rigor estava protegendo
        a coisa errada.

        ## O que muda

        1. **Consulta mais larga.** A tentativa encurtada só rodava quando a
           completa voltava vazia. Aqui ela roda SEMPRE, e os dois conjuntos são
           unidos — é o que traz "Lanternas" para a mesa.
        2. **Nada é descartado por nível.** O TMDB já decidiu que aquilo responde
           à consulta; a ordem é nossa, o veto não.
        3. **Oito em vez de duas.**

        O que NÃO muda: `lookup` e `lookup_options` seguem intactos. O pôster do
        histórico continua sendo escolhido com o rigor de antes, porque lá a
        pergunta continua sendo a outra.
        """
        if not self.enabled or not query.strip():
            return []
        limite = limite or self.RESULTADOS_DA_BUSCA
        if self._client is not None:
            return await self._buscar_com(self._client, query, limite)
        async with httpx.AsyncClient() as client:
            return await self._buscar_com(client, query, limite)

    async def _buscar_com(
        self, client: httpx.AsyncClient, query: str, limite: int,
    ) -> list[TitleAvailability]:
        observado = Observado(titulo=query.strip())
        achados: dict[tuple[str, int], Candidato] = {}
        for candidato in await self.gerar_candidatos(client, observado):
            achados[(candidato.tipo, candidato.tmdb_id)] = candidato

        # A consulta larga, SEMPRE — e não só quando a estreita falha. É o que
        # alcança o título que não contém as palavras que a pessoa digitou.
        for largura in self._alargamentos(query):
            for candidato in await self.gerar_candidatos(client, Observado(titulo=largura)):
                achados.setdefault((candidato.tipo, candidato.tmdb_id), candidato)

        # A pré-seleção ainda é por nome e fama: `disponivel` custa uma
        # requisição por candidato, e são dezenas. Quem passa daqui é reavaliado
        # com os três critérios.
        ordenados = sorted(
            achados.values(),
            key=lambda c: -self._pontuar_na_busca(c, observado, disponivel=False),
        )

        # Uma folga acima do limite, porque a disputa final ainda vai mudar a
        # ordem: só depois de saber ONDE ASSISTIR dá para dizer quais valem as
        # vagas. Buscar isso para os sessenta candidatos seria sessenta
        # requisições por letra digitada.
        finalistas = ordenados[: limite * 2]

        # Em paralelo: são requisições independentes, e em série o usuário
        # esperaria a soma delas.
        providers = await asyncio.gather(*[
            self._get(
                client,
                f"/{'tv' if c.tipo == 'TV' else 'movie'}/{c.tmdb_id}/watch/providers",
            )
            for c in finalistas
        ])

        achados_com_onde = [
            (candidato, self._platforms_of(resposta))
            for candidato, resposta in zip(finalistas, providers)
        ]

        # O DESEMPATE FINAL: dá para assistir?
        #
        # Pedido pelo usuário em 25/08/2026, e a razão é boa demais para virar
        # heurística escondida: ele digitou "Capitão América" e recebeu o filme
        # de 1990, que não está em serviço nenhum. Um resultado que a pessoa não
        # tem como abrir não é um resultado — é uma linha na tela.
        #
        # DESEMPATE e não critério principal: dentro do mesmo degrau de
        # relevância, quem está disponível sobe. Entre degraus, não — senão um
        # filme irrelevante que por acaso está na Netflix passaria na frente da
        # obra que a pessoa nomeou.
        achados_com_onde.sort(
            key=lambda par: -self._pontuar_na_busca(
                par[0], observado, disponivel=bool(par[1]),
            ),
        )

        return [
            TitleAvailability(
                title=candidato.titulo,
                year=candidato.ano,
                poster_url=(
                    f"{IMAGE_BASE}{candidato.poster_path}"
                    if candidato.poster_path else None
                ),
                platforms=plataformas,
                kind="TV" if candidato.tipo == "TV" else "MOVIE",
            )
            for candidato, plataformas in achados_com_onde[:limite]
        ]

    # Os pesos da busca. Explícitos e num lugar só, porque a alternativa é o
    # `confidence: 0.98` que `contratos.py` existe para não repetir: um número
    # mágico no meio de uma expressão que ninguém sabe justificar depois.
    #
    # A escala é logarítmica na fama de propósito. A popularidade do TMDB vai de
    # 0 a centenas, e somá-la crua faria o campeão de fama vencer qualquer
    # relevância — "Lanternas", com 320, atropelaria "Lanterna Verde" para quem
    # digitou "lanterna verde". Em log, a distância entre 300 e 30 vale um
    # ponto, que é mais ou menos o que ela significa.
    PESO_NOME_EXATO = 3.0
    PESO_NOME_PARCIAL = 1.5
    PESO_DISPONIVEL = 1.5

    def _pontuar_na_busca(
        self, candidato: Candidato, observado: Observado, disponivel: bool,
    ) -> float:
        """Quanto este resultado merece a próxima vaga da lista.

        ## Por que pontuação, e não degraus

        Degraus rígidos dão dominância absoluta ao primeiro critério, e isso
        produziu duas telas ruins, as duas medidas em 25/08/2026 contra a API:

            "capitão américa"  →  os filmes de 1990, 1979 e 1944 no topo, os
                                  três fora de qualquer serviço, porque casam
                                  EXATO com o nome. Os da Marvel, que é o que
                                  qualquer pessoa quis dizer, ficavam abaixo.

            "lanterna verde"   →  um filme romeno de 1962 com fama 0,8 acima da
                                  série da HBO com fama 320, por meio degrau de
                                  heurística de texto.

        Nos dois casos um critério legítimo — casou exato, casou por palavra —
        estava anulando os outros dois em vez de somar com eles. Casar exato
        VALE; não vale tudo.

        ## Os três critérios, e por que cada um

            nome        o que a pessoa digitou. Casar exato pesa o dobro de
                        casar em parte — é o que mantém "Lanterna Verde" na
                        frente de "Lanternas", que é 24 vezes mais famosa.

            fama        a melhor previsão disponível de "o que as pessoas
                        querem dizer com esta palavra". Em log, para informar
                        sem mandar.

            disponível  pedido do usuário, e a razão é boa: um resultado que
                        ele não tem como abrir não é um resultado, é uma linha
                        na tela. Vale o mesmo que casar em parte — sobe muito,
                        e não passa por cima de quem tem o nome certo.

        Maior é melhor, ao contrário de `Nivel`.
        """
        import math

        nivel = classificar(candidato, observado).nivel
        if nivel <= Nivel.ALTERNATIVO:
            pontos = self.PESO_NOME_EXATO
        elif nivel <= Nivel.SUBTITULO:
            pontos = self.PESO_NOME_PARCIAL
        else:
            # `PALAVRA_FORTE` e `NENHUM` juntos: como PREVISÃO do que a pessoa
            # quis, os dois são igualmente fracos, e deixar essa distinção
            # decidir foi o que enterrou a série da HBO.
            pontos = 0.0

        pontos += math.log10(1.0 + max(0.0, candidato.popularidade))

        # O bônus de disponibilidade NÃO alcança quem não responde à consulta.
        #
        # Disponibilidade é desempate entre resultados relevantes; ela não pode
        # FABRICAR relevância. Sem esta trava, medido: "capitão américa"
        # devolvia "Jake e os Piratas da Terra do Nunca" — que não tem nada a
        # ver, e subiu só por estar no Disney+.
        #
        # O nível `NENHUM` continua podendo aparecer, e é assim que "Lanternas"
        # chega à lista: pela FAMA, que é o que de fato sugere que a pessoa
        # queria aquilo. Quem não tem nome nem fama não entra por estar num
        # serviço.
        if disponivel and nivel < Nivel.NENHUM:
            pontos += self.PESO_DISPONIVEL
        return pontos

    def _alargamentos(self, query: str) -> list[str]:
        """Consultas mais largas que a digitada, para alcançar o vizinho.

        Só a primeira palavra que vale alguma coisa. Duas seria quase a consulta
        original de novo; três palavras já é a original. E a primeira palavra é
        justamente a que sobrevive à tradução — "Green Lantern" virou "Lanterna
        Verde", "Lanterns" virou "Lanternas", e "lanterna" é o que os três
        dividem.

        Nada de plural nem de radical: mexer na palavra é onde a busca começa a
        inventar. O TMDB já casa "lanterna" com "Lanternas" sozinho.
        """
        palavras = [
            p.strip(":;,.-–—!?\"'") for p in query.strip().split()
            if _normalize(p) not in self._LIGACOES
        ]
        palavras = [p for p in palavras if len(p) >= 4]
        if len(palavras) < 2:
            return []
        return [palavras[0]]

    async def lookup(self, query: str) -> TitleAvailability | None:
        opcoes = await self.lookup_options(query)
        return opcoes[0] if opcoes else None

    async def lookup_options(self, query: str) -> list[TitleAvailability]:
        """As opções para a consulta, com onde assistir em cada uma.

        Uma só na maioria das vezes. Duas quando filme e série respondem
        igualmente bem — aí quem escolhe é o usuário, não a popularidade.

        Lista vazia em qualquer imprevisto: sem chave, sem rede, sem resultado,
        formato inesperado. Quem chama cai na escolha manual.
        """
        if not self.enabled or not query.strip():
            return []

        if self._client is not None:
            return await self._lookup_with(self._client, query)
        async with httpx.AsyncClient() as client:
            return await self._lookup_with(client, query)

    # Palavras que não ajudam a identificar nada e atrapalham a busca literal
    # do TMDB. Curta de propósito: cortar demais transforma um título em outro.
    _LIGACOES = {"e", "o", "a", "os", "as", "de", "da", "do", "the", "and", "of"}

    async def _procurar(self, client: httpx.AsyncClient, query: str) -> list[dict]:
        """Resultados da busca, com um recuo quando ela volta vazia.

        A busca do TMDB é literal: uma palavra a mais e a resposta é nada.
        Medido — "Batman: Cruzado Encapuzado" existe no catálogo, mas
        "Batman: Cruzado e Encapuzado" (com o "e", que é como o serviço mostra)
        não devolve nada. Nem "Batman: O Cruzado Encapuzado".

        O recuo é encurtar: as duas primeiras palavras que valem alguma coisa
        acham o título sem trocá-lo por outro. Três tentativas no máximo, e só
        quando a anterior falhou — o caminho normal continua custando uma
        requisição só.
        """
        for tentativa in self._tentativas(query):
            resposta = await self._get(
                client,
                "/search/multi",
                query=tentativa,
                language=self.language,
                region=self.region,
                include_adult="false",
            )
            resultados = (resposta or {}).get("results") or []
            uteis = [
                item for item in resultados
                if isinstance(item, dict) and item.get("media_type") in ("movie", "tv")
            ]
            # Na tentativa encurtada, o resultado ainda precisa falar do
            # mesmo que o nome original. Sem esta trava, "Prime Video: Batman"
            # virava a busca "Prime Video" e devolvia um evento de boxe com
            # toda a confiança do mundo — aconteceu, e a capa errada foi parar
            # na tela.
            #
            # A pergunta é "é sobre a mesma coisa?", e não "o texto bate?":
            # encurtar tira justamente os pedaços que fariam o texto bater.
            if tentativa != query.strip():
                uteis = [
                    item for item in uteis
                    if self._fala_do_mesmo_item(item, query)
                ]
            if uteis:
                return uteis
        return []

    def _tentativas(self, query: str) -> list[str]:
        limpo = query.strip()
        if not limpo:
            return []
        palavras = [p for p in limpo.split() if _normalize(p) not in self._LIGACOES]
        tentativas = [limpo]
        # Sem as ligações: "Batman: Cruzado e Encapuzado" -> "Batman: Cruzado
        # Encapuzado", que é exatamente como o catálogo escreve.
        sem_ligacoes = " ".join(palavras)
        if sem_ligacoes and sem_ligacoes != limpo:
            tentativas.append(sem_ligacoes)
        # E, por último, só o começo, sem pontuação: é o que sobra quando o
        # nome vem com subtítulo, temporada ou tradução diferente. Esta é a
        # tentativa mais frouxa das três, então os dois pontos saem também —
        # "Batman: Cruzado" vira "Batman Cruzado".
        if len(palavras) > 2:
            comeco = " ".join(p.strip(":;,.-–—!?\"'") for p in palavras[:2]).strip()
            if comeco and comeco not in tentativas:
                tentativas.append(comeco)
        return tentativas

    async def _lookup_with(
        self,
        client: httpx.AsyncClient,
        query: str,
    ) -> list[TitleAvailability]:
        # O MESMO motor que resolve o pôster do histórico: geração ampla e
        # ranking por nível. A busca ficou de fora quando o resolver entrou, e
        # continuou com o defeito que ele existe para corrigir — medido em
        # 19/08/2026 contra a API real:
        #
        #   "O Rei"           devolvia o homônimo de 2014
        #   "The king"        devolvia "The King" de 2017 e "O Rei do Bairro"
        #   "Capitão América" devolvia o filme de 1991
        #   "Flash"           devolvia "Flash" de 2018
        #
        # Nenhum desses é falta de ranking: o candidato certo não estava na
        # lista, porque `/search/multi` numa página só não o traz. Ver
        # `catalog/resolver.py`.
        observado = Observado(titulo=query.strip())
        candidatos = await self.gerar_candidatos(client, observado)
        escolhidos = [
            self._como_item(c) for c in self._melhores_candidatos(candidatos, observado)
        ]
        if not escolhidos:
            # Só agora, e nunca antes: medido contra a API, "Blade Runner 2049"
            # e "velozes e furiosos 7" já são achados pela busca normal, porque
            # o número faz parte do nome. Tentar a coleção primeiro estragaria
            # os dois. Quando a busca normal falha é que o número tem chance de
            # ser "o quinto da franquia" — que é o caso de "harry potter 5".
            da_colecao = await self._da_colecao(client, query)
            if da_colecao is None:
                return []
            escolhidos = [da_colecao]

        saida: list[TitleAvailability] = []
        for item in escolhidos:
            media_type = item.get("media_type")
            identifier = item.get("id")
            if media_type not in {"movie", "tv"} or not isinstance(identifier, int):
                continue
            providers = await self._get(
                client, f"/{media_type}/{identifier}/watch/providers",
            )
            saida.append(TitleAvailability(
                title=self._title_of(item),
                year=self._year_of(item),
                poster_url=self._poster_of(item),
                platforms=self._platforms_of(providers),
                kind="TV" if media_type == "tv" else "MOVIE",
            ))
        return saida

    async def _da_colecao(self, client: httpx.AsyncClient, query: str) -> dict | None:
        """"harry potter 5" → o quinto filme da franquia, por data de estreia.

        Ninguém decora "Harry Potter e a Ordem da Fênix"; todo mundo sabe que é
        o quinto. O TMDB agrupa franquias em coleções, e a ordem de estreia é o
        que a pessoa quer dizer com o número.
        """
        separado = _NUMERO_NO_FIM.fullmatch(query.strip())
        if separado is None:
            return None

        posicao = int(separado.group("numero"))
        # Acima de vinte é quase certamente um ano ou parte do nome.
        if not 2 <= posicao <= 20:
            return None

        busca = await self._get(
            client,
            "/search/collection",
            query=separado.group("franquia"),
            language=self.language,
        )
        if busca is None:
            return None
        colecoes = busca.get("results")
        if not isinstance(colecoes, list) or not colecoes:
            return None
        identificador = colecoes[0].get("id")
        if not isinstance(identificador, int):
            return None

        detalhe = await self._get(client, f"/collection/{identificador}", language=self.language)
        if detalhe is None:
            return None

        partes = [
            parte for parte in (detalhe.get("parts") or [])
            if isinstance(parte, dict) and parte.get("release_date")
        ]
        # Por data de estreia, não pela ordem que a API devolveu: é a ordem em
        # que as pessoas contam os filmes.
        partes.sort(key=lambda parte: parte["release_date"])
        if len(partes) < posicao:
            return None

        escolhido = partes[posicao - 1]
        return {**escolhido, "media_type": "movie"}

    @staticmethod
    def _fala_do_mesmo(titulo: str, consulta: str) -> bool:
        """Os dois nomes dividem alguma palavra que identifica alguma coisa?

        Palavra de peso é a que tem quatro letras ou mais: "de", "the" e "e"
        aparecem em metade do catálogo e não provam nada. Basta uma — os
        catálogos traduzem o resto ("Caped Crusader" virou "Cruzado
        Encapuzado", e só "Batman" sobreviveu à tradução).
        """
        def palavras(texto: str) -> set[str]:
            limpas = (p.strip(":,.-!?\"'") for p in _normalize(texto).split())
            # O nome do serviço não identifica obra nenhuma: "Prime Video
            # Boxing" e "Prime Video: Batman" dividem duas palavras longas e não
            # têm nada a ver um com o outro.
            return {p for p in limpas if len(p) >= 4} - _NOMES_DE_SERVICO

        das_duas = palavras(titulo) & palavras(consulta)
        # Consulta sem nenhuma palavra longa (um nome curto como "Duna") não
        # tem como ser comparada assim; nesse caso, não barra nada.
        return bool(das_duas) or not palavras(consulta)

    @staticmethod
    def quanto_casa(titulo: str, consulta: str) -> int:
        """O quanto o título responde ao que foi digitado.

        Medido contra a API: ordenar só por popularidade erra feio. "the boys"
        traz o filme "Os Garotos Perdidos" — que não tem nada a ver — junto com
        a série certa, e o filme podia ganhar. Comparar o texto resolve isso
        sem inventar preferência por filme nem por série.
        """
        t, c = _normalize(titulo), _normalize(consulta)
        if not t or not c:
            return 0
        if t == c:
            return 3
        if t.startswith(c):
            return 2
        if c in t:
            return 1
        # Quase igual conta. Sem isto, uma letra de diferença zerava o título
        # certo: "the gentleman" não está contido em "the gentlemen", e o filme
        # do Guy Ritchie sumia em favor de um homônimo de 2000. Vale também
        # para acento perdido e plural trocado, que é como as pessoas digitam.
        if SequenceMatcher(None, t, c).ratio() >= 0.9:
            return 2
        # E para o caso de subtítulo: "the gentlemen" dentro de "the gentlemen:
        # a nova ordem" já é coberto acima; aqui é o contrário — o começo do
        # título quase igual ao que foi digitado.
        comeco = t[: len(c)]
        return 1 if SequenceMatcher(None, comeco, c).ratio() >= 0.9 else 0

    def _melhor_de_cada_tipo(self, results, query: str) -> tuple[dict | None, dict | None]:
        """(melhor, alternativa) para a consulta — a alternativa some quando
        o outro tipo não responde ao que foi digitado."""
        candidatos = [
            item for item in (results or [])
            if isinstance(item, dict) and item.get("media_type") in {"movie", "tv"}
        ]
        if not candidatos:
            return None, None

        def melhor(tipo: str) -> dict | None:
            do_tipo = [i for i in candidatos if i.get("media_type") == tipo]
            if not do_tipo:
                return None
            return max(
                do_tipo,
                key=lambda i: (
                    self._casa_com(i, query),
                    i.get("popularity") or 0,
                ),
            )

        filme, serie = melhor("movie"), melhor("tv")
        if filme is None or serie is None:
            return filme, serie

        pontos_filme = self._casa_com(filme, query)
        pontos_serie = self._casa_com(serie, query)

        # Um dos dois não responde à consulta: é ruído e sai. Medido — "the
        # boys" traz o filme "Os Garotos Perdidos", que não tem nada a ver.
        if pontos_filme == 0:
            return None, serie
        if pontos_serie == 0:
            return filme, None

        # Os dois respondem: os dois voltam, o melhor primeiro. Quem decide é
        # o contexto de quem chamou — a tela pergunta ao usuário, e o cartão
        # de "tocando agora" escolhe pela plataforma que está aberta.
        return (filme, serie) if pontos_filme >= pontos_serie else (serie, filme)

    def _best_result(self, results) -> dict | None:
        """Mais popular entre filme e série.

        O `/search/multi` devolve pessoas junto, e um ator costuma vir acima do
        filme quando o nome bate — daí o filtro por tipo antes da ordenação.
        """
        if not isinstance(results, list):
            return None
        candidates = [
            item for item in results
            if isinstance(item, dict) and item.get("media_type") in {"movie", "tv"}
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda item: item.get("popularity") or 0)

    @staticmethod
    def _title_of(item: dict) -> str:
        for key in ("title", "name", "original_title", "original_name"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return "Título desconhecido"

    @staticmethod
    def _nomes_de(item: dict) -> tuple[str, ...]:
        """Todos os nomes pelos quais a obra pode ser chamada.

        O de exibição e o original, porque raramente são o mesmo. Medido contra
        a API: "The Gentlemen", do Guy Ritchie, chega em PRIMEIRO lugar na busca
        por esse nome — mas com `title` "Magnatas do Crime", que é como o Brasil
        rebatizou. Comparar só com o nome traduzido dava zero, e a regra que
        descarta os zerados jogava fora justamente o resultado certo.

        Não é um caso isolado: na mesma resposta vieram "Um Distinto Cavalheiro"
        e "A Liga Extraordinária". E o nome que a pessoa digita é o que ela viu
        na tela do serviço — a Netflix mostra "The Gentlemen", em inglês.

        Vem de graça: o `/search/multi` já devolve os dois no mesmo item.
        """
        nomes: list[str] = []
        for chave in ("title", "name", "original_title", "original_name"):
            valor = item.get(chave)
            if isinstance(valor, str) and valor.strip() and valor.strip() not in nomes:
                nomes.append(valor.strip())
        return tuple(nomes)

    def _casa_com(self, item: dict, consulta: str) -> int:
        """A melhor pontuação entre os nomes da obra.

        A melhor e não a do nome de exibição: basta um dos nomes responder ao
        que foi digitado para a obra ser a certa.
        """
        return max(
            (self.quanto_casa(nome, consulta) for nome in self._nomes_de(item)),
            default=0,
        )

    def _fala_do_mesmo_item(self, item: dict, consulta: str) -> bool:
        """Algum dos nomes da obra fala do mesmo que a consulta?"""
        return any(
            self._fala_do_mesmo(nome, consulta)
            for nome in self._nomes_de(item) or (self._title_of(item),)
        )

    @staticmethod
    def _year_of(item: dict) -> int | None:
        for key in ("release_date", "first_air_date"):
            value = item.get(key)
            if isinstance(value, str) and len(value) >= 4 and value[:4].isdigit():
                return int(value[:4])
        return None

    @staticmethod
    def _poster_of(item: dict) -> str | None:
        path = item.get("poster_path")
        return f"{IMAGE_BASE}{path}" if isinstance(path, str) and path else None

    def _platforms_of(self, providers: dict | None) -> list[Platform]:
        if providers is None:
            return []
        results = providers.get("results")
        if not isinstance(results, dict):
            return []
        region = results.get(self.region)
        if not isinstance(region, dict):
            return []

        found: list[Platform] = []
        # Só assinatura: "rent" e "buy" levariam a pessoa a uma tela de compra
        # quando ela só queria assistir.
        for entry in region.get("flatrate") or []:
            if not isinstance(entry, dict):
                continue
            name = entry.get("provider_name")
            if not isinstance(name, str):
                continue
            platform = platform_for_provider(name)
            if platform is not None and platform not in found:
                found.append(platform)
        return found

    async def detalhes_de(
        self,
        titulo: str,
        ano: int | None = None,
        tipo: str | None = None,
        provider: str | None = None,
        provider_content_id: str | None = None,
    ) -> tuple[str | None, tuple[str, ...]]:
        """Pôster e gêneros da obra — ou nada, quando não dá para afirmar qual é.

        `ano` e `tipo` são opcionais porque hoje quase nunca se sabem: a janela
        do navegador dá só o nome. Quando chegarem — pelo Browser Media Bridge,
        que já lê a aba — eles transformam um palpite num casamento
        determinístico. Medido: para "O Rei", o ano leva a escolha de
        `Nivel.TITULO` (desempate por fama) para `Nivel.TITULO_ANO_TIPO`.

        `provider` e `provider_content_id` são o id da obra DENTRO do serviço.
        Não é um id do TMDB e não vira um por decreto — mas, uma vez que a
        resolução por título tenha decidido com segurança, a ligação fica
        guardada e a busca frágil não se repete. Ver `identidades.py`.
        """
        if not self.enabled or not titulo.strip():
            return None, ()

        async def buscar(client: httpx.AsyncClient) -> tuple[str | None, tuple[str, ...]]:
            # Geração ampla, ranking determinístico, e o direito de não decidir.
            #
            # O caminho antigo pegava o primeiro resultado que "falasse do
            # mesmo" — e isso deixou "O Rei" com o pôster do homônimo de 2014 e
            # "Prime Video: Batman" com o de um evento de boxe. Aqui, empate sem
            # desempate vira ENRIQUECIMENTO NENHUM: melhor um título sem capa do
            # que um título com a capa de outra obra e o histórico contaminado.
            observado = Observado(
                titulo=titulo.strip(), ano=ano, tipo=tipo,
                provider=provider, providerContentId=provider_content_id,
            )
            associado = self._identidades.tmdb_de(provider, provider_content_id)
            candidatos = await self.gerar_candidatos(client, observado, associado)
            escolha = resolver(candidatos, observado, associado)
            if not isinstance(escolha, Escolhido):
                return None, ()

            # Só se guarda o que foi decidido por algo além do nome. Uma
            # associação errada aqui é PIOR do que nenhuma: ela vira identidade
            # e passa a ganhar de todo o resto, inclusive de uma resolução
            # futura melhor informada.
            if escolha.nivel <= Nivel.TITULO_TIPO:
                self._identidades.associar(
                    provider, provider_content_id,
                    escolha.candidato.tmdb_id,
                    escolha.candidato.tipo,
                    escolha.candidato.titulo,
                )

            # Os gêneros já vieram na busca, como ids. Traduzi-los pelo mapa —
            # que é resolvido uma vez por execução — custa zero requisição a
            # mais; pedir o detalhe da obra custaria uma por título.
            nomes = await self._nomes_dos_generos(client)
            generos = tuple(
                nomes[i] for i in escolha.candidato.genre_ids if i in nomes
            )
            poster = (
                f"{IMAGE_BASE}{escolha.candidato.poster_path}"
                if escolha.candidato.poster_path else None
            )
            return poster, generos

        if self._client is not None:
            return await buscar(self._client)
        async with httpx.AsyncClient() as client:
            return await buscar(client)

    async def generos_de(self, titulo: str) -> tuple[str, ...]:
        """Os gêneros de um título, pelo nome.

        Vem da mesma busca que já resolve disponibilidade: o `/search/multi`
        devolve `genre_ids` junto, e o mapa de nomes é fixo por idioma. Uma
        chamada a mais só para o mapa, e ele é resolvido uma vez por execução.
        """
        if not self.enabled or not titulo.strip():
            return ()

        async def buscar(client: httpx.AsyncClient) -> tuple[str, ...]:
            nomes = await self._nomes_dos_generos(client)
            if not nomes:
                return ()
            resposta = await self._get(
                client, "/search/multi", query=titulo.strip(),
                language=self.language, include_adult="false",
            )
            for item in (resposta or {}).get("results") or []:
                if not isinstance(item, dict) or item.get("media_type") == "person":
                    continue
                ids = item.get("genre_ids")
                if not isinstance(ids, list):
                    continue
                return tuple(nomes[i] for i in ids if i in nomes)
            return ()

        if self._client is not None:
            return await buscar(self._client)
        async with httpx.AsyncClient() as client:
            return await buscar(client)

    async def _nomes_dos_generos(self, client: httpx.AsyncClient) -> dict[int, str]:
        if self._generos is not None:
            return self._generos
        nomes: dict[int, str] = {}
        for caminho in ("/genre/movie/list", "/genre/tv/list"):
            resposta = await self._get(client, caminho, language=self.language)
            for genero in (resposta or {}).get("genres") or []:
                if isinstance(genero, dict) and isinstance(genero.get("id"), int):
                    nome = genero.get("name")
                    if isinstance(nome, str) and nome:
                        nomes[genero["id"]] = nome
        self._generos = nomes
        return nomes

    async def parecidos_com(
        self, titulo: str, plataformas: list[Platform], limite: int = 12,
    ) -> list[Destaque]:
        """"Porque você assistiu X": o que o TMDB associa a esse título.

        Filtrado pelos serviços que a pessoa realmente tem. Sem esse filtro a
        lista viraria o que toda lista de recomendação genérica é — cheia de
        títulos que ela não pode assistir sem assinar mais alguma coisa.
        """
        if not self.enabled or not titulo.strip():
            return []

        async def buscar(client: httpx.AsyncClient) -> list[Destaque]:
            achado = await self._get(
                client, "/search/multi", query=titulo.strip(),
                language=self.language, include_adult="false",
            )
            base = next(
                (
                    item for item in (achado or {}).get("results") or []
                    if isinstance(item, dict) and item.get("media_type") in ("movie", "tv")
                ),
                None,
            )
            if base is None:
                return []

            tipo = "movie" if base.get("media_type") == "movie" else "tv"
            resposta = await self._get(
                client, f"/{tipo}/{base.get('id')}/recommendations",
                language=self.language,
            )
            permitidas = set(plataformas)
            saida: list[Destaque] = []
            for item in (resposta or {}).get("results") or []:
                if not isinstance(item, dict):
                    continue
                poster = self._poster_of(item)
                if poster is None:
                    continue
                if permitidas:
                    provedores = await self._get(
                        client, f"/{tipo}/{item.get('id')}/watch/providers",
                    )
                    if not permitidas.intersection(self._platforms_of(provedores)):
                        continue
                saida.append(Destaque(
                    title=self._title_of(item),
                    year=self._year_of(item),
                    poster_url=poster,
                ))
                if len(saida) >= limite:
                    break
            return saida

        if self._client is not None:
            return await buscar(self._client)
        async with httpx.AsyncClient() as client:
            return await buscar(client)
