<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { isAdmin } from '$lib/stores/auth.js';
	import { toasts } from '$lib/stores/toast.js';
	import {
		getReprocessStats,
		getActiveReprocess,
		startBatchReprocess,
		pauseReprocess,
		resumeReprocess,
		skipCurrentDocument,
		cancelReprocess,
		type ReprocessStats,
	} from '$lib/api/imports.js';
	import { jobStore } from '$lib/stores/jobs.js';
	import type { ReprocessEvent } from '$lib/api/events.js';

	let reprocessStats = $state<ReprocessStats | null>(null);
	let selectedFilter = $state<string>('all');
	let selectedJobType = $state<string>('ocr');
	let starting = $state(false);
	let activeTaskId = $state<string | null>(null);
	let progress = $state<ReprocessEvent | null>(null);
	let paused = $state(false);
	let actionPending = $state(false);
	let results = $state<ReprocessEvent[]>([]);
	let unsubscribers: Array<() => void> = [];

	onMount(() => {
		if (!$isAdmin) {
			goto('/documents');
			return;
		}
		loadStats();
		checkActiveJob();

		unsubscribers.push(
			jobStore.onReprocessProgress((data) => {
				activeTaskId = data.task_id;
				progress = data;
				paused = !!data.paused;
			}),
			jobStore.onReprocessCompleted((data) => {
				activeTaskId = null;
				progress = null;
				paused = false;
				results = [data, ...results];
				toasts.success(`Processing complete: ${data.succeeded}/${data.total} succeeded`);
				loadStats();
			}),
			jobStore.onReprocessCancelled((data) => {
				activeTaskId = null;
				progress = null;
				paused = false;
				results = [data, ...results];
				toasts.success('Processing cancelled');
				loadStats();
			}),
		);
	});

	onDestroy(() => {
		unsubscribers.forEach((u) => u());
	});

	async function loadStats() {
		try {
			reprocessStats = await getReprocessStats();
		} catch {
			/* ignore */
		}
	}

	async function checkActiveJob() {
		try {
			const active = await getActiveReprocess();
			if (active.active && active.task_id) {
				activeTaskId = active.task_id;
				paused = !!active.paused;
			}
		} catch {
			/* ignore */
		}
	}

	async function handleStart() {
		starting = true;
		try {
			const res = await startBatchReprocess(selectedJobType, selectedFilter);
			activeTaskId = res.task_id;
			toasts.success(`Processing ${res.total} documents (${selectedJobType.toUpperCase()})...`);
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to start');
		} finally {
			starting = false;
		}
	}

	async function handlePauseResume() {
		if (!activeTaskId) return;
		actionPending = true;
		try {
			if (paused) {
				await resumeReprocess(activeTaskId);
				paused = false;
			} else {
				await pauseReprocess(activeTaskId);
				paused = true;
			}
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed');
		} finally {
			actionPending = false;
		}
	}

	async function handleSkip() {
		if (!activeTaskId) return;
		actionPending = true;
		try {
			await skipCurrentDocument(activeTaskId);
			toasts.success('Skipping current document...');
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to skip');
		} finally {
			actionPending = false;
		}
	}

	async function handleCancel() {
		if (!activeTaskId) return;
		actionPending = true;
		try {
			await cancelReprocess(activeTaskId);
			toasts.success('Cancelling...');
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to cancel');
		} finally {
			actionPending = false;
		}
	}

	let percent = $derived(
		progress ? Math.round((progress.current / Math.max(progress.total, 1)) * 100) : 0,
	);
	let isRunning = $derived(!!activeTaskId);
	let filterCount = $derived(
		reprocessStats
			? selectedFilter === 'no_text'
				? reprocessStats.no_text
				: selectedFilter === 'no_ai'
					? reprocessStats.no_ai
					: reprocessStats.total
			: 0,
	);

	// Auto-select smart default filter when job type changes
	$effect(() => {
		if (selectedJobType === 'ai') {
			selectedFilter = 'no_ai';
		} else {
			selectedFilter = 'no_text';
		}
	});
</script>

<svelte:head>
	<title>Processing - DocManFu</title>
</svelte:head>

