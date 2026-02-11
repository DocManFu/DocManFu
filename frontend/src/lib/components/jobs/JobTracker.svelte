<script lang="ts">
	import { jobStore } from '$lib/stores/jobs.js';
	import JobStatusBadge from './JobStatusBadge.svelte';
	import JobProgressBar from './JobProgressBar.svelte';

	let expanded = $state(true);

	let hasJobs = $derived($jobStore.length > 0);
	let activeCount = $derived(
		$jobStore.filter((j) => j.status.status === 'pending' || j.status.status === 'processing')
			.length
	);
	let hasFinished = $derived(
		$jobStore.some((j) => j.status.status === 'completed' || j.status.status === 'failed')
	);
</script>

{#if hasJobs}
	<div class="fixed bottom-4 right-4 z-40 w-80">
		<div class="card shadow-lg overflow-hidden">
			<div class="flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-750 border-b border-gray-200 dark:border-gray-700">
				<button
					class="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 cursor-pointer"
					onclick={() => (expanded = !expanded)}
				>
					<span class="i-lucide-activity"></span>
					Jobs
					{#if activeCount > 0}
						<span class="badge bg-brand-100 text-brand-700">{activeCount} active</span>
					{/if}
					<span class="i-lucide-chevron-down text-gray-400 transition-transform {expanded ? '' : 'rotate-180'}"></span>
				</button>
				{#if hasFinished}
					<button
						class="text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 px-1 cursor-pointer"
						onclick={() => jobStore.clearCompleted()}
					>
						Clear
					</button>
				{/if}
			</div>

			{#if expanded}
				<div class="max-h-60 overflow-y-auto divide-y divide-gray-100 dark:divide-gray-700">
					{#each $jobStore as job (job.jobId)}
						<div class="px-4 py-3">
							<div class="flex items-center justify-between mb-1">
								<div class="truncate mr-2">
									<span class="text-sm text-gray-700 dark:text-gray-300 truncate">{job.fileName}</span>
									<span class="text-xs text-gray-400 dark:text-gray-500 ml-1">{job.status.job_type === 'ai_analysis' ? 'AI' : 'OCR'}</span>
								</div>
								<JobStatusBadge status={job.status.status} />
							</div>
							{#if job.status.status === 'processing'}
								<JobProgressBar progress={job.status.progress} />
							{/if}
							{#if job.status.error_message}
								<p class="text-xs text-red-600 mt-1">{job.status.error_message}</p>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		</div>
	</div>
{/if}
