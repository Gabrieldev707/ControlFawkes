/**
 * Onde o pareamento do aparelho fica guardado — e por que não é `localStorage`.
 *
 * O par `deviceId`/`token` vinha do pareamento por PIN e morava em
 * `localStorage`. O problema é o mesmo que tirou o nome e a foto de lá:
 * `localStorage` é separado por ORIGEM, e origem é esquema + host + PORTA.
 *
 * Medido em 17/08/2026: o controle era aberto em `192.168.0.168:5174`, passou a
 * ser aberto em `:5173`, e o celular pediu pareamento de novo — o token estava
 * guardado, íntegro, numa gaveta que a página nova não alcança.
 *
 * ## Cookie ignora a porta
 *
 * Essa é a diferença que resolve metade do problema. Cookie é escopado por
 * HOST, e a porta não faz parte da chave: um cookie gravado em `:5173` é lido
 * em `:5174` e vice-versa. É a única gaveta do navegador com essa propriedade.
 *
 * ## O que o cookie NÃO resolve
 *
 * Troca de IP. Se a máquina sai de `192.168.0.168` e vai para
 * `192.168.18.175` — o que acontece ao trocar de rede Wi-Fi —, é outro host, e
 * nada guardado no navegador atravessa isso. Não há truque: para o navegador
 * são dois sites diferentes.
 *
 * A saída para esse caso não é de armazenamento, é de ENDEREÇO: abrir o
 * controle pelo nome da máquina em vez do IP. Medido nesta máquina,
 * `DESKTOP-GBRLL5E.local` resolve para o IP atual via mDNS, e o nome não muda
 * quando o IP muda. Ver o README.
 *
 * ## Por que guardar um token em cookie aqui é seguro
 *
 * O backend NÃO lê cookie: ele autentica pelos cabeçalhos `X-Device-Id` e
 * `X-Device-Token`, que este código põe à mão. O cookie é só a gaveta. Isso
 * importa — um cookie que o navegador enviasse sozinho criaria superfície de
 * CSRF, e este não cria, porque ninguém do outro lado olha para ele.
 *
 * `SameSite=Lax` de propósito, e não `None`: não há uso legítimo deste cookie
 * partindo de outro site.
 */

const CHAVE_ID = 'controlfawkes.deviceId'
const CHAVE_TOKEN = 'controlfawkes.token'

// Um ano. O pareamento não expira do lado do servidor, e um cookie que vencesse
// antes disso faria o celular pedir PIN de novo sem nada ter mudado.
const DIAS_DE_VALIDADE = 365

function lerCookie(nome: string): string | null {
  try {
    const alvo = `${encodeURIComponent(nome)}=`
    for (const pedaco of document.cookie.split(';')) {
      const limpo = pedaco.trim()
      if (limpo.startsWith(alvo)) return decodeURIComponent(limpo.slice(alvo.length))
    }
    return null
  } catch {
    return null
  }
}

function escreverCookie(nome: string, valor: string): void {
  try {
    const idade = DIAS_DE_VALIDADE * 24 * 60 * 60
    document.cookie = `${encodeURIComponent(nome)}=${encodeURIComponent(valor)}`
      + `; Path=/; Max-Age=${idade}; SameSite=Lax`
  } catch {
    // Cookies bloqueados. O `localStorage` abaixo continua valendo, e o
    // pareamento só deixa de atravessar a troca de porta.
  }
}

function apagarCookie(nome: string): void {
  try {
    document.cookie = `${encodeURIComponent(nome)}=; Path=/; Max-Age=0; SameSite=Lax`
  } catch {
    // Nada a fazer.
  }
}

function lerLocal(chave: string): string | null {
  try {
    return localStorage.getItem(chave)
  } catch {
    return null
  }
}

export interface DispositivoGuardado {
  deviceId: string
  token: string
}

/**
 * O pareamento guardado, venha ele de onde vier.
 *
 * Cookie primeiro; `localStorage` como retaguarda, para quem já estava pareado
 * antes desta mudança. E quando o achado vem só do `localStorage`, ele é
 * promovido a cookie na hora — é assim que a migração acontece sozinha, sem
 * ninguém precisar parear de novo.
 */
export function lerDispositivo(): DispositivoGuardado | null {
  const doCookie = { deviceId: lerCookie(CHAVE_ID), token: lerCookie(CHAVE_TOKEN) }
  if (doCookie.deviceId && doCookie.token) {
    return { deviceId: doCookie.deviceId, token: doCookie.token }
  }

  const doLocal = { deviceId: lerLocal(CHAVE_ID), token: lerLocal(CHAVE_TOKEN) }
  if (doLocal.deviceId && doLocal.token) {
    escreverCookie(CHAVE_ID, doLocal.deviceId)
    escreverCookie(CHAVE_TOKEN, doLocal.token)
    return { deviceId: doLocal.deviceId, token: doLocal.token }
  }
  return null
}

/** Guarda nos dois lugares: o cookie atravessa a porta, o local é retaguarda. */
export function guardarDispositivo(deviceId: string, token: string): void {
  escreverCookie(CHAVE_ID, deviceId)
  escreverCookie(CHAVE_TOKEN, token)
  try {
    localStorage.setItem(CHAVE_ID, deviceId)
    localStorage.setItem(CHAVE_TOKEN, token)
  } catch {
    // Sem `localStorage` o cookie basta.
  }
}

/** Desparear tem de desparear: sobrar em qualquer gaveta traria o token de volta. */
export function esquecerDispositivo(): void {
  apagarCookie(CHAVE_ID)
  apagarCookie(CHAVE_TOKEN)
  try {
    localStorage.removeItem(CHAVE_ID)
    localStorage.removeItem(CHAVE_TOKEN)
  } catch {
    // Nada a fazer.
  }
}
