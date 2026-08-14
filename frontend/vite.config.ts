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
  },
})
