import { apiFetch } from './client.js';
import type { AISettings, AISettingsUpdate, TestConnectionResult } from '$lib/types/index.js';

export async function getAISettings(): Promise<AISettings> {
	return apiFetch('/api/admin/settings/ai');
}

export async function updateAISettings(data: AISettingsUpdate): Promise<AISettings> {
	return apiFetch('/api/admin/settings/ai', {
		method: 'PUT',
		body: JSON.stringify(data),
	});
}

export async function testAIConnection(data: AISettingsUpdate): Promise<TestConnectionResult> {
	return apiFetch('/api/admin/settings/ai/test', {
		method: 'POST',
		body: JSON.stringify(data),
	});
}

export async function resetAISettings(): Promise<{ detail: string }> {
	return apiFetch('/api/admin/settings/ai', {
		method: 'DELETE',
	});
}
