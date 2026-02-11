<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { searchDocuments } from '$lib/api/documents.js';
	import type { SearchResultItem, SearchDocumentsParams } from '$lib/types/index.js';
	import SearchBar from '$lib/components/shared/SearchBar.svelte';
	import TagBadge from '$lib/components/tags/TagBadge.svelte';
	import Pagination from '$lib/components/shared/Pagination.svelte';
	import LoadingSpinner from '$lib/components/shared/LoadingSpinner.svelte';
	import EmptyState from '$lib/components/shared/EmptyState.svelte';
	import { formatFileSize, formatDate, formatDocumentType } from '$lib/utils/format.js';
	import { toasts } from '$lib/stores/toast.js';

	let documents = $state<SearchResultItem[]>([]);
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
	<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-6">Search Documents</h1>

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
		<p class="text-sm text-gray-500 dark:text-gray-400 mb-4">{total} result{total === 1 ? '' : 's'} for "{query}"</p>

		<div class="space-y-3 mb-6">
			{#each documents as doc (doc.id)}
				<a
					href="/documents/{doc.id}?q={encodeURIComponent(query)}"
					class="card hover:shadow-md transition-shadow p-4 block no-underline text-inherit"
				>
					<div class="flex items-start gap-3">
						<div class="flex-shrink-0 w-10 h-10 rounded-lg bg-brand-50 dark:bg-brand-900/30 flex items-center justify-center">
							<span class="i-lucide-file-text text-brand-600 dark:text-brand-400"></span>
						</div>
						<div class="flex-1 min-w-0">
							<h3 class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
								{doc.ai_generated_name || doc.original_name}
							</h3>
							<div class="flex items-center gap-2 mt-1 text-xs text-gray-500 dark:text-gray-400">
								{#if doc.document_type}
									<span class="badge bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300">
										{formatDocumentType(doc.document_type)}
									</span>
								{/if}
								<span>{formatFileSize(doc.file_size)}</span>
								<span>{formatDate(doc.upload_date)}</span>
								{#if doc.rank > 0}
									<span class="text-gray-400">score: {doc.rank.toFixed(2)}</span>
								{/if}
							</div>

							{#if doc.headline}
								<p class="text-sm text-gray-600 dark:text-gray-400 mt-2 leading-relaxed">
									{@html doc.headline}
								</p>
							{/if}

							{#if doc.tags.length > 0}
								<div class="flex flex-wrap gap-1 mt-2">
									{#each doc.tags.slice(0, 5) as tag (tag.id)}
										<TagBadge {tag} />
									{/each}
									{#if doc.tags.length > 5}
										<span class="text-xs text-gray-400">+{doc.tags.length - 5}</span>
									{/if}
								</div>
							{/if}
						</div>
					</div>
				</a>
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
