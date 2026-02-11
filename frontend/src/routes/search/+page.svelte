<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { searchDocuments } from '$lib/api/documents.js';
	import type { DocumentListItem, SearchDocumentsParams } from '$lib/types/index.js';
	import SearchBar from '$lib/components/shared/SearchBar.svelte';
	import DocumentCard from '$lib/components/documents/DocumentCard.svelte';
	import Pagination from '$lib/components/shared/Pagination.svelte';
	import LoadingSpinner from '$lib/components/shared/LoadingSpinner.svelte';
	import EmptyState from '$lib/components/shared/EmptyState.svelte';
	import { toasts } from '$lib/stores/toast.js';

	let documents = $state<DocumentListItem[]>([]);
	let total = $state(0);
	let loading = $state(false);
	let searched = $state(false);

	let query = $state('');
	let offset = $state(0);
	let limit = $state(24);
	let documentType = $state('');
	let tag = $state('');

	function syncFromUrl() {
		const p = $page.url.searchParams;
		query = p.get('q') ?? '';
		offset = parseInt(p.get('offset') ?? '0');
		documentType = p.get('document_type') ?? '';
		tag = p.get('tag') ?? '';
	}

	function buildUrl(): string {
		const params = new URLSearchParams();
		if (query) params.set('q', query);
		if (offset > 0) params.set('offset', String(offset));
		if (documentType) params.set('document_type', documentType);
		if (tag) params.set('tag', tag);
		const qs = params.toString();
		return qs ? `/search?${qs}` : '/search';
	}

	async function doSearch() {
		if (!query.trim()) {
			documents = [];
			total = 0;
			searched = false;
			return;
		}

		loading = true;
		searched = true;
		goto(buildUrl(), { replaceState: true, noScroll: true });

		try {
			const params: SearchDocumentsParams = { q: query, offset, limit };
			if (documentType) params.document_type = documentType;
			if (tag) params.tag = tag;

			const res = await searchDocuments(params);
			documents = res.documents;
			total = res.total;
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Search failed');
		} finally {
			loading = false;
		}
	}

	function handleSearch(q: string) {
		query = q;
		offset = 0;
		doSearch();
	}

	function handlePageChange(newOffset: number) {
		offset = newOffset;
		doSearch();
	}

	onMount(() => {
		syncFromUrl();
		if (query) doSearch();
	});
</script>

<svelte:head>
	<title>{query ? `"${query}" - Search` : 'Search'} - DocManFu</title>
</svelte:head>

<div class="page-container">
	<h1 class="text-2xl font-bold text-gray-900 mb-6">Search Documents</h1>

	<div class="mb-6">
		<SearchBar bind:value={query} onSearch={handleSearch} />
	</div>

	{#if loading}
		<LoadingSpinner />
	{:else if searched && documents.length === 0}
		<EmptyState
			icon="i-lucide-search-x"
			title="No results found"
			description="Try a different search term or adjust your filters."
		/>
	{:else if documents.length > 0}
		<p class="text-sm text-gray-500 mb-4">{total} result{total === 1 ? '' : 's'} for "{query}"</p>

		<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
			{#each documents as doc (doc.id)}
				<DocumentCard document={doc} />
			{/each}
		</div>

		<Pagination {total} {offset} {limit} onchange={handlePageChange} />
	{:else}
		<EmptyState
			icon="i-lucide-search"
			title="Search your documents"
			description="Enter a search term to find documents by name, content, or AI-generated name."
		/>
	{/if}
</div>
