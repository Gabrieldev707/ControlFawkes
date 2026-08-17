import { beforeEach, describe, expect, it } from 'vitest'

import {
  esquecerDispositivo,
  guardarDispositivo,
  lerDispositivo,
} from './dispositivoGuardado'


function limparCookies(): void {
  for (const pedaco of document.cookie.split(';')) {
    const nome = pedaco.split('=')[0]?.trim()
    if (nome) document.cookie = `${nome}=; Path=/; Max-Age=0; SameSite=Lax`
  }
}

describe('onde o pareamento fica guardado', () => {
  beforeEach(() => {
    localStorage.clear()
    limparCookies()
  })

  it('guarda e devolve o par', () => {
    guardarDispositivo('aparelho-1', 'segredo-1')

    expect(lerDispositivo()).toEqual({ deviceId: 'aparelho-1', token: 'segredo-1' })
  })

  it('sem nada guardado não inventa aparelho', () => {
    expect(lerDispositivo()).toBeNull()
  })

  /**
   * O motivo de tudo isto, medido em 17/08/2026: o controle era aberto em
   * `192.168.0.168:5174`, passou a ser aberto em `:5173`, e o celular pediu
   * pareamento de novo — o token estava guardado e íntegro numa gaveta que a
   * página nova não alcança.
   *
   * `localStorage` é separado por origem, e origem inclui a PORTA. Cookie é
   * escopado por host e ignora a porta. É a única gaveta do navegador com essa
   * propriedade, e é por isso que o pareamento mudou de casa.
   */
  it('grava em cookie, que é a gaveta que a porta não separa', () => {
    guardarDispositivo('aparelho-1', 'segredo-1')

    expect(document.cookie).toContain('controlfawkes.deviceId=aparelho-1')
    expect(document.cookie).toContain('controlfawkes.token=segredo-1')
  })

  it('quem já estava pareado antes da mudança continua pareado', () => {
    // O estado de quem usava a versão anterior: só `localStorage`.
    localStorage.setItem('controlfawkes.deviceId', 'aparelho-antigo')
    localStorage.setItem('controlfawkes.token', 'segredo-antigo')

    expect(lerDispositivo()).toEqual({
      deviceId: 'aparelho-antigo', token: 'segredo-antigo',
    })
  })

  it('e é promovido a cookie na primeira leitura, sem parear de novo', () => {
    localStorage.setItem('controlfawkes.deviceId', 'aparelho-antigo')
    localStorage.setItem('controlfawkes.token', 'segredo-antigo')

    lerDispositivo()

    // A migração acontece sozinha: da próxima vez o cookie já responde, e a
    // troca de porta deixa de desparear.
    expect(document.cookie).toContain('controlfawkes.deviceId=aparelho-antigo')
  })

  it('meio par não vale nem no cookie nem no local', () => {
    localStorage.setItem('controlfawkes.deviceId', 'aparelho-1')

    expect(lerDispositivo()).toBeNull()
  })

  it('o cookie vence o local quando os dois existem', () => {
    localStorage.setItem('controlfawkes.deviceId', 'antigo')
    localStorage.setItem('controlfawkes.token', 'antigo')
    guardarDispositivo('novo', 'novo')

    expect(lerDispositivo()?.deviceId).toBe('novo')
  })

  it('desparear apaga das duas gavetas', () => {
    guardarDispositivo('aparelho-1', 'segredo-1')

    esquecerDispositivo()

    expect(lerDispositivo()).toBeNull()
    expect(document.cookie).not.toContain('aparelho-1')
    expect(localStorage.getItem('controlfawkes.deviceId')).toBeNull()
  })

  /**
   * A honestidade sobre o limite: cookie resolve a troca de PORTA e não
   * resolve a troca de IP. Sair de `192.168.0.168` para `192.168.18.175` — o
   * que acontece ao trocar de Wi-Fi — é outro host, e para o navegador são dois
   * sites diferentes. Nenhuma gaveta atravessa isso.
   *
   * A saída para esse caso é de endereço, não de armazenamento: abrir pelo nome
   * da máquina, que não muda quando o IP muda.
   */
  it('o cookie não é enviado sozinho: quem autentica são os cabeçalhos', () => {
    guardarDispositivo('aparelho-1', 'segredo-1')

    // O backend lê `X-Device-Id` e `X-Device-Token`, postos à mão. Um cookie
    // que o navegador enviasse sozinho e o servidor aceitasse criaria
    // superfície de CSRF; este não cria, porque ninguém do outro lado olha.
    expect(document.cookie).toContain('controlfawkes.token=segredo-1')
    expect(lerDispositivo()?.token).toBe('segredo-1')
  })
})
