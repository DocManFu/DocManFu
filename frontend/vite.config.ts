import { sveltekit } from '@sveltejs/kit/vite';
import UnoCSS from 'unocss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [UnoCSS(), sveltekit()],
	server: {
		proxy: {
			'/api': {
				target: process.env.API_TARGET || 'http://localhost:8000',
				changeOrigin: true
			}
		}
	}
});
