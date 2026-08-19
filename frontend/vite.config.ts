import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'


const PASTA_CERTS = resolve(__dirname, '../backend/data/certs')
const CERT = resolve(PASTA_CERTS, 'controlfawkes.crt')
const CHAVE = resolve(PASTA_CERTS, 'controlfawkes.key')

/**
 * HTTPS só quando pedido e só quando o certificado existe.
 *
 * O microfone do iPhone exige contexto seguro: por `http://IP-da-rede` o
 * Safari nem expõe `navigator.mediaDevices`. Mas ligar HTTPS por padrão
 * quebraria quem ainda não gerou o certificado, então é opt-in por
 * `FAWKES_HTTPS=1` (o que `npm run dev:https` faz).
 */
function certificadoLocal() {
  if (process.env.FAWKES_HTTPS !== '1') return undefined
  if (!existsSync(CERT) || !existsSync(CHAVE)) {
    throw new Error(
      'FAWKES_HTTPS=1 sem certificado. Rode primeiro:\n'
      + '  cd backend && .\\.venv\\Scripts\\python.exe scripts/gerar_certificado.py',
    )
  }
  return { cert: readFileSync(CERT), key: readFileSync(CHAVE) }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // Allow external connections (IP)
    port: 5173,
    https: certificadoLocal(),
    /**
     * Nomes mDNS liberados — e só eles.
     *
     * O Vite recusa requisições cujo `Host` ele não conhece, e faz isso por um
     * motivo real: DNS rebinding. Um site qualquer pode apontar um domínio dele
     * para 127.0.0.1 e, se o servidor de desenvolvimento responder a qualquer
     * `Host`, passa a ler o que roda na sua máquina. Endereço IP o Vite já
     * aceita sozinho; nome, não.
     *
     * Medido em 17/08/2026: o IP da máquina mudou de 192.168.0.168 para
     * 192.168.18.175 ao trocar de Wi-Fi, e com ele foram embora o pareamento e
     * qualquer coisa guardada por origem no navegador. O nome mDNS não muda
     * junto — `DESKTOP-GBRLL5E.local` resolve para o IP de agora, e vai
     * resolver para o próximo.
     *
     * O ponto na frente cobre o domínio e os subdomínios dele, então isto vale
     * para qualquer máquina sem precisar escrever o nome desta aqui. E é bem
     * mais estreito que `allowedHosts: true`, que desligaria a proteção
     * inteira.
     */
    allowedHosts: ['.local'],
  },
})
