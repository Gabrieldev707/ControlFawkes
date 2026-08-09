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
  test: {
    environment: 'jsdom',
    clearMocks: true,
    setupFiles: ['./src/test/setup.ts'],
    ...windowsTestPool,
  },
})
