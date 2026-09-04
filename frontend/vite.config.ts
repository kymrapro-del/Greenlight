import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

/**
 * En développement, l'API tourne à part (uvicorn sur 8000) et l'interface la
 * joint par ce proxy : `VITE_API_BASE` reste vide, le client tape la même
 * origine, et il n'y a pas de CORS à traverser localement.
 *
 * En production, `VITE_API_BASE` pointe sur le service déployé.
 */
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: process.env.GREENLIGHT_API ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
        // Le flux SSE doit arriver événement par événement : un proxy qui
        // tamponne rendrait la progression d'un bloc, à la fin.
        configure: (proxy) => {
          proxy.on('proxyRes', (res) => {
            res.headers['cache-control'] = 'no-cache';
          });
        },
      },
    },
  },
});
