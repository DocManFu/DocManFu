import { writable, derived } from 'svelte/store';
import type { User } from '$lib/types/index.js';

interface AuthState {
	user: User | null;
	accessToken: string | null;
	refreshToken: string | null;
	initialized: boolean;
}

const STORAGE_KEY = 'docmanfu_auth';

function createAuthStore() {
	const { subscribe, set, update } = writable<AuthState>({
		user: null,
		accessToken: null,
		refreshToken: null,
		initialized: false
	});

	function login(data: { access_token: string; refresh_token: string; user: User }) {
		const state: AuthState = {
			user: data.user,
			accessToken: data.access_token,
			refreshToken: data.refresh_token,
			initialized: true
		};
		set(state);
		try {
			localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
		} catch {
			// localStorage unavailable
		}
	}

	function logout() {
		const state: AuthState = {
			user: null,
			accessToken: null,
			refreshToken: null,
			initialized: true
		};
		set(state);
		try {
			localStorage.removeItem(STORAGE_KEY);
		} catch {
			// localStorage unavailable
		}
	}

	function updateTokens(accessToken: string, refreshToken: string, user?: User) {
		update((s) => {
			const newState = {
				...s,
				accessToken,
				refreshToken,
				user: user ?? s.user
			};
			try {
				localStorage.setItem(STORAGE_KEY, JSON.stringify(newState));
			} catch {
				// localStorage unavailable
			}
			return newState;
		});
	}

	function loadFromStorage() {
		try {
			const raw = localStorage.getItem(STORAGE_KEY);
			if (raw) {
				const stored = JSON.parse(raw) as AuthState;
				set({ ...stored, initialized: true });
				return;
			}
		} catch {
			// corrupted data
		}
		update((s) => ({ ...s, initialized: true }));
	}

	return { subscribe, login, logout, updateTokens, loadFromStorage };
}

export const auth = createAuthStore();

export const isAuthenticated = derived(auth, ($auth) => !!$auth.accessToken);
export const isAdmin = derived(auth, ($auth) => $auth.user?.role === 'admin');
export const currentUser = derived(auth, ($auth) => $auth.user);
