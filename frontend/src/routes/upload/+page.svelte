<script lang="ts">
	import DropZone from '$lib/components/upload/DropZone.svelte';
	import UploadProgress from '$lib/components/upload/UploadProgress.svelte';
	import { uploadDocument } from '$lib/api/documents.js';
	import { jobStore } from '$lib/stores/jobs.js';
	import { toasts } from '$lib/stores/toast.js';

	interface UploadItem {
		id: number;
		file: File;
		status: 'uploading' | 'pending' | 'processing' | 'completed' | 'failed';
		progress: number;
		error: string | null;
		jobId: string | null;
	}

	let uploads = $state<UploadItem[]>([]);
	let nextId = 0;
	let uploading = $state(false);

	async function handleFiles(files: File[]) {
		const startIndex = uploads.length;
		const newItems: UploadItem[] = files.map((file) => ({
			id: nextId++,
			file,
			status: 'uploading' as const,
			progress: 0,
			error: null,
			jobId: null
		}));

		uploads = [...uploads, ...newItems];

		for (let i = 0; i < newItems.length; i++) {
			await uploadFile(startIndex + i);
		}
	}

	async function uploadFile(index: number) {
		uploading = true;
		const item = uploads[index];
		try {
			uploads[index].progress = 50;
			const res = await uploadDocument(item.file);

			uploads[index].status = 'completed';
			uploads[index].progress = 100;
			uploads[index].jobId = res.job_id;

			jobStore.track(res.job_id, res.id, item.file.name);
			toasts.success(`${item.file.name} uploaded`);
		} catch (e) {
			uploads[index].status = 'failed';
			uploads[index].error = e instanceof Error ? e.message : 'Upload failed';
			toasts.error(`Failed to upload ${item.file.name}`);
		} finally {
			uploading = false;
		}
	}

	function clearCompleted() {
		uploads = uploads.filter((u) => u.status !== 'completed' && u.status !== 'failed');
	}

	let hasCompleted = $derived(uploads.some((u) => u.status === 'completed' || u.status === 'failed'));
</script>

<svelte:head>
	<title>Upload - DocManFu</title>
</svelte:head>

<div class="page-container">
	<h1 class="text-2xl font-bold text-gray-900 mb-6">Upload Documents</h1>

	<DropZone onfiles={handleFiles} disabled={uploading} />

	{#if uploads.length > 0}
		<div class="mt-6">
			<div class="flex items-center justify-between mb-3">
				<h2 class="text-sm font-medium text-gray-700">Uploads</h2>
				{#if hasCompleted}
					<button class="btn-ghost btn-sm text-xs" onclick={clearCompleted}>Clear finished</button>
				{/if}
			</div>
			<div class="space-y-3">
				{#each uploads as item (item.id)}
					<UploadProgress
						fileName={item.file.name}
						status={item.status}
						progress={item.progress}
						error={item.error}
					/>
				{/each}
			</div>
		</div>
	{/if}
</div>
