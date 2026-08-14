import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'


afterEach(() => {
  cleanup()
  // A tela atual é guardada em `sessionStorage` para sobreviver ao recarregar
  // da aba no iPhone. Num arquivo de teste isso vaza de um caso para o
  // seguinte: o segundo teste começava na tela onde o primeiro parou, e os
  // atalhos da tela inicial simplesmente não estavam lá.
  sessionStorage.clear()
})
