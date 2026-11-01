import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const apiTarget = process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000';
const previewMode = process.env.BASE44_PREVIEW_MODE === '1';
const sandboxDomain = process.env.BASE44_SANDBOX_HOST_DOMAIN || '';

// Im Sandbox-Preview erreicht den Dev-Server ein durchgereichter Hostname,
// dessen Sandbox-ID wechselt – daher nur im Preview-Modus erweitern.
const allowedHosts = previewMode && sandboxDomain ? [`.${sandboxDomain}`] : undefined;

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    strictPort: true,
    ...(allowedHosts ? { allowedHosts } : {}),
    ...(previewMode ? { watch: { usePolling: true, interval: 300 } } : {}),
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true },
    },
  },
});
