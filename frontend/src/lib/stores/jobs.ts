import { writable, get } from 'svelte/store';
import { getJobStatus, getDocumentJobs } from '$lib/api/jobs.js';
import type { JobStatusResponse } from '$lib/types/index.js';

export interface TrackedJob {
	jobId: string;
	documentId: string;
	fileName: string;
	status: JobStatusResponse;
}

function createJobStore() {
	const { subscribe, update } = writable<TrackedJob[]>([]);
	let pollInterval: ReturnType<typeof setInterval> | null = null;

	function startPolling() {
		if (pollInterval) return;
		pollInterval = setInterval(poll, 2000);
	}

	function stopPolling() {
		if (pollInterval) {
			clearInterval(pollInterval);
			pollInterval = null;
		}
	}

	async function poll() {
		const jobs = get({ subscribe });
		const active = jobs.filter(
			(j) => j.status.status === 'pending' || j.status.status === 'processing'
		);

		if (active.length === 0) {
			stopPolling();
			return;
		}

		for (const job of active) {
			try {
				const prev = job.status;
				const status = await getJobStatus(job.jobId);
				update((all) => all.map((j) => (j.jobId === job.jobId ? { ...j, status } : j)));

				// When a job just completed, check for follow-on jobs (e.g. AI analysis after OCR)
				if (prev.status !== 'completed' && status.status === 'completed') {
					await pickUpNewJobs(job.documentId, job.fileName);
				}
			} catch {
				// ignore polling errors
			}
		}
	}

	async function pickUpNewJobs(documentId: string, fileName: string) {
		try {
			const activeJobs = await getDocumentJobs(documentId);
			const currentJobs = get({ subscribe });
			const trackedIds = new Set(currentJobs.map((j) => j.jobId));
			let added = false;

			for (const job of activeJobs) {
				if (!trackedIds.has(job.id)) {
					update((all) => [
						...all,
						{ jobId: job.id, documentId, fileName, status: job }
					]);
					added = true;
				}
			}

			if (added) startPolling();
		} catch {
			// ignore — follow-on job tracking is best-effort
		}
	}

	function track(jobId: string, documentId: string, fileName: string) {
		const initial: JobStatusResponse = {
			id: jobId,
			document_id: documentId,
			job_type: 'ocr',
			status: 'pending',
			progress: 0,
			error_message: null,
			created_at: new Date().toISOString(),
			started_at: null,
			completed_at: null,
			result_data: null
		};
		update((jobs) => [...jobs, { jobId, documentId, fileName, status: initial }]);
		startPolling();
	}

	function dismiss(jobId: string) {
		update((jobs) => jobs.filter((j) => j.jobId !== jobId));
	}

	function clearCompleted() {
		update((jobs) =>
			jobs.filter((j) => j.status.status === 'pending' || j.status.status === 'processing')
		);
	}

	return { subscribe, track, dismiss, clearCompleted };
}

export const jobStore = createJobStore();
