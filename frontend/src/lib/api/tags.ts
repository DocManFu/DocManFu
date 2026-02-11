import { apiFetch } from './client.js';
import type {
	TagWithCount,
	TagCreateRequest,
	TagUpdateRequest,
	TagMergeRequest
} from '$lib/types/index.js';

interface TagResponse {
	id: string;
	name: string;
	color: string;
}

export function listTags(): Promise<TagWithCount[]> {
	return apiFetch<TagWithCount[]>('/api/tags');
}

export function createTag(data: TagCreateRequest): Promise<TagResponse> {
	return apiFetch<TagResponse>('/api/tags', {
		method: 'POST',
		body: JSON.stringify(data)
	});
}

export function updateTag(id: string, data: TagUpdateRequest): Promise<TagResponse> {
	return apiFetch<TagResponse>(`/api/tags/${id}`, {
		method: 'PUT',
		body: JSON.stringify(data)
	});
}

export function deleteTag(id: string): Promise<{ detail: string }> {
	return apiFetch<{ detail: string }>(`/api/tags/${id}`, { method: 'DELETE' });
}

export function mergeTags(data: TagMergeRequest): Promise<{ detail: string }> {
	return apiFetch<{ detail: string }>('/api/tags/merge', {
		method: 'POST',
		body: JSON.stringify(data)
	});
}
