import type { TokenResponse, User, AdminUser } from '$lib/types/index.js';
import { apiFetch } from './client.js';

export async function checkSetupNeeded(): Promise<boolean> {
	const res = await fetch('/api/auth/setup-status');
	if (!res.ok) throw new Error('Failed to check setup status');
	const data = await res.json();
	return data.setup_needed === true;
}

export async function setup(
	username: string,
	email: string,
	password: string,
): Promise<TokenResponse> {
	const res = await fetch('/api/auth/setup', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ username, email, password }),
	});
	if (!res.ok) {
		const body = await res.json().catch(() => ({ detail: 'Setup failed' }));
		throw new Error(body.detail || 'Setup failed');
	}
	return res.json();
}

export async function login(username: string, password: string): Promise<TokenResponse> {
	const res = await fetch('/api/auth/login', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ username, password }),
	});
	if (!res.ok) {
		const body = await res.json().catch(() => ({ detail: 'Login failed' }));
		throw new Error(body.detail || 'Login failed');
	}
	return res.json();
}

export async function refresh(refreshToken: string): Promise<TokenResponse> {
	const res = await fetch('/api/auth/refresh', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ refresh_token: refreshToken }),
	});
	if (!res.ok) {
		throw new Error('Token refresh failed');
	}
	return res.json();
}

export async function getMe(): Promise<User> {
	return apiFetch<User>('/api/auth/me');
}

export async function generateApiKey(): Promise<{ api_key: string }> {
	return apiFetch('/api/auth/api-key', { method: 'POST' });
}

export async function revokeApiKey(): Promise<void> {
	await apiFetch('/api/auth/api-key', { method: 'DELETE' });
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
	await apiFetch('/api/auth/change-password', {
		method: 'POST',
		body: JSON.stringify({
			current_password: currentPassword,
			new_password: newPassword,
		}),
	});
}

// --- Admin ---

export async function listUsers(): Promise<AdminUser[]> {
	return apiFetch('/api/admin/users');
}

export async function createUser(
	username: string,
	email: string,
	password: string,
	role: string,
): Promise<AdminUser> {
	return apiFetch('/api/admin/users', {
		method: 'POST',
		body: JSON.stringify({ username, email, password, role }),
	});
}

export async function updateUser(
	userId: string,
	data: { role?: string; is_active?: boolean },
): Promise<AdminUser> {
	return apiFetch(`/api/admin/users/${userId}`, {
		method: 'PUT',
		body: JSON.stringify(data),
	});
}

export async function deactivateUser(userId: string): Promise<void> {
	await apiFetch(`/api/admin/users/${userId}`, { method: 'DELETE' });
}

export async function resetUserPassword(userId: string, newPassword: string): Promise<void> {
	await apiFetch(`/api/admin/users/${userId}/reset-password`, {
		method: 'POST',
		body: JSON.stringify({ new_password: newPassword }),
	});
}
