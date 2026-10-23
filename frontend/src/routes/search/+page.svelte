<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { searchDocuments } from '$lib/api/documents.js';
	import { listTags } from '$lib/api/tags.js';
	import type { SearchFacets, SearchResultItem, SearchSort, SearchTerm } from '$lib/types/index.js';
	import SearchQueryInput from '$lib/components/shared/SearchQueryInput.svelte';
	import TagBadge from '$lib/components/tags/TagBadge.svelte';
	import Pagination from '$lib/components/shared/Pagination.svelte';
	import LoadingSpinner from '$lib/components/shared/LoadingSpinner.svelte';
	import EmptyState from '$lib/components/shared/EmptyState.svelte';
	import { formatFileSize, formatDate, formatDocumentType } from '$lib/utils/format.js';
	import {
		OPERATORS,
		TERM_LABELS,
		addTerm,
		highlightWords,
		legacyParamsToQuery,
		removeSpan,
	} from '$lib/utils/searchQuery.js';
	import { toasts } from '$lib/stores/toast.js';

	let documents = $state<SearchResultItem[]>([]);
	let total = $state(0);
	let terms = $state<SearchTerm[]>([]);
	let errors = $state<string[]>([]);
	let facets = $state<SearchFacets | null>(null);
	let loading = $state(false);
	let searched = $state(false);
	let showTips = $state(false);
	let showFacets = $state(false); // mobile only; always shown on md+
	let tagNames = $state<string[]>([]);

	let query = $state('');
	// The query the current results/terms belong to (term spans index into it)
	let resultQuery = $state('');
	let sort = $state<SearchSort>('relevance');
	let offset = $state(0);
	let limit = $state(24);
	let requestId = 0;
	// URL this page last wrote via goto(); navigations to it are our own echoes, not external changes
	let lastWrittenUrl: string | null = null;

	const SORTS: { value: SearchSort; label: string }[] = [
		{ value: 'relevance', label: 'Best match' },
		{ value: 'newest', label: 'Newest first' },
		{ value: 'oldest', label: 'Oldest first' },
		{ value: 'name', label: 'Name' },
	];

	const PLACEHOLDER = 'Search… try tag:bill, title:utah, ocr:"oil change", -type:receipt';

	const EXAMPLES = [
		'tag:bill is:unpaid',
		'title:utah ocr:ford',
		'company:"rocky mountain" date:2024',
		'type:receipt newer_than:3m',
		'insurance -tag:medical',
		'is:untagged',
	];

	// Facet values already applied positively aren't worth offering again
	const applied = $derived(
		new Set(terms.filter((t) => !t.negated).map((t) => `${t.key}:${t.value.toLowerCase()}`)),
	);

	const highlightQuery = $derived(highlightWords(resultQuery, terms));

	onMount(async () => {
		try {
			// Admins get every user's tags, so the same name can repeat
			tagNames = [...new Set((await listTags()).map((t) => t.name))];
		} catch {
			// Autocomplete just won't offer tag names
		}
	});

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
		query = legacyParamsToQuery(p.get('q') ?? '', p);
		offset = parseInt(p.get('offset') ?? '0') || 0;
		const s = p.get('sort') as SearchSort | null;
		sort = s && SORTS.some((o) => o.value === s) ? s : 'relevance';
	}

	function buildUrl(): string {
		const params = new URLSearchParams();
		if (query) params.set('q', query);
		if (sort !== 'relevance') params.set('sort', sort);
		if (offset > 0) params.set('offset', String(offset));
		const qs = params.toString();
		return qs ? `/search?${qs}` : '/search';
	}

	async function doSearch() {
		const currentRequest = ++requestId;
		lastWrittenUrl = buildUrl();
		goto(lastWrittenUrl, { replaceState: true, noScroll: true, keepFocus: true });

		if (!query.trim()) {
			documents = [];
			total = 0;
			terms = [];
			errors = [];
			facets = null;
			searched = false;
			loading = false;
			return;
		}

		loading = true;
		searched = true;
		const q = query;
		try {
			const res = await searchDocuments({ q, sort, offset, limit });
			if (currentRequest !== requestId) return;
			documents = res.documents;
			total = res.total;
			terms = res.terms;
			errors = res.errors;
			facets = res.facets;
			resultQuery = q;
		} catch (e) {
			if (currentRequest !== requestId) return;
			toasts.error(e instanceof Error ? e.message : 'Search failed');
		} finally {
			if (currentRequest === requestId) loading = false;
		}
	}

	function runQuery(q: string) {
		query = q;
		offset = 0;
		doSearch();
	}

	// Term spans index into resultQuery. If the box has unsearched edits, add the
	// facet to what's typed (no spans to reuse); chip removal waits for a search.
	const stale = $derived(loading || query !== resultQuery);

	function refine(key: string, value: string, negated = false) {
		if (loading) return;
		runQuery(addTerm(query, query === resultQuery ? terms : [], key, value, negated));
	}

	function removeTerm(term: SearchTerm) {
		if (stale) return;
		runQuery(removeSpan(resultQuery, term.start, term.end));
	}

	function termLabel(term: SearchTerm): string {
		const value = term.key === 'type' ? formatDocumentType(term.value) : term.value;
		return `${TERM_LABELS[term.key] ?? term.key}: ${value}`;
	}

	function handlePageChange(newOffset: number) {
		offset = newOffset;
		doSearch();
		window.scrollTo({ top: 0 });
	}

	// Sync state from the URL only on external navigation (back/forward, links). Local
	// state is read untracked so typing or toggling filters doesn't re-run this and
	// clobber the input with stale URL values.
	$effect(() => {
		const url = $page.url.pathname + $page.url.search;
		untrack(() => {
			if (url === lastWrittenUrl) return;
			syncFromUrl();
			doSearch();
		});
	});
