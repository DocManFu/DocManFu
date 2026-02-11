<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { listDocuments, bulkDeleteDocuments, bulkReprocessDocuments, getExportCsvUrl } from '$lib/api/documents.js';
	import type { DocumentListItem, ListDocumentsParams } from '$lib/types/index.js';
	import DocumentCard from '$lib/components/documents/DocumentCard.svelte';
	import FilterPanel from '$lib/components/shared/FilterPanel.svelte';
	import SortSelect from '$lib/components/shared/SortSelect.svelte';
	import Pagination from '$lib/components/shared/Pagination.svelte';
	import LoadingSpinner from '$lib/components/shared/LoadingSpinner.svelte';
	import EmptyState from '$lib/components/shared/EmptyState.svelte';
	import ConfirmDialog from '$lib/components/shared/ConfirmDialog.svelte';
	import { toasts } from '$lib/stores/toast.js';
	import { jobStore } from '$lib/stores/jobs.js';

	let documents = $state<DocumentListItem[]>([]);
	let total = $state(0);
	let loading = $state(true);

	// Filter state from URL params
	let offset = $state(0);
	let limit = $state(24);
	let documentType = $state('');
	let tag = $state('');
	let dateFrom = $state('');
	let dateTo = $state('');
	let sortBy = $state('upload_date');
	let sortOrder = $state('desc');

	// Selection / bulk mode
	let selectMode = $state(false);
	let selectedIds = $state<Set<string>>(new Set());
	let showBulkDeleteDialog = $state(false);
	let bulkProcessing = $state(false);

	// j/k navigation
	let focusedIndex = $state(-1);

	function syncFromUrl() {
		const p = $page.url.searchParams;
		offset = parseInt(p.get('offset') ?? '0');
		documentType = p.get('document_type') ?? '';
		tag = p.get('tag') ?? '';
		dateFrom = p.get('date_from') ?? '';
		dateTo = p.get('date_to') ?? '';
		sortBy = p.get('sort_by') ?? 'upload_date';
		sortOrder = p.get('sort_order') ?? 'desc';
	}

	function buildUrl(): string {
		const params = new URLSearchParams();
		if (offset > 0) params.set('offset', String(offset));
		if (documentType) params.set('document_type', documentType);
		if (tag) params.set('tag', tag);
		if (dateFrom) params.set('date_from', dateFrom);
		if (dateTo) params.set('date_to', dateTo);
		if (sortBy !== 'upload_date') params.set('sort_by', sortBy);
		if (sortOrder !== 'desc') params.set('sort_order', sortOrder);
		const qs = params.toString();
		return qs ? `/documents?${qs}` : '/documents';
	}

	async function fetchDocuments() {
		loading = true;
		try {
			const params: ListDocumentsParams = { offset, limit };
			if (documentType) params.document_type = documentType;
			if (tag) params.tag = tag;
			if (dateFrom) params.date_from = dateFrom;
			if (dateTo) params.date_to = dateTo;
			params.sort_by = sortBy as ListDocumentsParams['sort_by'];
			params.sort_order = sortOrder as ListDocumentsParams['sort_order'];

			const res = await listDocuments(params);
			documents = res.documents;
			total = res.total;
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to load documents');
		} finally {
			loading = false;
		}
	}

	function handleFilterChange() {
		offset = 0;
		goto(buildUrl(), { replaceState: true, noScroll: true });
		fetchDocuments();
	}

	function handlePageChange(newOffset: number) {
		offset = newOffset;
		goto(buildUrl(), { replaceState: true });
		fetchDocuments();
	}

	function toggleSelect(id: string) {
		const next = new Set(selectedIds);
		if (next.has(id)) {
			next.delete(id);
		} else {
			next.add(id);
		}
		selectedIds = next;
	}

	function selectAll() {
		selectedIds = new Set(documents.map((d) => d.id));
	}

	function deselectAll() {
		selectedIds = new Set();
	}

	function exitSelectMode() {
		selectMode = false;
		selectedIds = new Set();
	}

	async function handleBulkDelete() {
		bulkProcessing = true;
		try {
			const res = await bulkDeleteDocuments({ document_ids: [...selectedIds] });
			toasts.success(res.detail);
			exitSelectMode();
			fetchDocuments();
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Bulk delete failed');
		} finally {
			bulkProcessing = false;
			showBulkDeleteDialog = false;
		}
	}

	async function handleBulkReprocess() {
		bulkProcessing = true;
		try {
			const res = await bulkReprocessDocuments({ document_ids: [...selectedIds] });
			toasts.success(res.detail);
			if (res.jobs) {
				for (const job of res.jobs) {
					const doc = documents.find((d) => d.id === job.document_id);
					jobStore.track(job.job_id, job.document_id, doc?.original_name ?? 'Document');
				}
			}
			exitSelectMode();
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Bulk reprocess failed');
		} finally {
			bulkProcessing = false;
		}
	}

	function handleDocNavigate(e: Event) {
		const detail = (e as CustomEvent).detail;
		if (!detail) return;
		const direction = detail.direction;
		if (direction === 'next') {
			focusedIndex = Math.min(focusedIndex + 1, documents.length - 1);
		} else if (direction === 'prev') {
			focusedIndex = Math.max(focusedIndex - 1, 0);
		} else if (direction === 'open' && focusedIndex >= 0 && focusedIndex < documents.length) {
			goto(`/documents/${documents[focusedIndex].id}`);
		} else if (direction === 'selectAll' && selectMode) {
			selectAll();
		}
	}

	let containerEl: HTMLDivElement;

	onMount(() => {
		syncFromUrl();
		fetchDocuments();
		containerEl?.addEventListener('docnavigate', handleDocNavigate);
		return () => {
			containerEl?.removeEventListener('docnavigate', handleDocNavigate);
		};
	});
