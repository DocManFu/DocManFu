import { apiFetch, ApiError, getAuthHeader } from './client.js';

export interface ImportTaskResponse {
	task_id: string;
	filename: string;
	status: string;
}

export interface ImportProgress {
	current: number;
	total: number;
	imported?: number;
	documents_created?: number;
	status: string;
}

export interface ImportResult {
	filename: string;
	total_notes: number;
	imported_notes: number;
	documents_created: number;
	errors: number;
	skipped: Array<{
		title: string;
		reason: string;
		created: string;
		tags: string[];
		resources: Array<{ mime: string; filename: string | null; reason: string }>;
	}>;
	error_list: Array<{ title: string; error: string }>;
}

export interface ImportStatusResponse {
	task_id: string;
	status: string;
	progress: ImportProgress | null;
	result: ImportResult | null;
}

export async function startEvernoteImport(
	file: File,
	onProgress?: (loaded: number, total: number) => void,
): Promise<ImportTaskResponse> {
	return new Promise((resolve, reject) => {
		const xhr = new XMLHttpRequest();
		xhr.open('POST', '/api/admin/import/evernote');
		xhr.setRequestHeader('Content-Type', 'application/octet-stream');
		xhr.setRequestHeader('X-Filename', encodeURIComponent(file.name));

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
				return;
			}

			let detail = `Import upload failed with status ${xhr.status}`;
			try {
				const body = JSON.parse(xhr.responseText);
				if (body.detail) detail = body.detail;
			} catch {
				/* use default */
			}
			reject(new ApiError(xhr.status, detail));
		};

		xhr.onerror = () => reject(new ApiError(0, 'Network error'));
		xhr.send(file);
	});
}

export async function getImportStatus(taskId: string): Promise<ImportStatusResponse> {
	return apiFetch<ImportStatusResponse>(`/api/admin/import/status/${taskId}`);
}

export async function cancelImport(taskId: string): Promise<{ detail: string }> {
	return apiFetch<{ detail: string }>(`/api/admin/import/cancel/${taskId}`, { method: 'POST' });
}

// --- Batch Reprocess ---

export interface ReprocessStats {
	total: number;
	with_text: number;
	no_text: number;
	no_ai: number;
	no_ai_needs_ocr: number;
}

export interface ReprocessStartResponse {
	task_id: string;
	total: number;
	job_type: string;
	filter: string;
	status: string;
}

export interface ActiveReprocess {
	active: boolean;
	task_id?: string;
	paused?: boolean;
}

export async function getActiveReprocess(): Promise<ActiveReprocess> {
	return apiFetch<ActiveReprocess>('/api/admin/import/reprocess/active');
}

export async function getReprocessStats(): Promise<ReprocessStats> {
	return apiFetch<ReprocessStats>('/api/admin/import/reprocess/stats');
}

export async function startBatchReprocess(
	jobType: string = 'ocr',
	filter: string = 'all',
): Promise<ReprocessStartResponse> {
	return apiFetch<ReprocessStartResponse>('/api/admin/import/reprocess', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ job_type: jobType, filter }),
	});
}

export async function pauseReprocess(taskId: string): Promise<{ detail: string }> {
	return apiFetch<{ detail: string }>(`/api/admin/import/reprocess/pause/${taskId}`, {
		method: 'POST',
	});
}

export async function resumeReprocess(taskId: string): Promise<{ detail: string }> {
	return apiFetch<{ detail: string }>(`/api/admin/import/reprocess/resume/${taskId}`, {
		method: 'POST',
	});
}

export async function skipCurrentDocument(taskId: string): Promise<{ detail: string }> {
	return apiFetch<{ detail: string }>(`/api/admin/import/reprocess/skip/${taskId}`, {
		method: 'POST',
	});
}

export async function cancelReprocess(taskId: string): Promise<{ detail: string }> {
	return apiFetch<{ detail: string }>(`/api/admin/import/reprocess/cancel/${taskId}`, {
		method: 'POST',
	});
}
