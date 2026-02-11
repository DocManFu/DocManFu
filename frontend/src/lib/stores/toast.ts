import { writable } from 'svelte/store';

export interface Toast {
	id: number;
	message: string;
	type: 'success' | 'error' | 'info';
}

let nextId = 0;

function createToastStore() {
	const { subscribe, update } = writable<Toast[]>([]);

	function add(message: string, type: Toast['type'] = 'info', duration = 4000) {
		const id = nextId++;
		update((toasts) => [...toasts, { id, message, type }]);
		setTimeout(() => remove(id), duration);
	}

	function remove(id: number) {
		update((toasts) => toasts.filter((t) => t.id !== id));
	}

	return {
		subscribe,
		success: (msg: string) => add(msg, 'success'),
		error: (msg: string) => add(msg, 'error', 6000),
		info: (msg: string) => add(msg, 'info')
	};
}

export const toasts = createToastStore();
