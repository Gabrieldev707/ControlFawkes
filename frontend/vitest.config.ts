import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

const windowsTestPool = process.platform === 'win32'
  ? {
      pool: 'threads' as const,
      fileParallelism: false,
      isolate: false,
    }
  : {}


export default defineConfig({
  plugins: [react()],
  // A suíte roda com raiz em `frontend/`, e os testes da extensão vivem um
  // nível acima. Sem esta permissão o Vite recusa servir o arquivo e o erro
  // que aparece é "Cannot find module", que aponta para o lugar errado.
  server: { fs: { allow: ['..'] } },
  test: {
    environment: 'jsdom',
    clearMocks: true,
    setupFiles: ['./src/test/setup.ts'],
    // A extensão entra na mesma suíte em vez de ganhar um runner próprio: ela
    // é DOM puro, o jsdom já está aqui, e um segundo `package.json` com as
    // mesmas dependências seria manutenção em dobro para rodar o mesmo teste.
    include: [
      'src/**/*.{test,spec}.{ts,tsx}',
      '../browser-extension/**/*.{test,spec}.{ts,tsx}',
    ],
    ...windowsTestPool,
  },
})
