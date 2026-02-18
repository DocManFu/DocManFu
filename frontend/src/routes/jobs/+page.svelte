<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { listAllJobs, cancelJob } from '$lib/api/jobs.js';
	import { jobStore } from '$lib/stores/jobs.js';
	import { toasts } from '$lib/stores/toast.js';
	import { formatRelativeTime, formatDocumentType } from '$lib/utils/format.js';
	import type { JobListItem } from '$lib/types/index.js';
	import Pagination from '$lib/components/shared/Pagination.svelte';
	import LoadingSpinner from '$lib/components/shared/LoadingSpinner.svelte';
	import EmptyState from '$lib/components/shared/EmptyState.svelte';
	import ConfirmDialog from '$lib/components/shared/ConfirmDialog.svelte';
	import JobStatusBadge from '$lib/components/jobs/JobStatusBadge.svelte';
	import JobProgressBar from '$lib/components/jobs/JobProgressBar.svelte';

	type StatusTab = 'all' | 'pending' | 'processing' | 'completed' | 'failed';

	const statusTabs: { key: StatusTab; label: string }[] = [
		{ key: 'all', label: 'All' },
		{ key: 'pending', label: 'Pending' },
		{ key: 'processing', label: 'Processing' },
		{ key: 'completed', label: 'Completed' },
		{ key: 'failed', label: 'Failed' },
	];

	const jobTypeOptions = [
		{ value: '', label: 'All Types' },
		{ value: 'ocr', label: 'OCR' },
		{ value: 'ai_analysis', label: 'AI Analysis' },
	];

	let jobs = $state<JobListItem[]>([]);
	let total = $state(0);
	let loading = $state(true);
	let activeTab = $state<StatusTab>('all');
	let jobTypeFilter = $state('');
	let offset = $state(0);
	let limit = 50;

	// Cancel dialog state
	let cancelDialogOpen = $state(false);
	let cancelTargetJob = $state<JobListItem | null>(null);

	function formatJobType(type: string): string {
		if (type === 'ocr') return 'OCR';
		if (type === 'ai_analysis') return 'AI Analysis';
		if (type === 'file_organization') return 'File Org';
		return type;
	}

	function formatDuration(job: JobListItem): string {
		const start = job.started_at;
		const end = job.completed_at;
		if (!start) return '—';
		const startMs = new Date(start).getTime();
		const endMs = end ? new Date(end).getTime() : Date.now();
		const diffSec = Math.floor((endMs - startMs) / 1000);
		if (diffSec < 60) return `${diffSec}s`;
		const mins = Math.floor(diffSec / 60);
		const secs = diffSec % 60;
		return `${mins}m ${secs}s`;
	}

	async function fetchJobs() {
		loading = true;
		try {
			const res = await listAllJobs({
				status: activeTab === 'all' ? undefined : activeTab,
				job_type: jobTypeFilter || undefined,
				offset,
				limit,
			});
			jobs = res.jobs;
			total = res.total;
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to load jobs');
		} finally {
			loading = false;
		}
	}

	function switchTab(tab: StatusTab) {
		activeTab = tab;
		offset = 0;
		fetchJobs();
	}

	function handleTypeChange(e: Event) {
		jobTypeFilter = (e.target as HTMLSelectElement).value;
		offset = 0;
		fetchJobs();
	}

	function handlePageChange(newOffset: number) {
		offset = newOffset;
		fetchJobs();
	}

	function openCancelDialog(job: JobListItem, e: Event) {
		e.stopPropagation();
		cancelTargetJob = job;
		cancelDialogOpen = true;
	}

	async function confirmCancel() {
		if (!cancelTargetJob) return;
		try {
			await cancelJob(cancelTargetJob.id);
			toasts.success('Job cancelled');
			cancelDialogOpen = false;
			cancelTargetJob = null;
			fetchJobs();
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to cancel job');
		}
	}

	function closeCancelDialog() {
		cancelDialogOpen = false;
		cancelTargetJob = null;
	}

	// Real-time updates via SSE
	let unsubscribeJobEvent: (() => void) | null = null;
	let debounceTimer: ReturnType<typeof setTimeout> | null = null;

	function debouncedRefetch() {
		if (debounceTimer) clearTimeout(debounceTimer);
		debounceTimer = setTimeout(() => {
			fetchJobs();
		}, 500);
	}

	onMount(() => {
		fetchJobs();
		unsubscribeJobEvent = jobStore.onJobEvent(() => {
			debouncedRefetch();
		});
	});

	onDestroy(() => {
		if (unsubscribeJobEvent) unsubscribeJobEvent();
		if (debounceTimer) clearTimeout(debounceTimer);
	});
