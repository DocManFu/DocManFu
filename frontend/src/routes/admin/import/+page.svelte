<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { isAdmin } from '$lib/stores/auth.js';
	import { toasts } from '$lib/stores/toast.js';
	import { startEvernoteImport, cancelImport, type ImportResult } from '$lib/api/imports.js';
	import { jobStore } from '$lib/stores/jobs.js';
	import type { ImportEvent } from '$lib/api/events.js';

	let dragover = $state(false);
	let uploading = $state(false);
	let uploadPercent = $state(0);
	let uploadFileName = $state('');
	let importCancelling = $state(false);
	let activeImportId = $state<string | null>(null);
	let importProgress = $state<ImportEvent | null>(null);
	let completedImports = $state<ImportResult[]>([]);
	let unsubscribers: Array<() => void> = [];

	onMount(() => {
		if (!$isAdmin) {
			goto('/documents');
			return;
		}

		unsubscribers.push(
			jobStore.onImportProgress((data) => {
				activeImportId = data.task_id;
				importProgress = data;
			}),
			jobStore.onImportCompleted((data) => {
				activeImportId = null;
				importProgress = null;
				completedImports = [
					{
						filename: data.filename,
						total_notes: data.total_notes!,
						imported_notes: data.imported_notes!,
						documents_created: data.documents_created,
						errors: data.errors!,
						skipped: data.skipped || [],
						error_list: data.error_list || [],
					},
					...completedImports,
				];
				toasts.success(
					`Import complete: ${data.imported_notes} notes → ${data.documents_created} documents`,
				);
			}),
			jobStore.onImportFailed((data) => {
				activeImportId = null;
				importProgress = null;
				toasts.error(`Import failed: ${data.filename}`);
				if (data.error_list?.length) {
					completedImports = [
						{
							filename: data.filename,
							total_notes: data.total_notes || 0,
							imported_notes: data.imported_notes || 0,
							documents_created: data.documents_created,
							errors: data.errors || 0,
							skipped: data.skipped || [],
							error_list: data.error_list || [],
						},
						...completedImports,
					];
				}
			}),
		);
	});

	onDestroy(() => {
		unsubscribers.forEach((u) => u());
	});

	async function handleFile(file: File) {
		if (!file.name.toLowerCase().endsWith('.enex')) {
			toasts.error('Please upload an .enex file');
			return;
		}
		uploading = true;
		uploadPercent = 0;
		uploadFileName = file.name;
		try {
			const res = await startEvernoteImport(file, (loaded, total) => {
				uploadPercent = Math.round((loaded / total) * 100);
			});
			activeImportId = res.task_id;
			toasts.success(`Import started: ${file.name}`);
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to start import');
		} finally {
			uploading = false;
			uploadPercent = 0;
		}
	}

	function handleDrop(e: DragEvent) {
		e.preventDefault();
		dragover = false;
		const f = e.dataTransfer?.files[0];
		if (f) handleFile(f);
	}
	function handleDragOver(e: DragEvent) {
		e.preventDefault();
		dragover = true;
	}
	function handleFileInput(e: Event) {
		const input = e.target as HTMLInputElement;
		const f = input.files?.[0];
		if (f) handleFile(f);
		input.value = '';
	}

	async function handleImportCancel() {
		if (!activeImportId) return;
		importCancelling = true;
		try {
			await cancelImport(activeImportId);
			toasts.success('Import cancelled');
			activeImportId = null;
			importProgress = null;
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to cancel');
		} finally {
			importCancelling = false;
		}
	}

	let importPercent = $derived(
		importProgress
			? Math.round((importProgress.current / Math.max(importProgress.total, 1)) * 100)
			: 0,
	);
	let isImporting = $derived(!!activeImportId);
</script>

