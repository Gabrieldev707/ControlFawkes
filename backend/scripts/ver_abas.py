"""Quantas observações de cada cenário o dataset da Fase 14 já tem.

    cd backend && .venv\\Scripts\\python.exe scripts/ver_abas.py

O gate da Fase 14 pede "dataset real coletado", e o da Fase 15 depende dele:
"nenhuma política congelada antes dos dados". Este script responde a única
pergunta que decide se dá para avançar — quais cenários já foram vistos de
verdade, e quais continuam em zero.

## Um aviso sobre os números históricos

`resumir()` conta o rótulo que foi GRAVADO em cada linha, e as linhas de antes
de 26/08/2026 foram rotuladas contando SESSÕES em vez de abas. Naquele momento
o estado da ponte deixava sessões fantasma vivas na mesma aba, e cada fantasma
virava uma aba a mais.

O efeito na leitura foi grosseiro:

                                contando sessões   contando ABAS
    instantes com 2+ tocando           477               18

As duas causas já foram corrigidas — `EstadoDaPonte._esquecer_a_mesma_aba` na
origem e `telemetria.uma_por_aba` no classificador —, então o dado NOVO está
certo. O velho não é reescrito: um dataset que se corrige sozinho depois do
fato deixa de ser registro do que aconteceu.

Por isso a coluna abaixo é um PISO, e não uma medida. O que ela decide bem é a
única coisa que ela precisa decidir: o cenário foi visto alguma vez, ou nunca?
"""

from __future__ import annotations

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.bridge.telemetria import CAMINHO_PADRAO, resumir  # noqa: E402


# Os cenários que o plano lista. Ficar em zero é informação, não ausência dela:
# é o que diz que a Fase 15 ainda não pode ser escrita.
ESPERADOS = (
    "duas-tocando",
    "background-tocando",
    "ativa-pausada-outra-tocando",
    "pip",
    "varias-janelas",
    "servicos-diferentes",
    "mesmo-servico",
)


def main() -> int:
    contagem = resumir()
    if not contagem:
        print(f"Nenhuma observação ainda em {CAMINHO_PADRAO}")
        print()
        print("O coletor só grava quando há DUAS ou mais abas com mídia ao mesmo")
        print("tempo — uma aba sozinha não tem ambiguidade a estudar.")
        return 0

    print(f"Dataset: {CAMINHO_PADRAO}")
    print(f"{sum(contagem.values())} observações\n")

    largura = max(len(nome) for nome in (*ESPERADOS, *contagem))
    for nome in ESPERADOS:
        quantas = contagem.get(nome, 0)
        marca = "  " if quantas else "! "
        print(f"{marca}{nome.ljust(largura)}  {quantas}")

    extras = {k: v for k, v in contagem.items() if k not in ESPERADOS}
    for nome, quantas in extras.items():
        print(f"  {nome.ljust(largura)}  {quantas}")

    faltando = [nome for nome in ESPERADOS if not contagem.get(nome)]
    print()
    if not faltando:
        print("Todos os cenários têm dados. O gate da Fase 14 pode fechar.")
        return 0

    print(f"Ainda sem dados ({len(faltando)}): {', '.join(faltando)}")
    print()
    if faltando == ["pip"]:
        # A Fase 15 FOI escrita, e escrita a partir dos outros seis cenários.
        # O que falta não é a política inteira: é a posição de UM sinal.
        print("A Fase 15 já foi escrita — com os cenários que existem, e sem")
        print("ranquear o Picture-in-Picture, que tem zero observações.")
        print()
        print("Ranquear um sinal sem nenhuma medição é como nasceu o")
        print("`confidence: 0.98` que `contratos.py` existe para não repetir.")
        print()
        print("O que acontece HOJE com PiP, para ninguém se surpreender:")
        print("  sozinha tocando ................. vence")
        print("  contra uma aba ATIVA tocando .... PERDE")
        print("E o segundo é justamente o caso que ele deveria ganhar.")
        print()
        print("Para fechar: duas abas com vídeo, uma delas em Picture-in-Picture")
        print("(botão direito no vídeo), por uns vinte segundos. Depois rode")
        print("este script de novo.")
    else:
        print("A Fase 15 não pode ser revista sem eles — a política não se")
        print("escreve antes dos dados que ela deveria explicar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
