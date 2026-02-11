<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import {
		getDocument,
		updateDocument,
		deleteDocument,
		reprocessDocument,
		getDownloadUrl
	} from '$lib/api/documents.js';
	import type { DocumentDetail } from '$lib/types/index.js';
	import DocumentMeta from '$lib/components/documents/DocumentMeta.svelte';
	import TagInput from '$lib/components/tags/TagInput.svelte';
	import ConfirmDialog from '$lib/components/shared/ConfirmDialog.svelte';
	import LoadingSpinner from '$lib/components/shared/LoadingSpinner.svelte';
	import { toasts } from '$lib/stores/toast.js';
	import { jobStore } from '$lib/stores/jobs.js';

	let doc = $state<DocumentDetail | null>(null);
	let loading = $state(true);
	let error = $state('');

	// Edit state
	let editingName = $state(false);
	let editName = $state('');
	let saving = $state(false);

	// Delete state
	let showDeleteDialog = $state(false);
	let deleting = $state(false);

	// Reprocess state
	let reprocessing = $state(false);

	let displayName = $derived(doc?.ai_generated_name || doc?.original_name || '');

	async function loadDocument() {
		loading = true;
		error = '';
		try {
			doc = await getDocument($page.params.id);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load document';
		} finally {
			loading = false;
		}
	}

	function startEditName() {
		editName = doc?.original_name ?? '';
		editingName = true;
	}

	async function saveName() {
		if (!doc || !editName.trim()) return;
		saving = true;
		try {
			doc = await updateDocument(doc.id, { original_name: editName.trim() });
			editingName = false;
			toasts.success('Name updated');
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to update name');
		} finally {
			saving = false;
		}
	}

	function cancelEditName() {
		editingName = false;
	}

	async function handleTagsChange(tagNames: string[]) {
		if (!doc) return;
		try {
			doc = await updateDocument(doc.id, { tags: tagNames });
			toasts.success('Tags updated');
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to update tags');
		}
	}

	async function handleDelete() {
		if (!doc) return;
		deleting = true;
		try {
			await deleteDocument(doc.id);
			toasts.success('Document deleted');
			goto('/documents');
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to delete document');
		} finally {
			deleting = false;
			showDeleteDialog = false;
		}
	}

	async function handleReprocess() {
		if (!doc) return;
		reprocessing = true;
		try {
			const res = await reprocessDocument(doc.id);
			for (const job of res.jobs) {
				jobStore.track(job.job_id, doc.id, displayName);
			}
			toasts.success(res.message);
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to reprocess');
		} finally {
			reprocessing = false;
		}
	}

	function handleNameKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') saveName();
		if (e.key === 'Escape') cancelEditName();
	}

	onMount(loadDocument);
</script>

<svelte:head>
	<title>{displayName || 'Document'} - DocManFu</title>
</svelte:head>

<div class="page-container">
	{#if loading}
		<LoadingSpinner />
	{:else if error}
		<div class="text-center py-16">
			<span class="i-lucide-alert-circle text-4xl text-red-400 mb-4 block mx-auto"></span>
			<p class="text-gray-600 mb-4">{error}</p>
			<a href="/documents" class="btn-primary no-underline">Back to Documents</a>
		</div>
	{:else if doc}
		<!-- Header -->
		<div class="mb-6">
			<a href="/documents" class="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-3 no-underline">
				<span class="i-lucide-arrow-left"></span>
				Back to documents
			</a>

			<div class="flex items-start justify-between gap-4">
				<div class="flex-1 min-w-0">
					{#if editingName}
						<div class="flex items-center gap-2">
							<input
								type="text"
								class="input-base text-lg font-bold"
								bind:value={editName}
								onkeydown={handleNameKeydown}
							/>
							<button class="btn-primary btn-sm" onclick={saveName} disabled={saving}>Save</button>
							<button class="btn-ghost btn-sm" onclick={cancelEditName}>Cancel</button>
						</div>
					{:else}
						<div class="flex items-center gap-2 group">
							<h1 class="text-2xl font-bold text-gray-900 truncate">{displayName}</h1>
							<button
								class="btn-icon opacity-0 group-hover:opacity-100"
								title="Edit name"
								onclick={startEditName}
							>
								<span class="i-lucide-pencil text-sm"></span>
							</button>
						</div>
						{#if doc.ai_generated_name && doc.ai_generated_name !== doc.original_name}
							<p class="text-sm text-gray-500 mt-1">Original: {doc.original_name}</p>
						{/if}
					{/if}
				</div>

				<div class="flex items-center gap-2 flex-shrink-0">
					<a
						href={getDownloadUrl(doc.id)}
						class="btn-secondary no-underline"
						download
					>
						<span class="i-lucide-download mr-1"></span>Download
					</a>
					<button
						class="btn-secondary"
						onclick={handleReprocess}
						disabled={reprocessing}
					>
						<span class="i-lucide-refresh-cw mr-1 {reprocessing ? 'animate-spin' : ''}"></span>
						Reprocess
					</button>
					<button
						class="btn-danger"
						onclick={() => (showDeleteDialog = true)}
					>
						<span class="i-lucide-trash-2 mr-1"></span>Delete
					</button>
				</div>
			</div>
		</div>

		<!-- Metadata -->
		<div class="card p-6 mb-6">
			<DocumentMeta document={doc} />
		</div>

		<!-- Tags -->
		<div class="card p-6 mb-6">
			<h3 class="text-sm font-medium text-gray-700 mb-3 flex items-center gap-1">
				<span class="i-lucide-tags"></span>
				Tags
			</h3>
			<TagInput tags={doc.tags} onchange={handleTagsChange} />
		</div>

		<!-- Content text -->
		{#if doc.content_text}
			<div class="card p-6">
				<h3 class="text-sm font-medium text-gray-700 mb-3 flex items-center gap-1">
					<span class="i-lucide-text"></span>
					Extracted Text
				</h3>
				<pre class="text-sm text-gray-600 whitespace-pre-wrap bg-gray-50 rounded-lg p-4 max-h-96 overflow-y-auto">{doc.content_text}</pre>
			</div>
		{/if}

		<ConfirmDialog
			open={showDeleteDialog}
			title="Delete Document"
			message="This will soft-delete the document. It won't appear in search results anymore. Are you sure?"
			confirmLabel={deleting ? 'Deleting...' : 'Delete'}
			onconfirm={handleDelete}
			oncancel={() => (showDeleteDialog = false)}
		/>
	{/if}
</div>
