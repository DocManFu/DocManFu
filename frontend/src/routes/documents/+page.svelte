<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { listDocuments } from '$lib/api/documents.js';
	import type { DocumentListItem, ListDocumentsParams } from '$lib/types/index.js';
	import DocumentCard from '$lib/components/documents/DocumentCard.svelte';
	import FilterPanel from '$lib/components/shared/FilterPanel.svelte';
	import SortSelect from '$lib/components/shared/SortSelect.svelte';
	import Pagination from '$lib/components/shared/Pagination.svelte';
	import LoadingSpinner from '$lib/components/shared/LoadingSpinner.svelte';
	import EmptyState from '$lib/components/shared/EmptyState.svelte';
	import { toasts } from '$lib/stores/toast.js';

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

	onMount(() => {
		syncFromUrl();
		fetchDocuments();
	});
</script>

<svelte:head>
	<title>Documents - DocManFu</title>
</svelte:head>

<div class="page-container">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-gray-900">Documents</h1>
		<a href="/upload" class="btn-primary no-underline">
			<span class="i-lucide-upload mr-2"></span>Upload
		</a>
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
		<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
			{#each documents as doc (doc.id)}
				<DocumentCard document={doc} />
			{/each}
		</div>

		<Pagination {total} {offset} {limit} onchange={handlePageChange} />
	{/if}
</div>
