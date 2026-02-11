import { get } from 'svelte/store';
import { auth } from '$lib/stores/auth.js';

export class ApiError extends Error {
	constructor(
		public status: number,
		public detail: string
	) {
		super(detail);
		this.name = 'ApiError';
	}
}

function getAuthHeader(): Record<string, string> {
	const state = get(auth);
	if (state.accessToken) {
		return { Authorization: `Bearer ${state.accessToken}` };
	}
	return {};
}

let refreshPromise: Promise<boolean> | null = null;

async function attemptTokenRefresh(): Promise<boolean> {
	if (refreshPromise) return refreshPromise;

	refreshPromise = (async () => {
		try {
			const state = get(auth);
			if (!state.refreshToken) return false;

			const res = await fetch('/api/auth/refresh', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ refresh_token: state.refreshToken })
			});

			if (!res.ok) return false;

			const data = await res.json();
			auth.updateTokens(data.access_token, data.refresh_token, data.user);
			return true;
		} catch {
			return false;
		} finally {
			refreshPromise = null;
		}
	})();

	return refreshPromise;
}

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
	const res = await fetch(path, {
		...options,
		headers: {
			'Content-Type': 'application/json',
			...getAuthHeader(),
			...options?.headers
		}
	});

	if (res.status === 401) {
		const refreshed = await attemptTokenRefresh();
		if (refreshed) {
			// Retry with new token
			const retryRes = await fetch(path, {
				...options,
				headers: {
					'Content-Type': 'application/json',
					...getAuthHeader(),
					...options?.headers
				}
			});
			if (retryRes.ok) {
				if (retryRes.status === 204) return undefined as T;
				return retryRes.json();
			}
		}
		// Refresh failed — logout and redirect
		auth.logout();
		if (typeof window !== 'undefined') {
			window.location.href = '/auth/login';
		}
		throw new ApiError(401, 'Session expired');
	}

	if (!res.ok) {
		let detail = `Request failed with status ${res.status}`;
		try {
			const body = await res.json();
			if (body.detail) detail = body.detail;
		} catch {
			// use default message
		}
		throw new ApiError(res.status, detail);
	}

	if (res.status === 204) return undefined as T;
	return res.json();
}

export async function apiUpload<T>(path: string, file: File): Promise<T> {
	const formData = new FormData();
	formData.append('file', file);

	const res = await fetch(path, {
		method: 'POST',
		headers: getAuthHeader(),
		body: formData
	});

	if (res.status === 401) {
		const refreshed = await attemptTokenRefresh();
		if (refreshed) {
			const retryRes = await fetch(path, {
				method: 'POST',
				headers: getAuthHeader(),
				body: formData
			});
			if (retryRes.ok) return retryRes.json();
		}
		auth.logout();
		if (typeof window !== 'undefined') {
			window.location.href = '/auth/login';
		}
		throw new ApiError(401, 'Session expired');
	}

	if (!res.ok) {
		let detail = `Upload failed with status ${res.status}`;
		try {
			const body = await res.json();
			if (body.detail) detail = body.detail;
		} catch {
			// use default message
		}
		throw new ApiError(res.status, detail);
	}

	return res.json();
}
