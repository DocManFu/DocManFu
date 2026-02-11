<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { getAuthHeader } from '$lib/api/client.js';
	import {
		getDocument,
		updateDocument,
		deleteDocument,
		reprocessDocument,
		getDownloadUrl,
		downloadDocument
	} from '$lib/api/documents.js';
	import { updateBillStatus, updateBillDueDate } from '$lib/api/bills.js';
	import { getDocumentJobHistory } from '$lib/api/jobs.js';
	import type { DocumentDetail, DocumentUpdateRequest, JobStatusResponse } from '$lib/types/index.js';
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
	let editingDueDate = $state(false);
	let editDueDate = $state('');

	// Copy state
	let copied = $state(false);

	// Processing log
	let showProcessingLog = $state(false);
	let jobHistory = $state<JobStatusResponse[]>([]);
	let loadingJobs = $state(false);

	let searchQuery = $derived($page.url.searchParams.get('q') ?? '');
	let imageBlobUrl = $state<string | null>(null);

	$effect(() => {
		if (doc && doc.mime_type.startsWith('image/')) {
			const url = getDownloadUrl(doc.id);
			fetch(url, { headers: getAuthHeader() })
				.then((res) => res.blob())
				.then((blob) => {
					imageBlobUrl = URL.createObjectURL(blob);
				});
			return () => {
				if (imageBlobUrl) URL.revokeObjectURL(imageBlobUrl);
			};
		}
	});

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

	function startEditDueDate() {
		editDueDate = doc?.bill_due_date?.slice(0, 10) ?? '';
		editingDueDate = true;
	}

	async function handleDueDateSave() {
		if (!doc) return;
		updatingBill = true;
		try {
			const res = await updateBillDueDate(doc.id, editDueDate || null);
			doc.bill_due_date = res.bill_due_date;
			editingDueDate = false;
			toasts.success('Due date updated');
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to update due date');
		} finally {
			updatingBill = false;
		}
	}

	async function toggleProcessingLog() {
		showProcessingLog = !showProcessingLog;
		if (showProcessingLog && jobHistory.length === 0 && doc) {
			loadingJobs = true;
			try {
				jobHistory = await getDocumentJobHistory(doc.id);
			} catch {
				// silently fail
			} finally {
				loadingJobs = false;
			}
		}
	}

	function formatJobType(type: string): string {
		switch (type) {
			case 'ocr': return 'OCR';
			case 'ai_analysis': return 'AI Analysis';
			case 'file_organization': return 'File Organization';
			default: return type;
		}
	}

	function formatJobStatus(status: string): { label: string; classes: string } {
		switch (status) {
			case 'completed': return { label: 'Completed', classes: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400' };
			case 'failed': return { label: 'Failed', classes: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400' };
			case 'processing': return { label: 'Processing', classes: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400' };
			case 'pending': return { label: 'Pending', classes: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400' };
			default: return { label: status, classes: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400' };
		}
	}

	function formatDateTime(iso: string): string {
		return new Date(iso).toLocaleString();
	}

	function handleNameKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') saveName();
		if (e.key === 'Escape') cancelEditName();
	}

	onMount(() => {
		loadDocument();
		const unsubDocUpdated = jobStore.onDocumentUpdated((event) => {
			if (doc && event.document_id === doc.id) {
				loadDocument();
			}
		});
		return () => unsubDocUpdated();
	});
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
				<button
					class="btn-secondary btn-sm"
					onclick={() => doc && downloadDocument(doc.id, displayName + '.pdf')}
				>
					<span class="i-lucide-download mr-1"></span>Download
				</button>
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
						<div class="flex items-center justify-between">
							<span class="text-gray-500 dark:text-gray-400">Due Date</span>
							{#if editingDueDate}
								<div class="flex items-center gap-1">
									<input
										type="date"
										class="input-base text-sm w-36"
										bind:value={editDueDate}
										onkeydown={(e) => { if (e.key === 'Enter') handleDueDateSave(); if (e.key === 'Escape') editingDueDate = false; }}
									/>
									<button class="btn-primary btn-sm" onclick={handleDueDateSave} disabled={updatingBill}>Save</button>
									<button class="btn-ghost btn-sm" onclick={() => editingDueDate = false}>Cancel</button>
								</div>
							{:else if doc.bill_due_date}
								<span class="inline-flex items-center gap-1 group">
									<span class="text-gray-900 dark:text-gray-100">{new Date(doc.bill_due_date).toLocaleDateString()}</span>
									<button
										class="btn-icon opacity-0 group-hover:opacity-100"
										title="Edit due date"
										onclick={startEditDueDate}
									>
										<span class="i-lucide-pencil text-xs"></span>
									</button>
								</span>
							{:else}
								<button
									class="text-blue-500 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 text-sm"
									onclick={startEditDueDate}
								>
									Add due date
								</button>
							{/if}
						</div>
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
					<div class="flex items-center justify-between mb-3">
						<h3 class="text-sm font-medium text-gray-700 dark:text-gray-300 flex items-center gap-1">
							<span class="i-lucide-text"></span>
							Extracted Text
						</h3>
						<button
							class="btn-ghost btn-sm flex items-center gap-1"
							title="Copy text to clipboard"
							onclick={() => {
								navigator.clipboard.writeText(doc.content_text ?? '');
								copied = true;
								setTimeout(() => (copied = false), 2000);
							}}
						>
							<span class={copied ? 'i-lucide-check text-green-500' : 'i-lucide-copy'}></span>
							<span class="text-xs">{copied ? 'Copied!' : 'Copy'}</span>
						</button>
					</div>
					<pre class="text-sm text-gray-600 dark:text-gray-400 whitespace-pre-wrap bg-gray-50 dark:bg-gray-900 rounded-lg p-3 max-h-64 overflow-y-auto">{doc.content_text}</pre>
				</div>
			{/if}

			<!-- Processing Log -->
			<div class="card p-4">
				<button
					class="flex items-center gap-2 w-full text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100"
					onclick={toggleProcessingLog}
				>
					<span class="{showProcessingLog ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'} text-xs"></span>
					<span class="i-lucide-activity"></span>
					Processing Log
				</button>

				{#if showProcessingLog}
					<div class="mt-3 space-y-3">
						{#if loadingJobs}
							<div class="flex items-center justify-center py-4">
								<div class="i-lucide-loader-2 animate-spin text-gray-400"></div>
							</div>
						{:else if jobHistory.length === 0}
							<p class="text-sm text-gray-500 dark:text-gray-400">No processing history found.</p>
						{:else}
							{#each jobHistory as job}
								<div class="border border-gray-100 dark:border-gray-700 rounded-lg p-3 text-sm">
									<div class="flex items-center justify-between mb-2">
										<span class="font-medium text-gray-900 dark:text-gray-100">
											{formatJobType(job.job_type)}
										</span>
										<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium {formatJobStatus(job.status).classes}">
											{formatJobStatus(job.status).label}
										</span>
									</div>
									<div class="text-xs text-gray-500 dark:text-gray-400 space-y-0.5">
										<div>Created: {formatDateTime(job.created_at)}</div>
										{#if job.completed_at}
											<div>Completed: {formatDateTime(job.completed_at)}</div>
										{/if}
									</div>
									{#if job.error_message}
										<div class="mt-2 text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded p-2">
											{job.error_message}
										</div>
									{/if}
									{#if job.result_data && job.job_type === 'ai_analysis'}
										<div class="mt-2 space-y-1 text-xs">
											{#if job.result_data.document_type}
												<div class="flex justify-between">
													<span class="text-gray-500 dark:text-gray-400">Type</span>
													<span class="text-gray-900 dark:text-gray-100 font-medium">{job.result_data.document_type}</span>
												</div>
											{/if}
											{#if job.result_data.suggested_name}
												<div class="flex justify-between gap-2">
													<span class="text-gray-500 dark:text-gray-400 flex-shrink-0">Name</span>
													<span class="text-gray-900 dark:text-gray-100 font-medium text-right">{job.result_data.suggested_name}</span>
												</div>
											{/if}
											{#if job.result_data.confidence_score != null}
												<div class="flex justify-between">
													<span class="text-gray-500 dark:text-gray-400">Confidence</span>
													<span class="text-gray-900 dark:text-gray-100 font-medium">{(Number(job.result_data.confidence_score) * 100).toFixed(0)}%</span>
												</div>
											{/if}
											{#if job.result_data.suggested_tags}
												<div class="flex justify-between gap-2">
													<span class="text-gray-500 dark:text-gray-400 flex-shrink-0">Tags</span>
													<span class="text-gray-900 dark:text-gray-100">{(job.result_data.suggested_tags as string[]).join(', ')}</span>
												</div>
											{/if}
											{#if job.result_data.vision_used}
												<div class="flex justify-between">
													<span class="text-gray-500 dark:text-gray-400">Method</span>
													<span class="text-gray-900 dark:text-gray-100">Vision</span>
												</div>
											{/if}
										</div>
									{/if}
									{#if job.result_data && job.job_type === 'ocr'}
										<div class="mt-2 space-y-1 text-xs">
											{#if job.result_data.pages_processed}
												<div class="flex justify-between">
													<span class="text-gray-500 dark:text-gray-400">Pages</span>
													<span class="text-gray-900 dark:text-gray-100 font-medium">{job.result_data.pages_processed}</span>
												</div>
											{/if}
											{#if job.result_data.text_length}
												<div class="flex justify-between">
													<span class="text-gray-500 dark:text-gray-400">Text Length</span>
													<span class="text-gray-900 dark:text-gray-100 font-medium">{Number(job.result_data.text_length).toLocaleString()} chars</span>
												</div>
											{/if}
										</div>
									{/if}
								</div>
							{/each}
						{/if}
					</div>
				{/if}
			</div>
		</div>

		<!-- Right: document viewer -->
		<div class="flex-1 min-w-0">
			{#if doc.mime_type.startsWith('image/')}
				<div class="h-full flex items-center justify-center bg-gray-50 dark:bg-gray-800 p-4 overflow-auto">
					{#if imageBlobUrl}
						<img
							src={imageBlobUrl}
							alt={displayName}
							class="max-w-full max-h-full object-contain rounded-lg shadow-lg"
						/>
					{/if}
				</div>
			{:else}
				<PdfPreview src={getDownloadUrl(doc.id)} highlight={searchQuery} />
			{/if}
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
