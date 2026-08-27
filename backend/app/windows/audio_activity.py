"""Está saindo som deste aplicativo agora?

Por que isto existe: quando a API de mídia do Windows não responde, o que sobra
é a janela aberta — e uma janela aberta não diz se o filme está rodando. O
código assumia que sim, porque "a janela está aberta e o usuário está
assistindo". Assumir isso custa caro: pausado, terminado ou esquecido em
segundo plano, tudo virava tempo assistido.

Medido nesta máquina: o Chrome com a sessão de áudio em `Inactive` — nenhum som
saindo — enquanto "Batman: Caped Crusader" somava um segundo por segundo e
chegava a 129 minutos no catálogo.

A Core Audio responde essa pergunta sem depender da API de mídia, e responde
mesmo com ela travada. É a mesma fonte que o controle já usa para o volume por
aplicativo.

Limitação herdada, e a mesma de lá: o Chrome agrupa o áudio de todas as abas
numa sessão só. Se outra aba estiver tocando som, esta função diz "tocando" —
o que se mede é o processo, não a aba. Ainda assim é muito melhor do que supor
que sim para sempre.
"""

from __future__ import annotations

import sys


# Core Audio do Windows, `AudioSessionState` (audiopolicy.h):
#
#   AudioSessionStateInactive = 0
#   AudioSessionStateActive   = 1
#   AudioSessionStateExpired  = 2
#
# Estava em 2, que é Expired — uma sessão que morreu, não uma que toca. Medido
# ao vivo com o Disney+ reproduzindo: `chrome.exe` em State=1 e esta função
# respondendo "não está tocando".
#
# O estrago era exatamente do tamanho do que esta função decide: com a SMTC
# travada, tudo que passa pelo navegador é lido pela janela, e a janela sozinha
# não sabe se está tocando — quem sabe é daqui. Respondendo False para quem
# está assistindo, o gravador tratava tudo como pausado ("pausado não acumula")
# e uma série inteira no Disney+ não virava um segundo de histórico.
ATIVO = 1


def processo_esta_tocando(nome_do_processo: str | None) -> bool | None:
    """True, False, ou None quando não dá para saber.

    None e não False: sem forma de medir, quem chama deve manter o palpite
    otimista de antes. Um controle que diz "pausado" para quem está assistindo
    é pior do que um que conta tempo demais.
    """
    if not nome_do_processo or sys.platform != "win32":
        return None

    try:
        import pythoncom
        from pycaw.pycaw import AudioUtilities
    except ImportError:
        return None

    procurado = nome_do_processo.strip().lower()
    try:
        pythoncom.CoInitialize()
        try:
            sessoes = list(AudioUtilities.GetAllSessions())
        finally:
            pythoncom.CoUninitialize()
    except Exception:  # noqa: BLE001 - áudio indisponível não derruba o cartão
        return None

    encontrou = False
    for sessao in sessoes:
        processo = getattr(sessao, "Process", None)
        if processo is None:
            continue
        try:
            nome = processo.name().lower()
        except Exception:  # noqa: BLE001 - processo pode morrer no meio
            continue
        if nome != procurado:
            continue
        encontrou = True
        try:
            if int(sessao.State) == ATIVO:
                return True
        except (TypeError, ValueError):
            return None

    # Achou o processo e nenhuma sessão dele estava ativa: está calado.
    # Não achou sessão nenhuma: o aplicativo nunca tocou nada, o que dá no
    # mesmo. Os dois casos são "não está tocando", e não "não sei".
    return False if encontrou or sessoes else None