</script>

<svelte:head>
	<title>Documents - DocManFu</title>
</svelte:head>

<div class="page-container" bind:this={containerEl}>
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">Documents</h1>
		<div class="flex items-center gap-2">
			<a
				href={getExportCsvUrl({ document_type: documentType || undefined, tag: tag || undefined, date_from: dateFrom || undefined, date_to: dateTo || undefined })}
				class="btn-secondary btn-sm no-underline"
				download
			>
				<span class="i-lucide-download mr-1"></span>CSV
			</a>
			<button
				class="btn-secondary btn-sm"
				onclick={() => selectMode ? exitSelectMode() : (selectMode = true)}
			>
				<span class="i-lucide-check-square mr-1"></span>
				{selectMode ? 'Cancel' : 'Select'}
			</button>
			<a href="/upload" class="btn-primary no-underline">
				<span class="i-lucide-upload mr-2"></span>Upload
			</a>
		</div>
	</div>

	<div class="card p-4 mb-6">
		<div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
			<FilterPanel
				bind:documentType
				bind:tag
				bind:dateFrom
				bind:dateTo
				onchange={handleFilterChange}
			/>
			<SortSelect
				bind:sortBy
				bind:sortOrder
				onchange={handleFilterChange}
			/>
		</div>
	</div>

	{#if loading}
		<LoadingSpinner />
	{:else if documents.length === 0}
		<EmptyState
			icon="i-lucide-files"
			title="No documents found"
			description="Upload your first PDF to get started, or adjust your filters."
		/>
	{:else}
		{#if selectMode}
			<div class="flex items-center gap-2 mb-4">
				<button class="btn-ghost btn-sm text-xs" onclick={selectAll}>Select all</button>
				<button class="btn-ghost btn-sm text-xs" onclick={deselectAll}>Deselect all</button>
				<span class="text-sm text-gray-500 dark:text-gray-400">{selectedIds.size} selected</span>
			</div>
		{/if}

		<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
			{#each documents as doc, i (doc.id)}
				{#if selectMode}
					<!-- svelte-ignore a11y_click_events_have_key_events -->
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<div class="relative cursor-pointer" onclick={() => toggleSelect(doc.id)}>
						<div class="absolute top-2 left-2 z-10">
							<div class="w-5 h-5 rounded border-2 flex items-center justify-center
								{selectedIds.has(doc.id) ? 'bg-brand-600 border-brand-600' : 'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600'}">
								{#if selectedIds.has(doc.id)}
									<span class="i-lucide-check text-white text-xs"></span>
								{/if}
							</div>
						</div>
						<DocumentCard document={doc} selected={selectedIds.has(doc.id)} />
					</div>
				{:else}
					<DocumentCard document={doc} focused={focusedIndex === i} />
				{/if}
			{/each}
		</div>

		<Pagination {total} {offset} {limit} onchange={handlePageChange} />
	{/if}
</div>

<!-- Floating bulk action bar -->
{#if selectMode && selectedIds.size > 0}
	<div class="fixed bottom-6 left-1/2 -translate-x-1/2 z-40">
		<div class="flex items-center gap-3 bg-white dark:bg-gray-800 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 px-4 py-3">
			<span class="text-sm font-medium text-gray-700 dark:text-gray-300">{selectedIds.size} selected</span>
			<button
				class="btn-secondary btn-sm"
				onclick={handleBulkReprocess}
				disabled={bulkProcessing}
			>
				<span class="i-lucide-refresh-cw mr-1"></span>Reprocess
			</button>
			<button
				class="btn-danger btn-sm"
				onclick={() => (showBulkDeleteDialog = true)}
				disabled={bulkProcessing}
			>
				<span class="i-lucide-trash-2 mr-1"></span>Delete
			</button>
			<button class="btn-ghost btn-sm" onclick={exitSelectMode}>Cancel</button>
		</div>
	</div>
{/if}

<ConfirmDialog
	open={showBulkDeleteDialog}
	title="Delete {selectedIds.size} Documents"
	message="This will soft-delete the selected documents. They won't appear in search results anymore. Are you sure?"
	confirmLabel={bulkProcessing ? 'Deleting...' : 'Delete All'}
	onconfirm={handleBulkDelete}
	oncancel={() => (showBulkDeleteDialog = false)}
/>
