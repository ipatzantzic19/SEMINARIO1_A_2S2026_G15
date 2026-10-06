import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { parseEnv } from './src/config/env.ts';

export default defineConfig(({ mode }) => {
  parseEnv(loadEnv(mode, '.', 'VITE_')); // Fallar temprano ante configuración inválida.
  return { plugins: [react()], base: './' };
});
