<script lang="ts">
	import JobStatusBadge from '$lib/components/jobs/JobStatusBadge.svelte';
	import JobProgressBar from '$lib/components/jobs/JobProgressBar.svelte';

	interface Props {
		fileName: string;
		status: 'uploading' | 'pending' | 'processing' | 'completed' | 'failed';
		progress: number;
		error?: string | null;
	}

	let { fileName, status, progress, error }: Props = $props();
</script>

<div class="card p-4">
	<div class="flex items-center justify-between mb-2">
		<div class="flex items-center gap-2 min-w-0">
			<span class="i-lucide-file-text text-gray-400 flex-shrink-0"></span>
			<span class="text-sm text-gray-700 dark:text-gray-300 truncate">{fileName}</span>
		</div>
		{#if status === 'uploading'}
			<span class="badge bg-blue-100 text-blue-800">
				<span class="i-lucide-loader-2 animate-spin mr-1 text-xs"></span>
				uploading
			</span>
		{:else}
			<JobStatusBadge {status} />
		{/if}
	</div>

	<JobProgressBar {progress} />

	{#if error}
		<p class="text-xs text-red-600 mt-2">{error}</p>
	{/if}
</div>
