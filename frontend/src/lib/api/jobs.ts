import { apiFetch } from './client.js';
import type { JobStatusResponse, JobListResponse, JobListParams } from '$lib/types/index.js';

export function getJobStatus(jobId: string): Promise<JobStatusResponse> {
	return apiFetch<JobStatusResponse>(`/api/jobs/${jobId}/status`);
}

export function getDocumentJobs(documentId: string): Promise<JobStatusResponse[]> {
	return apiFetch<JobStatusResponse[]>(`/api/jobs/by-document/${documentId}`);
}

export function getDocumentJobHistory(documentId: string): Promise<JobStatusResponse[]> {
	return apiFetch<JobStatusResponse[]>(`/api/jobs/by-document/${documentId}/history`);
}

export function listAllJobs(params: JobListParams = {}): Promise<JobListResponse> {
	const searchParams = new URLSearchParams();
	if (params.status) searchParams.set('status', params.status);
	if (params.job_type) searchParams.set('job_type', params.job_type);
	if (params.sort_order) searchParams.set('sort_order', params.sort_order);
	if (params.offset !== undefined) searchParams.set('offset', String(params.offset));
	if (params.limit !== undefined) searchParams.set('limit', String(params.limit));
	const qs = searchParams.toString();
	return apiFetch<JobListResponse>(`/api/jobs${qs ? `?${qs}` : ''}`);
}

export function cancelJob(jobId: string): Promise<{ detail: string }> {
	return apiFetch<{ detail: string }>(`/api/jobs/${jobId}/cancel`, { method: 'POST' });
}
