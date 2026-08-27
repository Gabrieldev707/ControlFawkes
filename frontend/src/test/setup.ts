import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'


afterEach(() => {
  cleanup()
  // A tela atual é guardada em `sessionStorage` para sobreviver ao recarregar
  // da aba no iPhone. Num arquivo de teste isso vaza de um caso para o
  // seguinte: o segundo teste começava na tela onde o primeiro parou, e os
  // atalhos da tela inicial simplesmente não estavam lá.
  sessionStorage.clear()

  // E o pareamento, que passou a morar em cookie para atravessar a troca de
  // porta (ver `dispositivoGuardado.ts`). Cookie é justamente a gaveta que NÃO
  // é limpa por `localStorage.clear()`, e no Windows a suíte roda com
  // `isolate: false` — um jsdom para todos os arquivos. Sem esta linha, um
  // aparelho pareado num arquivo aparece pareado nos seguintes, e o teste que
  // verifica a tela de pareamento não a encontra.
  //
  // Vale como aviso do mundo real, não só do teste: cookie gruda mais.
  for (const pedaco of document.cookie.split(';')) {
    const nome = pedaco.split('=')[0]?.trim()
    if (nome) document.cookie = `${nome}=; Path=/; Max-Age=0; SameSite=Lax`
  }
})
