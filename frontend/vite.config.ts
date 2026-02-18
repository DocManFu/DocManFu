import { sveltekit } from '@sveltejs/kit/vite';
import UnoCSS from 'unocss/vite';
import { defineConfig } from 'vite';

const apiTarget = process.env.API_TARGET || 'http://localhost:8000';

export default defineConfig({
	plugins: [UnoCSS(), sveltekit()],
	server: {
		proxy: {
			'/api/events': {
				target: apiTarget,
				changeOrigin: true,
				headers: { Accept: 'text/event-stream' },
			},
			'/api/admin/import/evernote': {
				target: apiTarget,
				changeOrigin: true,
				timeout: 600000, // 10 min for large ENEX uploads
			},
			'/api': {
				target: apiTarget,
				changeOrigin: true,
			},
		},
	},
});
