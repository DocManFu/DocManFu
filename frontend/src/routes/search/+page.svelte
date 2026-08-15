<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { searchDocuments } from '$lib/api/documents.js';
	import type { SearchResultItem, SearchDocumentsParams } from '$lib/types/index.js';
	import SearchBar from '$lib/components/shared/SearchBar.svelte';
	import TagBadge from '$lib/components/tags/TagBadge.svelte';
	import TagAutocomplete from '$lib/components/tags/TagAutocomplete.svelte';
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
	let untagged = $state(false);
	let untyped = $state(false);
	let requestId = 0;
	const docTypes = [
		'bill',
		'bank_statement',
		'medical',
		'insurance',
		'tax',
		'invoice',
		'receipt',
		'legal',
		'correspondence',
		'report',
		'other',
	];

	function escapeHtml(value: string): string {
		return value.replace(
			/[&<>"']/g,
			(char) =>
				({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char] ?? char,
		);
	}

	function safeHeadline(headline: string | null): string {
		if (!headline) return '';
		return headline
			.split(/(<mark>.*?<\/mark>)/gis)
			.map((part) =>
				part.startsWith('<mark>') && part.endsWith('</mark>')
					? `<mark>${escapeHtml(part.slice(6, -7))}</mark>`
					: escapeHtml(part),
			)
			.join('');
	}

	function syncFromUrl() {
		const p = $page.url.searchParams;
		query = p.get('q') ?? '';
		offset = parseInt(p.get('offset') ?? '0');
		documentType = p.get('document_type') ?? '';
		tag = p.get('tag') ?? '';
		untagged = p.get('untagged') === 'true';
		untyped = p.get('untyped') === 'true';
	}

	function buildUrl(): string {
		const params = new URLSearchParams();
		if (query) params.set('q', query);
		if (offset > 0) params.set('offset', String(offset));
		if (documentType) params.set('document_type', documentType);
		if (tag) params.set('tag', tag);
		if (untagged) params.set('untagged', 'true');
		if (untyped) params.set('untyped', 'true');
		const qs = params.toString();
		return qs ? `/search?${qs}` : '/search';
	}

	async function doSearch() {
		const currentRequest = ++requestId;
		if (!query.trim()) {
			documents = [];
			total = 0;
			searched = false;
			loading = false;
			return;
		}

		loading = true;
		searched = true;
		goto(buildUrl(), { replaceState: true, noScroll: true });

		try {
			const params: SearchDocumentsParams = { q: query, offset, limit };
			if (documentType) params.document_type = documentType;
			if (tag) params.tag = tag;
			if (untagged) params.untagged = 'true';
			if (untyped) params.untyped = 'true';

			const res = await searchDocuments(params);
			if (currentRequest !== requestId) return;
			documents = res.documents;
			total = res.total;
		} catch (e) {
			if (currentRequest !== requestId) return;
			toasts.error(e instanceof Error ? e.message : 'Search failed');
		} finally {
			if (currentRequest === requestId) loading = false;
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

	$effect(() => {
		const urlQuery = $page.url.searchParams.get('q') ?? '';
		const urlOffset = parseInt($page.url.searchParams.get('offset') ?? '0');
		const urlType = $page.url.searchParams.get('document_type') ?? '';
		const urlTag = $page.url.searchParams.get('tag') ?? '';
		const urlUntagged = $page.url.searchParams.get('untagged') === 'true';
		const urlUntyped = $page.url.searchParams.get('untyped') === 'true';
		if (
			urlQuery !== query ||
			urlOffset !== offset ||
			urlType !== documentType ||
			urlTag !== tag ||
			urlUntagged !== untagged ||
			urlUntyped !== untyped
		) {
			query = urlQuery;
			offset = urlOffset;
			documentType = urlType;
			tag = urlTag;
			untagged = urlUntagged;
			untyped = urlUntyped;
			if (urlQuery) doSearch();
		}
	});
</script>

<svelte:head>
	<title>{query ? `"${query}" - Search` : 'Search'} - DocManFu</title>
</svelte:head>

<div class="page-container">
	<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-6">Search Documents</h1>

	<div class="mb-6">
		<SearchBar bind:value={query} onSearch={handleSearch} />
		<div class="flex flex-wrap items-center gap-3 mt-3">
			<select
				class="input-base"
				bind:value={documentType}
				onchange={() => {
					offset = 0;
					doSearch();
				}}
				aria-label="Filter by document type"
			>
				<option value="">All types</option>
				{#each docTypes as type}<option value={type}>{formatDocumentType(type)}</option>{/each}
			</select>
			<div class="w-56">
				<TagAutocomplete
					selected={tag ? tag.split(',') : []}
					onchange={(tags) => {
						tag = tags.join(',');
						offset = 0;
						doSearch();
					}}
				/>
			</div>
			<label class="flex items-center gap-2 text-sm"
				><input
					type="checkbox"
					bind:checked={untagged}
					onchange={() => {
						offset = 0;
						doSearch();
					}}
				/> Untagged</label
			>
			<label class="flex items-center gap-2 text-sm"
				><input
					type="checkbox"
					bind:checked={untyped}
					onchange={() => {
						offset = 0;
						doSearch();
					}}
				/> Untyped</label
			>
		</div>
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
		<p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
			{total} result{total === 1 ? '' : 's'} for "{query}"
		</p>

		<div class="space-y-3 mb-6">
			{#each documents as doc (doc.id)}
				<a
					href="/documents/{doc.id}?q={encodeURIComponent(query)}"
					class="card hover:shadow-md transition-shadow p-4 block no-underline text-inherit"
				>
					<div class="flex items-start gap-3">
						<div
							class="flex-shrink-0 w-10 h-10 rounded-lg bg-brand-50 dark:bg-brand-900/30 flex items-center justify-center"
						>
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
									{@html safeHeadline(doc.headline)}
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