</script>

<svelte:head>
	<title>{query ? `"${query}" - Search` : 'Search'} - DocManFu</title>
</svelte:head>

{#snippet facetGroup(title: string, key: string, items: { value: string; count: number }[])}
	{#if items.length > 0}
		<div>
			<h3
				class="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-1.5"
			>
				{title}
			</h3>
			<ul class="space-y-0.5">
				{#each items as item (item.value)}
					{@const isApplied = applied.has(`${key}:${item.value.toLowerCase()}`)}
					<li class="group flex items-center gap-1 text-sm">
						<button
							class="flex-1 min-w-0 flex items-center justify-between gap-2 px-2 py-1 rounded-md text-left cursor-pointer {isApplied
								? 'bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-300'
								: 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700/50'}"
							disabled={isApplied || loading}
							title="Only show {key}:{item.value}"
							onclick={() => refine(key, item.value)}
						>
							<span class="truncate"
								>{key === 'type' ? formatDocumentType(item.value) : item.value}</span
							>
							<span class="text-xs text-gray-400 tabular-nums">{item.count}</span>
						</button>
						{#if !isApplied}
							<button
								class="opacity-0 group-hover:opacity-100 focus:opacity-100 btn-icon !p-1"
								title="Exclude {key}:{item.value}"
								aria-label="Exclude {item.value}"
								disabled={loading}
								onclick={() => refine(key, item.value, true)}
							>
								<span class="i-lucide-minus text-xs"></span>
							</button>
						{/if}
					</li>
				{/each}
			</ul>
		</div>
	{/if}
{/snippet}

<div class="page-container">
	<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-6">Search Documents</h1>

	<div class="mb-4 space-y-3">
		<div class="flex gap-2">
			<div class="flex-1">
				<SearchQueryInput
					bind:value={query}
					tags={tagNames}
					placeholder={PLACEHOLDER}
					onSearch={runQuery}
				/>
			</div>
			<button
				class="btn-secondary flex items-center gap-1.5 shrink-0"
				aria-expanded={showTips}
				aria-label="Search tips"
				onclick={() => (showTips = !showTips)}
			>
				<span class="i-lucide-circle-help"></span>
				<span class="hidden sm:inline">Search tips</span>
			</button>
		</div>

		{#if showTips}
			<div class="card p-4 text-sm">
				<p class="text-gray-600 dark:text-gray-400 mb-3">
					Combine words with operators. Put <code class="font-mono">-</code> in front of anything to exclude
					it, and wrap values with spaces in quotes. Type an operator name for suggestions.
				</p>
				<div class="grid sm:grid-cols-2 gap-x-6 gap-y-1">
					{#each OPERATORS as op (op.key)}
						<button
							class="flex items-baseline gap-3 text-left px-2 py-1 rounded hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer"
							onclick={() => runQuery(op.example)}
						>
							<code class="font-mono text-brand-600 dark:text-brand-400 shrink-0">{op.example}</code
							>
							<span class="text-gray-500 dark:text-gray-400">{op.description}</span>
						</button>
					{/each}
					<div class="flex items-baseline gap-3 px-2 py-1">
						<code class="font-mono text-brand-600 dark:text-brand-400 shrink-0">"exact phrase"</code
						>
						<span class="text-gray-500 dark:text-gray-400">Words in this order</span>
					</div>
					<div class="flex items-baseline gap-3 px-2 py-1">
						<code class="font-mono text-brand-600 dark:text-brand-400 shrink-0">water OR power</code
						>
						<span class="text-gray-500 dark:text-gray-400">Either word</span>
					</div>
				</div>
			</div>
		{/if}

		{#if terms.length > 0 || errors.length > 0}
			<div class="flex flex-wrap items-center gap-2">
				{#each terms as term (`${term.start}-${term.end}`)}
					<span
						class="inline-flex items-center gap-1 pl-2.5 pr-1 py-0.5 rounded-full text-xs font-medium {term.negated
							? 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300'
							: 'bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-300'}"
					>
						{#if term.negated}<span class="i-lucide-ban text-[11px]"></span>{/if}
						{termLabel(term)}
						<button
							class="p-0.5 rounded-full hover:bg-black/10 dark:hover:bg-white/10 cursor-pointer"
							aria-label="Remove {termLabel(term)}"
							disabled={stale}
							onclick={() => removeTerm(term)}
						>
							<span class="i-lucide-x text-[11px] block"></span>
						</button>
					</span>
				{/each}
				{#each errors as error (error)}
					<span class="inline-flex items-center gap-1 text-xs text-amber-700 dark:text-amber-400">
						<span class="i-lucide-triangle-alert"></span>
						{error}
					</span>
				{/each}
			</div>
		{/if}
	</div>

	{#if !searched}
		<EmptyState
			icon="i-lucide-search"
			title="Search your documents"
			description="Search names, scanned text, notes and AI details — then narrow it down with operators."
		/>
		<div class="flex flex-wrap justify-center gap-2 -mt-4">
			{#each EXAMPLES as example (example)}
				<button
					class="font-mono text-xs px-2.5 py-1 rounded-full bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600 cursor-pointer"
					onclick={() => runQuery(example)}
				>
					{example}
				</button>
			{/each}
		</div>
	{:else}
		<div class="flex flex-col md:flex-row gap-6">
			{#if facets && total > 0}
				<button
					class="md:hidden btn-secondary flex items-center justify-center gap-1.5 text-sm"
					aria-expanded={showFacets}
					onclick={() => (showFacets = !showFacets)}
				>
					<span class="i-lucide-sliders-horizontal"></span>
					{showFacets ? 'Hide filters' : 'Refine results'}
				</button>
				<aside
					class="md:w-56 shrink-0 space-y-5 {showFacets ? '' : 'hidden md:block'}"
					aria-label="Refine results"
				>
					{@render facetGroup('Type', 'type', facets.types)}
					{@render facetGroup('Tags', 'tag', facets.tags)}
					{@render facetGroup('Year', 'date', facets.years)}
				</aside>
			{/if}

			<div class="flex-1 min-w-0">
				<div class="flex items-center justify-between gap-3 mb-4">
					<p class="text-sm text-gray-500 dark:text-gray-400">
						{#if !loading}{total} result{total === 1 ? '' : 's'}{/if}
					</p>
					<select
						class="input-base !w-auto text-sm"
						bind:value={sort}
						onchange={() => {
							offset = 0;
							doSearch();
						}}
						aria-label="Sort results"
					>
						{#each SORTS as option (option.value)}
							<option value={option.value}>{option.label}</option>
						{/each}
					</select>
				</div>

				{#if loading}
					<LoadingSpinner />
				{:else if documents.length === 0}
					<EmptyState
						icon="i-lucide-search-x"
						title="No results found"
						description="Try fewer filters, a different word, or remove a filter above."
					/>
				{:else}
					<div class="space-y-3 mb-6">
						{#each documents as doc (doc.id)}
							<a
								href="/documents/{doc.id}{highlightQuery
									? `?q=${encodeURIComponent(highlightQuery)}`
									: ''}"
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
										<div
											class="flex flex-wrap items-center gap-2 mt-1 text-xs text-gray-500 dark:text-gray-400"
										>
											{#if doc.document_type}
												<span
													class="badge bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300"
												>
													{formatDocumentType(doc.document_type)}
												</span>
											{/if}
											{#if doc.document_date}
												<span title="Document date"
													>{formatDate(`${doc.document_date}T00:00:00`)}</span
												>
											{/if}
											<span>{formatFileSize(doc.file_size)}</span>
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
				{/if}
			</div>
		</div>
	{/if}
</div>
