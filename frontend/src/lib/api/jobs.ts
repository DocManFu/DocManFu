import { apiFetch } from './client.js';
import type { JobStatusResponse } from '$lib/types/index.js';

export function getJobStatus(jobId: string): Promise<JobStatusResponse> {
	return apiFetch<JobStatusResponse>(`/api/jobs/${jobId}/status`);
}

export function getDocumentJobs(documentId: string): Promise<JobStatusResponse[]> {
	return apiFetch<JobStatusResponse[]>(`/api/jobs/by-document/${documentId}`);
}
