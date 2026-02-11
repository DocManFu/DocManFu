import { apiFetch, apiUpload } from './client.js';
import type {
	PaginatedResponse,
	SearchPaginatedResponse,
	DocumentDetail,
	DocumentUpdateRequest,
	UploadResponse,
	ReprocessResponse,
	ListDocumentsParams,
	SearchDocumentsParams,
	BulkTagRequest,
	BulkDeleteRequest,
	BulkReprocessRequest
} from '$lib/types/index.js';

function buildQuery(params: Record<string, string | number | undefined>): string {
	const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== '');
	if (entries.length === 0) return '';
	return '?' + new URLSearchParams(entries.map(([k, v]) => [k, String(v)])).toString();
}

export function listDocuments(params: ListDocumentsParams = {}): Promise<PaginatedResponse> {
	return apiFetch<PaginatedResponse>(`/api/documents${buildQuery({ ...params })}`);
}

export function searchDocuments(params: SearchDocumentsParams): Promise<SearchPaginatedResponse> {
	return apiFetch<SearchPaginatedResponse>(`/api/documents/search${buildQuery({ ...params })}`);
}

export function getDocument(id: string): Promise<DocumentDetail> {
	return apiFetch<DocumentDetail>(`/api/documents/${id}`);
}

export function updateDocument(id: string, data: DocumentUpdateRequest): Promise<DocumentDetail> {
	return apiFetch<DocumentDetail>(`/api/documents/${id}`, {
		method: 'PUT',
		body: JSON.stringify(data)
	});
}

export function deleteDocument(id: string): Promise<{ detail: string }> {
	return apiFetch<{ detail: string }>(`/api/documents/${id}`, { method: 'DELETE' });
}

export function uploadDocument(file: File): Promise<UploadResponse> {
	return apiUpload<UploadResponse>('/api/documents/upload', file);
}

export function reprocessDocument(id: string): Promise<ReprocessResponse> {
	return apiFetch<ReprocessResponse>(`/api/documents/${id}/reprocess`, { method: 'POST' });
}

export function getDownloadUrl(id: string): string {
	return `/api/documents/${id}/download`;
}

// --- Bulk operations ---

export function bulkTagDocuments(data: BulkTagRequest): Promise<{ detail: string }> {
	return apiFetch<{ detail: string }>('/api/documents/bulk/tag', {
		method: 'POST',
		body: JSON.stringify(data)
	});
}

export function bulkDeleteDocuments(data: BulkDeleteRequest): Promise<{ detail: string }> {
	return apiFetch<{ detail: string }>('/api/documents/bulk/delete', {
		method: 'POST',
		body: JSON.stringify(data)
	});
}

export function bulkReprocessDocuments(data: BulkReprocessRequest): Promise<{ detail: string; jobs: Array<{ job_id: string; document_id: string }> }> {
	return apiFetch('/api/documents/bulk/reprocess', {
		method: 'POST',
		body: JSON.stringify(data)
	});
}

export function getExportCsvUrl(params: Record<string, string | undefined> = {}): string {
	return `/api/documents/export/csv${buildQuery(params)}`;
}
