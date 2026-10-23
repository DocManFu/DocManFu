import {
	startAuthentication,
	startRegistration,
	type PublicKeyCredentialCreationOptionsJSON,
	type PublicKeyCredentialRequestOptionsJSON,
} from '@simplewebauthn/browser';
import type { Passkey, TokenResponse } from '$lib/types/index.js';
import { apiFetch } from './client.js';

interface OptionsResponse<T> {
	challenge_id: string;
	options: T;
}

/** True when the browser dismissed the passkey prompt (user cancelled or timed out). */
export function isPasskeyCancelled(err: unknown): boolean {
	return err instanceof Error && (err.name === 'NotAllowedError' || err.name === 'AbortError');
}

async function postJSON<T>(path: string, body: unknown, fallback: string): Promise<T> {
	const res = await fetch(path, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body),
	});
	if (!res.ok) {
		const data = await res.json().catch(() => ({ detail: fallback }));
		throw new Error(data.detail || fallback);
	}
	return res.json();
}

export async function loginWithPasskey(): Promise<TokenResponse> {
	const { challenge_id, options } = await postJSON<
		OptionsResponse<PublicKeyCredentialRequestOptionsJSON>
	>('/api/auth/passkeys/login/options', {}, 'Passkey sign-in failed');
	const credential = await startAuthentication({ optionsJSON: options });
	return postJSON<TokenResponse>(
		'/api/auth/passkeys/login/verify',
		{ challenge_id, credential },
		'Passkey sign-in failed',
	);
}

export async function registerPasskey(password: string, name: string): Promise<Passkey> {
	const { challenge_id, options } = await apiFetch<
		OptionsResponse<PublicKeyCredentialCreationOptionsJSON>
	>('/api/auth/passkeys/register/options', { method: 'POST', body: JSON.stringify({ password }) });
	const credential = await startRegistration({ optionsJSON: options });
	return apiFetch<Passkey>('/api/auth/passkeys/register/verify', {
		method: 'POST',
		body: JSON.stringify({ challenge_id, credential, name }),
	});
}

export async function listPasskeys(): Promise<Passkey[]> {
	return apiFetch<Passkey[]>('/api/auth/passkeys');
}

export async function deletePasskey(id: string): Promise<void> {
	await apiFetch(`/api/auth/passkeys/${id}`, { method: 'DELETE' });
}
