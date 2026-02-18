import { writable } from 'svelte/store';
import { browser } from '$app/environment';

export type ViewMode = 'grid' | 'list';

function getInitialViewMode(): ViewMode {
	if (!browser) return 'grid';
	const stored = localStorage.getItem('viewMode');
	if (stored === 'grid' || stored === 'list') return stored;
	return 'grid';
}

function createViewModeStore() {
	const { subscribe, set } = writable<ViewMode>(getInitialViewMode());

	return {
		subscribe,
		set(mode: ViewMode) {
			if (browser) localStorage.setItem('viewMode', mode);
			set(mode);
		},
	};
}

export const viewMode = createViewModeStore();

// Stores the documents list URL (with query params) so the detail page can link back with filters preserved
export const documentsListUrl = writable<string>('/documents');
