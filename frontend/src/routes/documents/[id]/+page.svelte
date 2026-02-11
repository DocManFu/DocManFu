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
	import { updateBillStatus } from '$lib/api/bills.js';
	import type { DocumentDetail, DocumentUpdateRequest } from '$lib/types/index.js';
	import DocumentMeta from '$lib/components/documents/DocumentMeta.svelte';
	import PdfPreview from '$lib/components/documents/PdfPreview.svelte';
	import TagInput from '$lib/components/tags/TagInput.svelte';
	import ConfirmDialog from '$lib/components/shared/ConfirmDialog.svelte';
	import LoadingSpinner from '$lib/components/shared/LoadingSpinner.svelte';
	import { toasts } from '$lib/stores/toast.js';
	import { jobStore } from '$lib/stores/jobs.js';

	let doc = $state<DocumentDetail | null>(null);
	let loading = $state(true);
	let error = $state('');

	// Edit state — original name
	let editingName = $state(false);
	let editName = $state('');
	let saving = $state(false);

	// Edit state — AI-generated name
	let editingAiName = $state(false);
	let editAiName = $state('');
	let savingAiName = $state(false);

	// Delete state
	let showDeleteDialog = $state(false);
	let deleting = $state(false);

	// Reprocess state
	let reprocessing = $state(false);

	// Bill state
	let updatingBill = $state(false);

	let searchQuery = $derived($page.url.searchParams.get('q') ?? '');

	let isBill = $derived(doc?.document_type === 'bill' || doc?.document_type === 'invoice' || !!doc?.bill_status);

	let displayName = $derived(doc?.ai_generated_name || doc?.original_name || '');

	async function loadDocument() {
		loading = true;
		error = '';
		try {
			doc = await getDocument($page.params.id!);
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

	function startEditAiName() {
		editAiName = doc?.ai_generated_name ?? '';
		editingAiName = true;
	}

	async function saveAiName() {
		if (!doc || !editAiName.trim()) return;
		savingAiName = true;
		try {
			doc = await updateDocument(doc.id, { ai_generated_name: editAiName.trim() });
			editingAiName = false;
			toasts.success('AI name updated');
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to update AI name');
		} finally {
			savingAiName = false;
		}
	}

	function cancelEditAiName() {
		editingAiName = false;
	}

	function handleAiNameKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') saveAiName();
		if (e.key === 'Escape') cancelEditAiName();
	}

	async function handleMetaUpdate(fields: DocumentUpdateRequest) {
		if (!doc) return;
		doc = await updateDocument(doc.id, fields);
		toasts.success('AI analysis updated');
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

	async function handleBillStatus(status: 'paid' | 'dismissed' | 'unpaid') {
		if (!doc) return;
		updatingBill = true;
		try {
			const res = await updateBillStatus(doc.id, status);
			doc.bill_status = res.bill_status;
			doc.bill_paid_at = res.bill_paid_at;
			toasts.success(res.detail);
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to update bill status');
		} finally {
			updatingBill = false;
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

{#if loading}
	<div class="page-container">
		<LoadingSpinner />
	</div>
{:else if error}
	<div class="page-container">
		<div class="text-center py-16">
			<span class="i-lucide-alert-circle text-4xl text-red-400 mb-4 block mx-auto"></span>
			<p class="text-gray-600 dark:text-gray-400 mb-4">{error}</p>
			<a href="/documents" class="btn-primary no-underline">Back to Documents</a>
		</div>
	</div>
{:else if doc}
	<div class="flex h-[calc(100vh-4rem)]">
		<!-- Left sidebar: metadata -->
		<div class="w-sm flex-shrink-0 border-r border-gray-200 dark:border-gray-700 overflow-y-auto p-4 space-y-4 bg-white dark:bg-gray-900">
			<a href="/documents" class="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 no-underline">
				<span class="i-lucide-arrow-left"></span>
				Back to documents
			</a>

			<!-- Name -->
			<div>
				{#if doc.ai_generated_name}
					<!-- AI name (primary display) -->
					{#if editingAiName}
						<div class="flex items-center gap-2">
							<input
								type="text"
								class="input-base text-base font-bold flex-1"
								bind:value={editAiName}
								onkeydown={handleAiNameKeydown}
							/>
							<button class="btn-primary btn-sm" onclick={saveAiName} disabled={savingAiName}>Save</button>
							<button class="btn-ghost btn-sm" onclick={cancelEditAiName}>Cancel</button>
						</div>
					{:else}
						<div class="flex items-center gap-1 group">
							<h1 class="text-lg font-bold text-gray-900 dark:text-gray-100 break-words">{doc.ai_generated_name}</h1>
							<button
								class="btn-icon opacity-0 group-hover:opacity-100 flex-shrink-0"
								title="Edit AI name"
								onclick={startEditAiName}
							>
								<span class="i-lucide-pencil text-sm"></span>
							</button>
						</div>
					{/if}
					<!-- Original name (secondary, also editable) -->
					{#if editingName}
						<div class="flex items-center gap-2 mt-1">
							<input
								type="text"
								class="input-base text-sm flex-1"
								bind:value={editName}
								onkeydown={handleNameKeydown}
							/>
							<button class="btn-primary btn-sm" onclick={saveName} disabled={saving}>Save</button>
							<button class="btn-ghost btn-sm" onclick={cancelEditName}>Cancel</button>
						</div>
					{:else}
						<div class="flex items-center gap-1 group mt-1">
							<p class="text-sm text-gray-500 dark:text-gray-400">Original: {doc.original_name}</p>
							<button
								class="btn-icon opacity-0 group-hover:opacity-100 flex-shrink-0"
								title="Edit original name"
								onclick={startEditName}
							>
								<span class="i-lucide-pencil text-xs"></span>
							</button>
						</div>
					{/if}
				{:else}
					<!-- No AI name — original name is primary -->
					{#if editingName}
						<div class="flex items-center gap-2">
							<input
								type="text"
								class="input-base text-base font-bold flex-1"
								bind:value={editName}
								onkeydown={handleNameKeydown}
							/>
							<button class="btn-primary btn-sm" onclick={saveName} disabled={saving}>Save</button>
							<button class="btn-ghost btn-sm" onclick={cancelEditName}>Cancel</button>
						</div>
					{:else}
						<div class="flex items-center gap-1 group">
							<h1 class="text-lg font-bold text-gray-900 dark:text-gray-100 break-words">{doc.original_name}</h1>
							<button
								class="btn-icon opacity-0 group-hover:opacity-100 flex-shrink-0"
								title="Edit name"
								onclick={startEditName}
							>
								<span class="i-lucide-pencil text-sm"></span>
							</button>
						</div>
					{/if}
				{/if}
			</div>

			<!-- Actions -->
			<div class="flex flex-wrap items-center gap-2">
				<a
					href={getDownloadUrl(doc.id)}
					class="btn-secondary btn-sm no-underline"
					download
				>
					<span class="i-lucide-download mr-1"></span>Download
				</a>
				<button
					class="btn-secondary btn-sm"
					onclick={handleReprocess}
					disabled={reprocessing}
				>
					<span class="i-lucide-refresh-cw mr-1 {reprocessing ? 'animate-spin' : ''}"></span>
					Reprocess
				</button>
				<button
					class="btn-danger btn-sm"
					onclick={() => (showDeleteDialog = true)}
				>
					<span class="i-lucide-trash-2 mr-1"></span>Delete
				</button>
			</div>

			<!-- Bill Status -->
			{#if isBill}
				<div class="card p-4">
					<h3 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-1">
						<span class="i-lucide-receipt"></span>
						Bill Info
					</h3>
					<div class="space-y-2 text-sm">
						<div class="flex items-center justify-between">
							<span class="text-gray-500 dark:text-gray-400">Status</span>
							{#if doc.bill_status === 'unpaid'}
								<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400">Unpaid</span>
							{:else if doc.bill_status === 'paid'}
								<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">Paid</span>
							{:else if doc.bill_status === 'dismissed'}
								<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400">Dismissed</span>
							{:else}
								<span class="text-gray-400">—</span>
							{/if}
						</div>
						{#if doc.bill_due_date}
							<div class="flex items-center justify-between">
								<span class="text-gray-500 dark:text-gray-400">Due Date</span>
								<span class="text-gray-900 dark:text-gray-100">{new Date(doc.bill_due_date).toLocaleDateString()}</span>
							</div>
						{/if}
						{#if doc.bill_paid_at}
							<div class="flex items-center justify-between">
								<span class="text-gray-500 dark:text-gray-400">Paid</span>
								<span class="text-gray-900 dark:text-gray-100">{new Date(doc.bill_paid_at).toLocaleDateString()}</span>
							</div>
						{/if}
					</div>
					<div class="flex flex-wrap gap-2 mt-3">
						{#if doc.bill_status === 'unpaid'}
							<button class="btn-primary btn-sm" onclick={() => handleBillStatus('paid')} disabled={updatingBill}>
								<span class="i-lucide-check mr-1"></span>Mark Paid
							</button>
							<button class="btn-ghost btn-sm" onclick={() => handleBillStatus('dismissed')} disabled={updatingBill}>
								Not a Bill
							</button>
						{:else if doc.bill_status === 'paid' || doc.bill_status === 'dismissed'}
							<button class="btn-secondary btn-sm" onclick={() => handleBillStatus('unpaid')} disabled={updatingBill}>
								Mark Unpaid
							</button>
						{/if}
					</div>
				</div>
			{/if}

			<!-- Metadata -->
			<div class="card p-4">
				<DocumentMeta document={doc} onupdate={handleMetaUpdate} />
			</div>

			<!-- Tags -->
			<div class="card p-4">
				<h3 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-1">
					<span class="i-lucide-tags"></span>
					Tags
				</h3>
				<TagInput tags={doc.tags} onchange={handleTagsChange} />
			</div>

			<!-- Content text -->
			{#if doc.content_text}
				<div class="card p-4">
					<h3 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-1">
						<span class="i-lucide-text"></span>
						Extracted Text
					</h3>
					<pre class="text-sm text-gray-600 dark:text-gray-400 whitespace-pre-wrap bg-gray-50 dark:bg-gray-900 rounded-lg p-3 max-h-64 overflow-y-auto">{doc.content_text}</pre>
				</div>
			{/if}
		</div>

		<!-- Right: PDF viewer -->
		<div class="flex-1 min-w-0">
			<PdfPreview src={getDownloadUrl(doc.id)} highlight={searchQuery} />
		</div>
	</div>

	<ConfirmDialog
		open={showDeleteDialog}
		title="Delete Document"
		message="This will soft-delete the document. It won't appear in search results anymore. Are you sure?"
		confirmLabel={deleting ? 'Deleting...' : 'Delete'}
		onconfirm={handleDelete}
		oncancel={() => (showDeleteDialog = false)}
	/>
{/if}
