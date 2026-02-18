import { writable } from 'svelte/store';
import { browser } from '$app/environment';

function getInitialTheme(): 'light' | 'dark' {
	if (!browser) return 'light';
	const stored = localStorage.getItem('theme');
	if (stored === 'dark' || stored === 'light') return stored;
	return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function createThemeStore() {
	const { subscribe, set, update } = writable<'light' | 'dark'>(getInitialTheme());

	function apply(theme: 'light' | 'dark') {
		if (!browser) return;
		document.documentElement.classList.toggle('dark', theme === 'dark');
		localStorage.setItem('theme', theme);
	}

	// Apply initial theme
	if (browser) {
		apply(getInitialTheme());
	}

	return {
		subscribe,
		toggle() {
			update((current) => {
				const next = current === 'light' ? 'dark' : 'light';
				apply(next);
				return next;
			});
		},
	};
}

export const theme = createThemeStore();
