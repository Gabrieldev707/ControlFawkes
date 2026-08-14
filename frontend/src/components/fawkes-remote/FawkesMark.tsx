import React from 'react'


/**
 * O nome desenhado em ASCII.
 *
 * Seis linhas monoespaçadas com sombra, o suficiente para o nome se ler de
 * longe — que é como um controle é olhado — sem comer o espaço do orb.
 *
 * Fica em `aria-hidden` porque um leitor de tela leria os blocos um a um; o
 * nome continua acessível pelo `<h1>` invisível ao lado.
 */
// Blocos com sombra. Cheguei a trocar por uma versão de traço fino, que era
// mais limpa de perto e perdia a presença que faz a marca funcionar de longe.
//
// A base do F fica aberta de propósito: fechá-la transforma a letra num E e o
// nome vira "EAWKES". Já aconteceu, e só a captura de tela pegou.
const ART = String.raw`███████╗ █████╗ ██╗    ██╗██╗  ██╗███████╗███████╗
██╔════╝██╔══██╗██║    ██║██║ ██╔╝██╔════╝██╔════╝
█████╗  ███████║██║ █╗ ██║█████╔╝ █████╗  ███████╗
██╔══╝  ██╔══██║██║███╗██║██╔═██╗ ██╔══╝  ╚════██║
██║     ██║  ██║╚███╔███╔╝██║  ██╗███████╗███████║
╚═╝     ╚═╝  ╚═╝ ╚══╝╚══╝ ╚═╝  ╚═╝╚══════╝╚══════╝`

export const FawkesMark: React.FC = () => (
  <>
    <h1 className="visually-hidden">ControlFawkes</h1>
    <pre className="fawkes-mark" aria-hidden="true">{ART}</pre>
  </>
)
