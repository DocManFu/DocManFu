/**
 * EventSource wrapper for SSE real-time events.
 */

export interface JobEvent {
	job_id: string;
	document_id: string;
	job_type: string;
	status: string;
	progress: number;
	result_data?: Record<string, unknown> | null;
	error_message?: string | null;
}

export interface DocumentUpdatedEvent {
	document_id: string;
	changes: string[];
}

export interface ImportEvent {
	task_id: string;
	user_id: string;
	filename: string;
	current: number;
	total: number;
	imported: number;
	documents_created: number;
	current_note?: string;
	status: string;
	// Present on completed/failed:
	total_notes?: number;
	imported_notes?: number;
	errors?: number;
	skipped?: Array<{
		title: string;
		reason: string;
		created: string;
		tags: string[];
		resources: Array<{ mime: string; filename: string | null; reason: string }>;
	}>;
	error_list?: Array<{ title: string; error: string }>;
}

export interface ReprocessEvent {
	task_id: string;
	user_id: string;
	current: number;
	total: number;
	succeeded: number;
	failed: number;
	skipped: number;
	current_document?: string;
	paused?: boolean;
	status: string;
	errors?: Array<{ document: string; error: string }>;
}

export interface SSEHandlers {
	onConnected?: () => void;
	onDisconnected?: () => void;
	onJobStarted?: (data: JobEvent) => void;
	onJobProgress?: (data: JobEvent) => void;
	onJobCompleted?: (data: JobEvent) => void;
	onJobFailed?: (data: JobEvent) => void;
	onDocumentUpdated?: (data: DocumentUpdatedEvent) => void;
	onImportProgress?: (data: ImportEvent) => void;
	onImportCompleted?: (data: ImportEvent) => void;
	onImportFailed?: (data: ImportEvent) => void;
	onReprocessProgress?: (data: ReprocessEvent) => void;
	onReprocessCompleted?: (data: ReprocessEvent) => void;
	onReprocessCancelled?: (data: ReprocessEvent) => void;
}

let eventSource: EventSource | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let currentHandlers: SSEHandlers | null = null;

function clearReconnectTimer() {
	if (reconnectTimer) {
		clearTimeout(reconnectTimer);
		reconnectTimer = null;
	}
}

function scheduleReconnect() {
	clearReconnectTimer();
	reconnectTimer = setTimeout(() => {
		if (currentHandlers) {
			connectSSE(currentHandlers);
		}
	}, 3000);
}

export function connectSSE(handlers: SSEHandlers): void {
	disconnectSSE();
	currentHandlers = handlers;

	// Pass JWT token as query param (EventSource doesn't support custom headers)
	let url = '/api/events';
	try {
		const raw = localStorage.getItem('docmanfu_auth');
		if (raw) {
			const stored = JSON.parse(raw);
			if (stored.accessToken) {
				url += `?token=${encodeURIComponent(stored.accessToken)}`;
			}
		}
	} catch {
		// localStorage unavailable
	}

	eventSource = new EventSource(url);

	eventSource.addEventListener('connected', () => {
		handlers.onConnected?.();
	});

	eventSource.addEventListener('job.started', (e) => {
		handlers.onJobStarted?.(JSON.parse((e as MessageEvent).data));
	});

	eventSource.addEventListener('job.progress', (e) => {
		handlers.onJobProgress?.(JSON.parse((e as MessageEvent).data));
	});

	eventSource.addEventListener('job.completed', (e) => {
		handlers.onJobCompleted?.(JSON.parse((e as MessageEvent).data));
	});

	eventSource.addEventListener('job.failed', (e) => {
		handlers.onJobFailed?.(JSON.parse((e as MessageEvent).data));
	});

	eventSource.addEventListener('document.updated', (e) => {
		handlers.onDocumentUpdated?.(JSON.parse((e as MessageEvent).data));
	});

	eventSource.addEventListener('import.progress', (e) => {
		handlers.onImportProgress?.(JSON.parse((e as MessageEvent).data));
	});

	eventSource.addEventListener('import.completed', (e) => {
		handlers.onImportCompleted?.(JSON.parse((e as MessageEvent).data));
	});

	eventSource.addEventListener('import.failed', (e) => {
		handlers.onImportFailed?.(JSON.parse((e as MessageEvent).data));
	});

	eventSource.addEventListener('reprocess.progress', (e) => {
		handlers.onReprocessProgress?.(JSON.parse((e as MessageEvent).data));
	});

	eventSource.addEventListener('reprocess.completed', (e) => {
		handlers.onReprocessCompleted?.(JSON.parse((e as MessageEvent).data));
	});

	eventSource.addEventListener('reprocess.cancelled', (e) => {
		handlers.onReprocessCancelled?.(JSON.parse((e as MessageEvent).data));
	});

	eventSource.onerror = () => {
		handlers.onDisconnected?.();
		eventSource?.close();
		eventSource = null;
		scheduleReconnect();
	};
}

export function disconnectSSE(): void {
	clearReconnectTimer();
	currentHandlers = null;
	if (eventSource) {
		eventSource.close();
		eventSource = null;
	}
}

export function isSSEConnected(): boolean {
	return eventSource !== null && eventSource.readyState === EventSource.OPEN;
}