<div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
	<!-- Admin tabs -->
	<div class="flex gap-1 mb-6 border-b border-gray-200 dark:border-gray-700">
		<a
			href="/admin/users"
			class="px-4 py-2 text-sm font-medium no-underline border-b-2 border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
			>Users</a
		>
		<a
			href="/admin/settings"
			class="px-4 py-2 text-sm font-medium no-underline border-b-2 border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
			>Settings</a
		>
		<a
			href="/admin/import"
			class="px-4 py-2 text-sm font-medium no-underline border-b-2 border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
			>Import</a
		>
		<a
			href="/admin/processing"
			class="px-4 py-2 text-sm font-medium no-underline border-b-2 border-brand-500 text-brand-600 dark:text-brand-400"
			>Processing</a
		>
	</div>

	<div class="mb-6">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">Batch Processing</h1>
		<p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
			Run OCR text extraction or AI analysis across your document library. Pause, resume, or cancel
			anytime.
		</p>
	</div>

	<!-- Stats cards -->
	{#if reprocessStats}
		<div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
			<div
				class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 text-center"
			>
				<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">{reprocessStats.total}</p>
				<p class="text-sm text-gray-500 dark:text-gray-400">Total Documents</p>
			</div>
			<div
				class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 text-center"
			>
				<p class="text-2xl font-bold text-green-600 dark:text-green-400">
					{reprocessStats.with_text}
				</p>
				<p class="text-sm text-gray-500 dark:text-gray-400">With Text</p>
			</div>
			<div
				class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 text-center"
			>
				<p class="text-2xl font-bold text-amber-600 dark:text-amber-400">
					{reprocessStats.no_text}
				</p>
				<p class="text-sm text-gray-500 dark:text-gray-400">Missing Text</p>
			</div>
			<div
				class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 text-center"
			>
				<p class="text-2xl font-bold text-purple-600 dark:text-purple-400">
					{reprocessStats.no_ai}
				</p>
				<p class="text-sm text-gray-500 dark:text-gray-400">Ready for AI</p>
				{#if reprocessStats.no_ai_needs_ocr > 0}
					<p class="text-xs text-amber-500 mt-0.5">
						+{reprocessStats.no_ai_needs_ocr} need OCR first
					</p>
				{/if}
			</div>
		</div>
	{/if}

	{#if isRunning}
		<!-- Active job -->
		<div
			class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 mb-8"
		>
			{#if progress}
				<div class="mb-4">
					<div class="flex justify-between text-sm text-gray-500 dark:text-gray-400 mb-1.5">
						<span>{progress.current} / {progress.total} documents</span>
						<span>{percent}%</span>
					</div>
					<div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3 mb-3">
						<div
							class="h-3 rounded-full transition-all duration-150 {paused
								? 'bg-amber-500'
								: 'bg-brand-500'}"
							style="width: {percent}%"
						></div>
					</div>
					{#if progress.current_document}
						<p class="text-sm text-gray-700 dark:text-gray-300 truncate">
							<span class="i-lucide-file-text w-3.5 h-3.5 inline-block mr-1 align-text-bottom"
							></span>
							{progress.current_document}
						</p>
					{/if}
					{#if paused}
						<p class="text-sm text-amber-600 dark:text-amber-400 font-medium mt-2">
							<span class="i-lucide-pause-circle w-4 h-4 inline-block mr-1 align-text-bottom"
							></span> Paused
						</p>
					{/if}
					<div class="flex gap-3 text-xs text-gray-400 dark:text-gray-500 mt-2">
						<span class="text-green-600 dark:text-green-400">{progress.succeeded} succeeded</span>
						{#if progress.failed > 0}<span class="text-red-600 dark:text-red-400"
								>{progress.failed} failed</span
							>{/if}
						{#if progress.skipped > 0}<span>{progress.skipped} skipped</span>{/if}
					</div>
				</div>
				<div class="flex gap-3">
					<button
						class="px-4 py-1.5 text-sm font-medium rounded-lg border transition-colors disabled:opacity-50
							{paused
							? 'border-green-300 dark:border-green-700 text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/20'
							: 'border-amber-300 dark:border-amber-700 text-amber-600 dark:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-900/20'}"
						onclick={handlePauseResume}
						disabled={actionPending}
					>
						{#if paused}
							<span class="i-lucide-play w-3.5 h-3.5 inline-block mr-1 align-text-bottom"
							></span>Resume
						{:else}
							<span class="i-lucide-pause w-3.5 h-3.5 inline-block mr-1 align-text-bottom"
							></span>Pause
						{/if}
					</button>
					<button
						class="px-4 py-1.5 text-sm font-medium rounded-lg border border-blue-300 dark:border-blue-700 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors disabled:opacity-50"
						onclick={handleSkip}
						disabled={actionPending}
						title="Skip the current document and continue with the next one"
					>
						<span class="i-lucide-skip-forward w-3.5 h-3.5 inline-block mr-1 align-text-bottom"
						></span>Skip
					</button>
					<button
						class="px-4 py-1.5 text-sm font-medium rounded-lg border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors disabled:opacity-50"
						onclick={handleCancel}
						disabled={actionPending}
					>
						<span class="i-lucide-x w-3.5 h-3.5 inline-block mr-1 align-text-bottom"></span>Cancel
					</button>
				</div>
			{:else}
				<div class="flex items-center gap-3">
					<span class="i-lucide-loader-2 w-6 h-6 text-brand-500 animate-spin"></span>
					<span class="text-gray-700 dark:text-gray-300">Starting batch processing...</span>
				</div>
			{/if}
		</div>
	{:else}
		<!-- Start controls -->
		<div
			class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 mb-8"
		>
			<div class="grid grid-cols-1 sm:grid-cols-3 gap-4 items-end">
				<div>
					<label
						for="job-type"
						class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Job Type</label
					>
					<select
						id="job-type"
						class="block w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-900 dark:text-gray-100"
						bind:value={selectedJobType}
					>
						<option value="ocr">OCR / Text Extraction</option>
						<option value="ai">AI Analysis</option>
					</select>
				</div>
				<div>
					<label
						for="filter"
						class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Documents</label
					>
					<select
						id="filter"
						class="block w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-900 dark:text-gray-100"
						bind:value={selectedFilter}
					>
						<option value="all">All documents ({reprocessStats?.total ?? '...'})</option>
						{#if selectedJobType === 'ocr'}
							<option value="no_text">Missing text only ({reprocessStats?.no_text ?? '...'})</option
							>
						{:else}
							<option value="no_ai">Missing AI analysis ({reprocessStats?.no_ai ?? '...'})</option>
						{/if}
					</select>
				</div>
				<div>
					<button
						class="w-full px-5 py-2 text-sm font-medium rounded-lg bg-brand-600 text-white hover:bg-brand-700 transition-colors disabled:opacity-50"
						onclick={handleStart}
						disabled={starting || filterCount === 0}
					>
						{#if starting}
							<span
								class="i-lucide-loader-2 w-4 h-4 inline-block mr-1 animate-spin align-text-bottom"
							></span>Starting...
						{:else}
							<span class="i-lucide-cpu w-4 h-4 inline-block mr-1 align-text-bottom"></span>
							Start ({filterCount})
						{/if}
					</button>
				</div>
			</div>

			<!-- Job type descriptions -->
			<div class="mt-4 text-sm text-gray-500 dark:text-gray-400">
				{#if selectedJobType === 'ocr'}
					<p>
						<strong>OCR / Text Extraction</strong> — Extracts embedded text from PDFs (instant) and runs
						Tesseract OCR on scanned PDFs and images. Makes documents searchable.
					</p>
				{:else}
					<p>
						<strong>AI Analysis</strong> — Runs AI-powered document analysis to generate summaries, extract
						metadata, and classify document types. Requires an AI provider to be configured in Settings.
					</p>
					{#if reprocessStats && reprocessStats.no_ai_needs_ocr > 0}
						<div
							class="mt-3 flex items-start gap-2 p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300"
						>
							<span class="i-lucide-alert-triangle w-4 h-4 mt-0.5 shrink-0"></span>
							<p>
								<strong>{reprocessStats.no_ai_needs_ocr} documents</strong> need OCR text extraction
								before AI analysis can run on them.
								<a
									href="/admin/processing"
									class="underline"
									onclick={() => {
										selectedJobType = 'ocr';
									}}>Run OCR first</a
								> on documents missing text.
							</p>
						</div>
					{/if}
				{/if}
			</div>
		</div>
	{/if}

	<!-- Completed results -->
	{#each results as result}
		<div
			class="mb-6 bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden"
		>
			<div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
				<div class="flex items-center justify-between">
					<h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100">Batch Processing</h3>
					<span
						class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium
						{result.status === 'cancelled'
							? 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400'
							: result.status === 'blocked'
								? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
								: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'}"
					>
						{result.status === 'cancelled'
							? 'Cancelled'
							: result.status === 'blocked'
								? 'Blocked'
								: 'Complete'}
					</span>
				</div>
			</div>
			<div class="grid grid-cols-2 sm:grid-cols-4 gap-4 p-6">
				<div class="text-center">
					<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">{result.total}</p>
					<p class="text-sm text-gray-500 dark:text-gray-400">Total</p>
				</div>
				<div class="text-center">
					<p class="text-2xl font-bold text-green-600 dark:text-green-400">{result.succeeded}</p>
					<p class="text-sm text-gray-500 dark:text-gray-400">Succeeded</p>
				</div>
				<div class="text-center">
					<p class="text-2xl font-bold text-red-600 dark:text-red-400">{result.failed}</p>
					<p class="text-sm text-gray-500 dark:text-gray-400">Failed</p>
				</div>
				<div class="text-center">
					<p class="text-2xl font-bold text-gray-400 dark:text-gray-500">{result.skipped}</p>
					<p class="text-sm text-gray-500 dark:text-gray-400">Skipped</p>
				</div>
			</div>
			{#if result.errors && result.errors.length > 0}
				<div class="border-t border-gray-200 dark:border-gray-700 px-6 py-4">
					<h4 class="text-sm font-semibold text-red-700 dark:text-red-400 mb-3">
						Errors ({result.errors.length})
					</h4>
					<div class="space-y-2 max-h-64 overflow-y-auto">
						{#each result.errors as err}
							<div class="flex items-start gap-3 text-sm p-2 rounded bg-red-50 dark:bg-red-900/20">
								<span class="i-lucide-x-circle w-4 h-4 text-red-500 mt-0.5 shrink-0"></span>
								<div>
									<p class="font-medium text-gray-800 dark:text-gray-200">{err.document}</p>
									<p class="text-red-600 dark:text-red-400 font-mono text-xs">{err.error}</p>
								</div>
							</div>
						{/each}
					</div>
				</div>
			{/if}
		</div>
	{/each}
</div>
