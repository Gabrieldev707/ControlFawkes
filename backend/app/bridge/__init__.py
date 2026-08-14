"""A ponte entre o navegador e o ControlFawkes.

Fase 1 do Master Loop: aqui mora só o que os spikes de transporte precisam.
O Media Merger, os adapters e o histórico NÃO entram neste pacote — o host é
um relay, e um relay que ganha lógica de domínio deixa de ser testável fora do
Chrome.
"""