</script>

<svelte:head>
	<title>Jobs - DocManFu</title>
</svelte:head>

<div class="page-container">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">Jobs Queue</h1>
		<select
			class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-brand-500 dark:bg-gray-800 dark:border-gray-600 dark:text-gray-100"
			onchange={handleTypeChange}
		>
			{#each jobTypeOptions as opt}
				<option value={opt.value} selected={jobTypeFilter === opt.value}>{opt.label}</option>
			{/each}
		</select>
	</div>

	<!-- Status Tabs -->
	<div class="flex gap-1 mb-6 border-b border-gray-200 dark:border-gray-700">
		{#each statusTabs as tab}
			<button
				class="px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px
					{activeTab === tab.key
					? 'border-brand-600 text-brand-600 dark:border-brand-400 dark:text-brand-400'
					: 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'}"
				onclick={() => switchTab(tab.key)}
			>
				{tab.label}
			</button>
		{/each}
	</div>

	{#if loading}
		<LoadingSpinner />
	{:else if jobs.length === 0}
		<EmptyState
			icon="i-lucide-activity"
			title="No jobs found"
			description={activeTab === 'all'
				? 'Upload a document to start processing.'
				: `No ${activeTab} jobs.`}
		/>
	{:else}
		<div class="card overflow-hidden">
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr
							class="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50"
						>
							<th class="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400"
								>Document</th
							>
							<th class="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Type</th>
							<th class="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400"
								>Status</th
							>
							<th class="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400 w-32"
								>Progress</th
							>
							<th class="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400"
								>Created</th
							>
							<th class="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400"
								>Duration</th
							>
							<th class="text-right px-4 py-3 font-medium text-gray-600 dark:text-gray-400"
								>Actions</th
							>
						</tr>
					</thead>
					<tbody>
						{#each jobs as job (job.id)}
							<!-- svelte-ignore a11y_click_events_have_key_events -->
							<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
							<tr
								class="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/30 cursor-pointer transition-colors"
								onclick={() => goto(`/documents/${job.document_id}`)}
							>
								<td
									class="px-4 py-3 font-medium text-gray-900 dark:text-gray-100 max-w-xs truncate"
								>
									{job.document_name}
								</td>
								<td class="px-4 py-3 text-gray-600 dark:text-gray-400">
									{formatJobType(job.job_type)}
								</td>
								<td class="px-4 py-3">
									<JobStatusBadge status={job.status} />
								</td>
								<td class="px-4 py-3">
									{#if job.status === 'processing'}
										<div class="flex items-center gap-2">
											<div class="flex-1">
												<JobProgressBar progress={job.progress} />
											</div>
											<span class="text-xs text-gray-500 dark:text-gray-400 w-8 text-right"
												>{job.progress}%</span
											>
										</div>
									{:else if job.status === 'completed'}
										<span class="text-xs text-gray-500 dark:text-gray-400">100%</span>
									{:else if job.status === 'failed'}
										<span
											class="text-xs text-red-500 dark:text-red-400 truncate max-w-[8rem] inline-block"
											title={job.error_message || ''}
										>
											{job.error_message || 'Failed'}
										</span>
									{:else}
										<span class="text-xs text-gray-400">—</span>
									{/if}
								</td>
								<td class="px-4 py-3 text-gray-600 dark:text-gray-400 whitespace-nowrap">
									{formatRelativeTime(job.created_at)}
								</td>
								<td class="px-4 py-3 text-gray-600 dark:text-gray-400 whitespace-nowrap">
									{formatDuration(job)}
								</td>
								<td class="px-4 py-3 text-right">
									{#if job.status === 'pending' || job.status === 'processing'}
										<button
											class="btn-ghost btn-sm text-xs text-red-600 hover:text-red-700 dark:text-red-400"
											onclick={(e) => openCancelDialog(job, e)}
										>
											Cancel
										</button>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>

		<div class="mt-4">
			<Pagination {total} {offset} {limit} onchange={handlePageChange} />
		</div>
	{/if}
</div>

<ConfirmDialog
	open={cancelDialogOpen}
	title="Cancel Job"
	message="Are you sure you want to cancel this job? This action cannot be undone."
	confirmLabel="Cancel Job"
	onconfirm={confirmCancel}
	oncancel={closeCancelDialog}
/>
