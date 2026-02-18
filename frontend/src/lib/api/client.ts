import { get } from 'svelte/store';
import { auth } from '$lib/stores/auth.js';

export class ApiError extends Error {
	constructor(
		public status: number,
		public detail: string,
	) {
		super(detail);
		this.name = 'ApiError';
	}
}

export function getAuthHeader(): Record<string, string> {
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
				body: JSON.stringify({ refresh_token: state.refreshToken }),
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
			...options?.headers,
		},
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
					...options?.headers,
				},
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

export async function apiDownload(path: string, fallbackFilename: string): Promise<void> {
	let res = await fetch(path, { headers: getAuthHeader() });

	if (res.status === 401) {
		const refreshed = await attemptTokenRefresh();
		if (refreshed) {
			res = await fetch(path, { headers: getAuthHeader() });
		}
		if (!refreshed || !res.ok) {
			auth.logout();
			if (typeof window !== 'undefined') {
				window.location.href = '/auth/login';
			}
			throw new ApiError(401, 'Session expired');
		}
	}

	if (!res.ok) {
		throw new ApiError(res.status, `Download failed with status ${res.status}`);
	}

	const disposition = res.headers.get('Content-Disposition');
	let filename = fallbackFilename;
	if (disposition) {
		const match = disposition.match(/filename\*?=(?:UTF-8''|"?)([^";]+)/i);
		if (match) filename = decodeURIComponent(match[1].replace(/"/g, ''));
	}

	const blob = await res.blob();
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = filename;
	document.body.appendChild(a);
	a.click();
	document.body.removeChild(a);
	URL.revokeObjectURL(url);
}

export async function apiUploadWithProgress<T>(
	path: string,
	file: File,
	onProgress?: (loaded: number, total: number) => void,
): Promise<T> {
	const formData = new FormData();
	formData.append('file', file);

	return new Promise((resolve, reject) => {
		const xhr = new XMLHttpRequest();
		xhr.open('POST', path);

		const headers = getAuthHeader();
		for (const [key, value] of Object.entries(headers)) {
			xhr.setRequestHeader(key, value);
		}

		xhr.upload.onprogress = (e) => {
			if (e.lengthComputable && onProgress) {
				onProgress(e.loaded, e.total);
			}
		};

		xhr.onload = () => {
			if (xhr.status >= 200 && xhr.status < 300) {
				try {
					resolve(JSON.parse(xhr.responseText));
				} catch {
					reject(new ApiError(xhr.status, 'Invalid JSON response'));
				}
			} else if (xhr.status === 401) {
				attemptTokenRefresh().then((refreshed) => {
					if (refreshed) {
						// Retry with new token
						const retryXhr = new XMLHttpRequest();
						retryXhr.open('POST', path);
						const newHeaders = getAuthHeader();
						for (const [key, value] of Object.entries(newHeaders)) {
							retryXhr.setRequestHeader(key, value);
						}
						retryXhr.upload.onprogress = (e) => {
							if (e.lengthComputable && onProgress) onProgress(e.loaded, e.total);
						};
						retryXhr.onload = () => {
							if (retryXhr.status >= 200 && retryXhr.status < 300) {
								try {
									resolve(JSON.parse(retryXhr.responseText));
								} catch {
									reject(new ApiError(retryXhr.status, 'Invalid JSON'));
								}
							} else {
								reject(new ApiError(retryXhr.status, 'Upload failed after retry'));
							}
						};
						retryXhr.onerror = () => reject(new ApiError(0, 'Network error'));
						const retryForm = new FormData();
						retryForm.append('file', file);
						retryXhr.send(retryForm);
					} else {
						auth.logout();
						if (typeof window !== 'undefined') window.location.href = '/auth/login';
						reject(new ApiError(401, 'Session expired'));
					}
				});
			} else {
				let detail = `Upload failed with status ${xhr.status}`;
				try {
					const body = JSON.parse(xhr.responseText);
					if (body.detail) detail = body.detail;
				} catch {
					/* use default */
				}
				reject(new ApiError(xhr.status, detail));
			}
		};

		xhr.onerror = () => reject(new ApiError(0, 'Network error'));
		xhr.send(formData);
	});
}

export async function apiUpload<T>(path: string, file: File): Promise<T> {
	const formData = new FormData();
	formData.append('file', file);

	const res = await fetch(path, {
		method: 'POST',
		headers: getAuthHeader(),
		body: formData,
	});

	if (res.status === 401) {
		const refreshed = await attemptTokenRefresh();
		if (refreshed) {
			const retryRes = await fetch(path, {
				method: 'POST',
				headers: getAuthHeader(),
				body: formData,
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
