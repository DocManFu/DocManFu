import { writable, get } from 'svelte/store';
import { getJobStatus, getDocumentJobs } from '$lib/api/jobs.js';
import {
	connectSSE,
	disconnectSSE,
	isSSEConnected,
	type JobEvent,
	type DocumentUpdatedEvent,
	type ImportEvent,
	type ReprocessEvent,
} from '$lib/api/events.js';
import type { JobStatusResponse } from '$lib/types/index.js';

export interface TrackedJob {
	jobId: string;
	documentId: string;
	fileName: string;
	status: JobStatusResponse;
}

type DocumentUpdatedCallback = (event: DocumentUpdatedEvent) => void;
type JobEventCallback = (event: JobEvent) => void;
type ImportEventCallback = (event: ImportEvent) => void;
type ReprocessEventCallback = (event: ReprocessEvent) => void;

function createJobStore() {
	const { subscribe, update } = writable<TrackedJob[]>([]);
	let pollInterval: ReturnType<typeof setInterval> | null = null;
	let sseConnected = false;
	const documentUpdateCallbacks = new Set<DocumentUpdatedCallback>();
	const jobEventCallbacks = new Set<JobEventCallback>();
	const importProgressCallbacks = new Set<ImportEventCallback>();
	const importCompletedCallbacks = new Set<ImportEventCallback>();
	const importFailedCallbacks = new Set<ImportEventCallback>();
	const reprocessProgressCallbacks = new Set<ReprocessEventCallback>();
	const reprocessCompletedCallbacks = new Set<ReprocessEventCallback>();
	const reprocessCancelledCallbacks = new Set<ReprocessEventCallback>();

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

	function hasActiveJobs(): boolean {
		const jobs = get({ subscribe });
		return jobs.some((j) => j.status.status === 'pending' || j.status.status === 'processing');
	}

	async function poll() {
		const jobs = get({ subscribe });
		const active = jobs.filter(
			(j) => j.status.status === 'pending' || j.status.status === 'processing',
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
					update((all) => [...all, { jobId: job.id, documentId, fileName, status: job }]);
					added = true;
				}
			}

			if (added && !sseConnected) startPolling();
		} catch {
			// ignore — follow-on job tracking is best-effort
		}
	}

	function handleJobEvent(event: JobEvent) {
		for (const cb of jobEventCallbacks) {
			cb(event);
		}

		const jobs = get({ subscribe });
		const existing = jobs.find((j) => j.jobId === event.job_id);

		if (existing) {
			// Update existing tracked job
			update((all) =>
				all.map((j) =>
					j.jobId === event.job_id
						? {
								...j,
								status: {
									...j.status,
									status: event.status as JobStatusResponse['status'],
									progress: event.progress,
									job_type: event.job_type as JobStatusResponse['job_type'],
									result_data: event.result_data ?? j.status.result_data,
									error_message: event.error_message ?? j.status.error_message,
								},
							}
						: j,
				),
			);
		} else {
			// Auto-track follow-on jobs (e.g. AI analysis after OCR) matched by document_id
			const related = jobs.find((j) => j.documentId === event.document_id);
			if (related) {
				const newJob: TrackedJob = {
					jobId: event.job_id,
					documentId: event.document_id,
					fileName: related.fileName,
					status: {
						id: event.job_id,
						document_id: event.document_id,
						job_type: event.job_type as JobStatusResponse['job_type'],
						status: event.status as JobStatusResponse['status'],
						progress: event.progress,
						error_message: event.error_message ?? null,
						created_at: new Date().toISOString(),
						started_at: new Date().toISOString(),
						completed_at: null,
						result_data: event.result_data ?? null,
					},
				};
				update((all) => [...all, newJob]);
			}
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
			result_data: null,
		};
		update((jobs) => [...jobs, { jobId, documentId, fileName, status: initial }]);
		if (!sseConnected) startPolling();
	}

	function dismiss(jobId: string) {
		update((jobs) => jobs.filter((j) => j.jobId !== jobId));
	}

	function clearCompleted() {
		update((jobs) =>
			jobs.filter((j) => j.status.status === 'pending' || j.status.status === 'processing'),
		);
	}

	function init() {
		connectSSE({
			onConnected() {
				sseConnected = true;
				stopPolling();
			},
			onDisconnected() {
				sseConnected = false;
				if (hasActiveJobs()) startPolling();
			},
			onJobStarted: handleJobEvent,
			onJobProgress: handleJobEvent,
			onJobCompleted: handleJobEvent,
			onJobFailed: handleJobEvent,
			onDocumentUpdated(event) {
				for (const cb of documentUpdateCallbacks) {
					cb(event);
				}
			},
			onImportProgress(event) {
				for (const cb of importProgressCallbacks) cb(event);
			},
			onImportCompleted(event) {
				for (const cb of importCompletedCallbacks) cb(event);
			},
			onImportFailed(event) {
				for (const cb of importFailedCallbacks) cb(event);
			},
			onReprocessProgress(event) {
				for (const cb of reprocessProgressCallbacks) cb(event);
			},
			onReprocessCompleted(event) {
				for (const cb of reprocessCompletedCallbacks) cb(event);
			},
			onReprocessCancelled(event) {
				for (const cb of reprocessCancelledCallbacks) cb(event);
			},
		});
	}

	function destroy() {
		disconnectSSE();
		stopPolling();
		sseConnected = false;
		documentUpdateCallbacks.clear();
		jobEventCallbacks.clear();
		importProgressCallbacks.clear();
		importCompletedCallbacks.clear();
		importFailedCallbacks.clear();
		reprocessProgressCallbacks.clear();
		reprocessCompletedCallbacks.clear();
		reprocessCancelledCallbacks.clear();
	}

	function onDocumentUpdated(callback: DocumentUpdatedCallback): () => void {
		documentUpdateCallbacks.add(callback);
		return () => {
			documentUpdateCallbacks.delete(callback);
		};
	}

	function onJobEvent(callback: JobEventCallback): () => void {
		jobEventCallbacks.add(callback);
		return () => {
			jobEventCallbacks.delete(callback);
		};
	}

	function onImportProgress(callback: ImportEventCallback): () => void {
		importProgressCallbacks.add(callback);
		return () => {
			importProgressCallbacks.delete(callback);
		};
	}

	function onImportCompleted(callback: ImportEventCallback): () => void {
		importCompletedCallbacks.add(callback);
		return () => {
			importCompletedCallbacks.delete(callback);
		};
	}

	function onImportFailed(callback: ImportEventCallback): () => void {
		importFailedCallbacks.add(callback);
		return () => {
			importFailedCallbacks.delete(callback);
		};
	}

	function onReprocessProgress(callback: ReprocessEventCallback): () => void {
		reprocessProgressCallbacks.add(callback);
		return () => {
			reprocessProgressCallbacks.delete(callback);
		};
	}

	function onReprocessCompleted(callback: ReprocessEventCallback): () => void {
		reprocessCompletedCallbacks.add(callback);
		return () => {
			reprocessCompletedCallbacks.delete(callback);
		};
	}

	function onReprocessCancelled(callback: ReprocessEventCallback): () => void {
		reprocessCancelledCallbacks.add(callback);
		return () => {
			reprocessCancelledCallbacks.delete(callback);
		};
	}

	return {
		subscribe,
		track,
		dismiss,
		clearCompleted,
		init,
		destroy,
		onDocumentUpdated,
		onJobEvent,
		onImportProgress,
		onImportCompleted,
		onImportFailed,
		onReprocessProgress,
		onReprocessCompleted,
		onReprocessCancelled,
	};
}

export const jobStore = createJobStore();
