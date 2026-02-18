import { sveltekit } from '@sveltejs/kit/vite';
import UnoCSS from 'unocss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [UnoCSS(), sveltekit()],
	server: {
		proxy: {
			'/api/events': {
				target: process.env.API_TARGET || 'http://localhost:8000',
				changeOrigin: true,
				headers: { 'Accept': 'text/event-stream' }
			},
			'/api/admin/import/evernote': {
				target: process.env.API_TARGET || 'http://localhost:8000',
				changeOrigin: true,
				timeout: 600000, // 10 min for large ENEX uploads
				configure: (proxy) => {
					proxy.on('proxyReq', (proxyReq) => {
						// Remove default timeout for large uploads
						proxyReq.socket?.setTimeout(600000);
					});
				}
			},
			'/api': {
				target: process.env.API_TARGET || 'http://localhost:8000',
				changeOrigin: true
			}
		}
	}
});