<svelte:head>
	<title>Import - DocManFu</title>
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
			class="px-4 py-2 text-sm font-medium no-underline border-b-2 border-brand-500 text-brand-600 dark:text-brand-400"
			>Import</a
		>
		<a
			href="/admin/processing"
			class="px-4 py-2 text-sm font-medium no-underline border-b-2 border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
			>Processing</a
		>
	</div>

	<div class="mb-6">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">Import</h1>
		<p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
			Import documents from Evernote ENEX export files. PDFs will have their text extracted
			automatically.
		</p>
	</div>

	<!-- Upload area -->
	<div
		class="relative border-2 border-dashed rounded-xl p-12 text-center transition-colors
			{dragover
			? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
			: 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'}"
		ondrop={handleDrop}
		ondragover={handleDragOver}
		ondragleave={() => (dragover = false)}
		role="button"
		tabindex="0"
	>
		{#if uploading}
			<div class="flex flex-col items-center gap-3 w-full">
				<span class="i-lucide-upload-cloud w-10 h-10 text-brand-500"></span>
				<p class="text-lg font-medium text-gray-700 dark:text-gray-300">
					Uploading {uploadFileName}...
				</p>
				<div class="w-full max-w-md">
					<div class="flex justify-between text-sm text-gray-500 dark:text-gray-400 mb-1">
						<span>Uploading</span><span>{uploadPercent}%</span>
					</div>
					<div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3">
						<div
							class="bg-brand-500 h-3 rounded-full transition-all duration-150"
							style="width: {uploadPercent}%"
						></div>
					</div>
				</div>
			</div>
		{:else if isImporting}
			<div class="flex flex-col items-center gap-4 w-full">
				{#if importProgress}
					<div class="w-full max-w-lg">
						<div class="flex justify-between text-sm text-gray-500 dark:text-gray-400 mb-1.5">
							<span>{importProgress.current} / {importProgress.total} notes</span>
							<span>{importPercent}%</span>
						</div>
						<div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3 mb-3">
							<div
								class="bg-brand-500 h-3 rounded-full transition-all duration-150"
								style="width: {importPercent}%"
							></div>
						</div>
						{#if importProgress.current_note}
							<p class="text-sm text-gray-700 dark:text-gray-300 truncate text-center">
								<span class="i-lucide-file-text w-3.5 h-3.5 inline-block mr-1 align-text-bottom"
								></span>
								{importProgress.current_note}
							</p>
						{/if}
						<p class="text-xs text-gray-400 dark:text-gray-500 mt-2 text-center">
							{importProgress.imported} imported → {importProgress.documents_created} documents created
						</p>
						<button
							class="mt-4 px-4 py-1.5 text-sm font-medium rounded-lg border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors disabled:opacity-50"
							onclick={handleImportCancel}
							disabled={importCancelling}
							>{importCancelling ? 'Cancelling...' : 'Cancel Import'}</button
						>
					</div>
				{:else}
					<span class="i-lucide-loader-2 w-10 h-10 text-brand-500 animate-spin"></span>
					<p class="text-lg font-medium text-gray-700 dark:text-gray-300">Preparing import...</p>
					<p class="text-sm text-gray-400 dark:text-gray-500">
						Scanning notes and starting background worker
					</p>
				{/if}
			</div>
		{:else}
			<div class="flex flex-col items-center gap-3">
				<span class="i-lucide-file-archive w-10 h-10 text-gray-400 dark:text-gray-500"></span>
				<div>
					<p class="text-lg font-medium text-gray-700 dark:text-gray-300">
						Drop an .enex file here
					</p>
					<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
						or <label class="text-brand-600 dark:text-brand-400 hover:underline cursor-pointer">
							browse <input type="file" accept=".enex" class="hidden" onchange={handleFileInput} />
						</label>
					</p>
				</div>
			</div>
		{/if}
	</div>

	<!-- Completed imports -->
	{#each completedImports as result}
		<div
			class="mt-6 bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden"
		>
			<div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
				<div class="flex items-center justify-between">
					<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{result.filename}</h2>
					<span
						class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium
						{result.errors > 0 && result.imported_notes === 0
							? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
							: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'}"
					>
						<span
							class="{result.errors > 0 && result.imported_notes === 0
								? 'i-lucide-x'
								: 'i-lucide-check'} w-3 h-3"
						></span>
						{result.errors > 0 && result.imported_notes === 0 ? 'Failed' : 'Complete'}
					</span>
				</div>
			</div>
			<div class="grid grid-cols-2 sm:grid-cols-4 gap-4 p-6">
				<div class="text-center">
					<p class="text-2xl font-bold text-gray-900 dark:text-gray-100">{result.total_notes}</p>
					<p class="text-sm text-gray-500 dark:text-gray-400">Total Notes</p>
				</div>
				<div class="text-center">
					<p class="text-2xl font-bold text-green-600 dark:text-green-400">
						{result.imported_notes}
					</p>
					<p class="text-sm text-gray-500 dark:text-gray-400">Imported</p>
				</div>
				<div class="text-center">
					<p class="text-2xl font-bold text-blue-600 dark:text-blue-400">
						{result.documents_created}
					</p>
					<p class="text-sm text-gray-500 dark:text-gray-400">Documents Created</p>
				</div>
				<div class="text-center">
					<p
						class="text-2xl font-bold {result.errors > 0
							? 'text-red-600 dark:text-red-400'
							: 'text-gray-400 dark:text-gray-500'}"
					>
						{result.errors}
					</p>
					<p class="text-sm text-gray-500 dark:text-gray-400">Errors</p>
				</div>
			</div>
			{#if result.skipped.length > 0}
				<div class="border-t border-gray-200 dark:border-gray-700 px-6 py-4">
					<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
						Skipped Notes ({result.skipped.length})
					</h3>
					<div class="space-y-2 max-h-64 overflow-y-auto">
						{#each result.skipped as item}
							<div
								class="flex items-start gap-3 text-sm p-2 rounded bg-gray-50 dark:bg-gray-700/50"
							>
								<span class="i-lucide-alert-circle w-4 h-4 text-amber-500 mt-0.5 shrink-0"></span>
								<div>
									<p class="font-medium text-gray-800 dark:text-gray-200">{item.title}</p>
									<p class="text-gray-500 dark:text-gray-400">{item.reason}</p>
								</div>
							</div>
						{/each}
					</div>
				</div>
			{/if}
			{#if result.error_list.length > 0}
				<div class="border-t border-gray-200 dark:border-gray-700 px-6 py-4">
					<h3 class="text-sm font-semibold text-red-700 dark:text-red-400 mb-3">
						Errors ({result.error_list.length})
					</h3>
					<div class="space-y-2 max-h-64 overflow-y-auto">
						{#each result.error_list as item}
							<div class="flex items-start gap-3 text-sm p-2 rounded bg-red-50 dark:bg-red-900/20">
								<span class="i-lucide-x-circle w-4 h-4 text-red-500 mt-0.5 shrink-0"></span>
								<div>
									<p class="font-medium text-gray-800 dark:text-gray-200">{item.title}</p>
									<p class="text-red-600 dark:text-red-400 font-mono text-xs">{item.error}</p>
								</div>
							</div>
						{/each}
					</div>
				</div>
			{/if}
		</div>
	{/each}

	<!-- Info section -->
	<div
		class="mt-8 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl p-6"
	>
		<h3 class="text-sm font-semibold text-blue-800 dark:text-blue-300 mb-2">
			<span class="i-lucide-info mr-1"></span> How it works
		</h3>
		<ul class="text-sm text-blue-700 dark:text-blue-400 space-y-1.5 list-disc list-inside">
			<li>Export your notes from Evernote as .enex files (Settings → Export)</li>
			<li>Upload the .enex file here — import runs in the background</li>
			<li>PDFs, images, Office docs, audio, video, and text notes are all imported</li>
			<li>PDF text is automatically extracted during import for full-text search</li>
			<li>Evernote tags are preserved and applied to imported documents</li>
			<li>
				After importing, use the <a href="/admin/processing" class="underline">Processing</a> tab to run
				batch OCR or AI analysis
			</li>
		</ul>
	</div>
</div>
