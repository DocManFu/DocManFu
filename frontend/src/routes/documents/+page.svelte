<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { listDocuments, bulkDeleteDocuments, bulkReprocessDocuments, downloadExportCsv } from '$lib/api/documents.js';
	import type { DocumentListItem, ListDocumentsParams } from '$lib/types/index.js';
	import DocumentCard from '$lib/components/documents/DocumentCard.svelte';
	import DocumentRow from '$lib/components/documents/DocumentRow.svelte';
	import FilterPanel from '$lib/components/shared/FilterPanel.svelte';
	import QuickFilters from '$lib/components/shared/QuickFilters.svelte';
	import SortSelect from '$lib/components/shared/SortSelect.svelte';
	import ViewToggle from '$lib/components/shared/ViewToggle.svelte';
	import VirtualList from '$lib/components/shared/VirtualList.svelte';
	import LoadingSpinner from '$lib/components/shared/LoadingSpinner.svelte';
	import EmptyState from '$lib/components/shared/EmptyState.svelte';
	import ConfirmDialog from '$lib/components/shared/ConfirmDialog.svelte';
	import { toasts } from '$lib/stores/toast.js';
	import { jobStore } from '$lib/stores/jobs.js';
	import { viewMode } from '$lib/stores/preferences.js';
	import type { ViewMode } from '$lib/stores/preferences.js';

	let documents = $state<DocumentListItem[]>([]);
	let total = $state(0);
	let loading = $state(true);
	let loadingMore = $state(false);

	const BATCH_SIZE = 48;
	let currentOffset = $state(0);
	let hasMore = $derived(documents.length < total);

	// Filter state from URL params
	let documentType = $state('');
	let tags = $state<string[]>([]);
	let dateFrom = $state('');
	let dateTo = $state('');
	let sortBy = $state('upload_date');
	let sortOrder = $state('desc');
	let untagged = $state(false);
	let untyped = $state(false);

	// View mode
	let currentViewMode = $state<ViewMode>('grid');
	viewMode.subscribe((v) => (currentViewMode = v));

	// Selection / bulk mode
	let selectMode = $state(false);
	let selectedIds = $state<Set<string>>(new Set());
	let showBulkDeleteDialog = $state(false);
	let bulkProcessing = $state(false);

	// j/k navigation
	let focusedIndex = $state(-1);

	// Scroll-to-top visibility
	let showScrollTop = $state(false);

	// Sentinel for infinite scroll
	let sentinelEl: HTMLDivElement;
	let observer: IntersectionObserver;

	// Virtual list reference
	let virtualListEl: VirtualList<DocumentListItem>;

	function syncFromUrl() {
		const p = $page.url.searchParams;
		documentType = p.get('document_type') ?? '';
		const tagParam = p.get('tag') ?? '';
		tags = tagParam ? tagParam.split(',').map((t) => t.trim()).filter(Boolean) : [];
		dateFrom = p.get('date_from') ?? '';
		dateTo = p.get('date_to') ?? '';
		sortBy = p.get('sort_by') ?? 'upload_date';
		sortOrder = p.get('sort_order') ?? 'desc';
		untagged = p.get('untagged') === 'true';
		untyped = p.get('untyped') === 'true';
	}

	function buildUrl(): string {
		const params = new URLSearchParams();
		if (documentType) params.set('document_type', documentType);
		if (tags.length > 0) params.set('tag', tags.join(','));
		if (dateFrom) params.set('date_from', dateFrom);
		if (dateTo) params.set('date_to', dateTo);
		if (sortBy !== 'upload_date') params.set('sort_by', sortBy);
		if (sortOrder !== 'desc') params.set('sort_order', sortOrder);
		if (untagged) params.set('untagged', 'true');
		if (untyped) params.set('untyped', 'true');
		const qs = params.toString();
		return qs ? `/documents?${qs}` : '/documents';
	}

	function buildApiParams(offset: number): ListDocumentsParams {
		const params: ListDocumentsParams = { offset, limit: BATCH_SIZE };
		if (documentType) params.document_type = documentType;
		if (tags.length > 0) params.tag = tags.join(',');
		if (dateFrom) params.date_from = dateFrom;
		if (dateTo) params.date_to = dateTo;
		if (untagged) params.untagged = 'true';
		if (untyped) params.untyped = 'true';
		params.sort_by = sortBy as ListDocumentsParams['sort_by'];
		params.sort_order = sortOrder as ListDocumentsParams['sort_order'];
		return params;
	}

	async function fetchDocuments() {
		loading = true;
		currentOffset = 0;
		focusedIndex = -1;
		try {
			const res = await listDocuments(buildApiParams(0));
			documents = res.documents;
			total = res.total;
			currentOffset = res.documents.length;
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to load documents');
		} finally {
			loading = false;
		}
	}

	async function loadMore() {
		if (loadingMore || !hasMore) return;
		loadingMore = true;
		try {
			const res = await listDocuments(buildApiParams(currentOffset));
			documents = [...documents, ...res.documents];
			total = res.total;
			currentOffset += res.documents.length;
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to load more documents');
		} finally {
			loadingMore = false;
		}
	}

	function handleFilterChange() {
		goto(buildUrl(), { replaceState: true, noScroll: true });
		fetchDocuments();
	}

	function handleViewModeChange(mode: ViewMode) {
		viewMode.set(mode);
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
			// Auto-load more when near end
			if (focusedIndex >= documents.length - 3 && hasMore) {
				loadMore();
			}
			// Scroll focused row into view in list mode
			if (currentViewMode === 'list' && virtualListEl) {
				virtualListEl.scrollToIndex(focusedIndex);
			}
		} else if (direction === 'prev') {
			focusedIndex = Math.max(focusedIndex - 1, 0);
			if (currentViewMode === 'list' && virtualListEl) {
				virtualListEl.scrollToIndex(focusedIndex);
			}
		} else if (direction === 'open' && focusedIndex >= 0 && focusedIndex < documents.length) {
			goto(`/documents/${documents[focusedIndex].id}`);
		} else if (direction === 'selectAll' && selectMode) {
			selectAll();
		}
	}

	function scrollToTop() {
		window.scrollTo({ top: 0, behavior: 'smooth' });
	}

	function handleWindowScroll() {
		showScrollTop = window.scrollY > window.innerHeight;
	}

	let containerEl: HTMLDivElement;

	onMount(() => {
		syncFromUrl();
		fetchDocuments();
		containerEl?.addEventListener('docnavigate', handleDocNavigate);
		window.addEventListener('scroll', handleWindowScroll, { passive: true });

		// IntersectionObserver for infinite scroll
		observer = new IntersectionObserver(
			(entries) => {
				if (entries[0]?.isIntersecting && hasMore && !loading && !loadingMore) {
					loadMore();
				}
			},
			{ rootMargin: '200px' }
		);

		const unsubDocUpdated = jobStore.onDocumentUpdated(() => {
			fetchDocuments();
		});

		return () => {
			containerEl?.removeEventListener('docnavigate', handleDocNavigate);
			window.removeEventListener('scroll', handleWindowScroll);
			observer?.disconnect();
			unsubDocUpdated();
		};
	});

	// Observe sentinel when it exists
	$effect(() => {
		if (sentinelEl && observer) {
			observer.observe(sentinelEl);
			return () => observer?.unobserve(sentinelEl);
		}
	});
</script>

<svelte:head>
	<title>Documents - DocManFu</title>
</svelte:head>

<div class="page-container" bind:this={containerEl}>
	<div class="flex flex-wrap items-center justify-between gap-3 mb-6">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">Documents</h1>
		<div class="flex items-center gap-2">
			<ViewToggle value={currentViewMode} onchange={handleViewModeChange} />
			<button
				class="btn-secondary btn-sm"
				title="Export CSV"
				onclick={() => downloadExportCsv({
					document_type: documentType || undefined,
					tag: tags.length > 0 ? tags.join(',') : undefined,
					date_from: dateFrom || undefined,
					date_to: dateTo || undefined,
					untagged: untagged ? 'true' : undefined,
					untyped: untyped ? 'true' : undefined
				})}
			>
				<span class="i-lucide-download sm:mr-1"></span><span class="hidden sm:inline">CSV</span>
			</button>
			<button
				class="btn-secondary btn-sm"
				title={selectMode ? 'Cancel selection' : 'Select documents'}
				onclick={() => selectMode ? exitSelectMode() : (selectMode = true)}
			>
				<span class="i-lucide-check-square sm:mr-1"></span>
				<span class="hidden sm:inline">{selectMode ? 'Cancel' : 'Select'}</span>
			</button>
			<a href="/upload" class="btn-primary no-underline" title="Upload document">
				<span class="i-lucide-upload sm:mr-2"></span><span class="hidden sm:inline">Upload</span>
			</a>
		</div>
	</div>

	<div class="card p-4 mb-6">
		<div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
			<FilterPanel
				bind:documentType
				bind:tags
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
		<div class="border-t border-gray-100 dark:border-gray-700 mt-3 pt-3">
			<QuickFilters
				bind:untagged
				bind:untyped
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

		{#if currentViewMode === 'grid'}
			<!-- Grid View -->
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
		{:else}
			<!-- List View with Virtual Scrolling -->
			<div class="card divide-y divide-gray-100 dark:divide-gray-800 overflow-hidden mb-6">
				<VirtualList bind:this={virtualListEl} items={documents} itemHeight={48}>
					{#snippet children(doc, i)}
						{#if selectMode}
							<!-- svelte-ignore a11y_click_events_have_key_events -->
							<!-- svelte-ignore a11y_no_static_element_interactions -->
							<div class="flex items-center cursor-pointer" onclick={() => toggleSelect(doc.id)}>
								<div class="flex-shrink-0 pl-3">
									<div class="w-5 h-5 rounded border-2 flex items-center justify-center
										{selectedIds.has(doc.id) ? 'bg-brand-600 border-brand-600' : 'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600'}">
										{#if selectedIds.has(doc.id)}
											<span class="i-lucide-check text-white text-xs"></span>
										{/if}
									</div>
								</div>
								<div class="flex-1 min-w-0">
									<DocumentRow document={doc} selected={selectedIds.has(doc.id)} />
								</div>
							</div>
						{:else}
							<DocumentRow document={doc} focused={focusedIndex === i} />
						{/if}
					{/snippet}
				</VirtualList>
			</div>
		{/if}

		<!-- Infinite scroll status -->
		<div class="flex flex-col items-center gap-2 py-4">
			<span class="text-sm text-gray-500 dark:text-gray-400">
				Showing {documents.length} of {total}
			</span>
			{#if hasMore}
				{#if loadingMore}
					<LoadingSpinner />
				{:else}
					<div bind:this={sentinelEl}></div>
					<button class="btn-secondary btn-sm" onclick={loadMore}>
						Load more
					</button>
				{/if}
			{/if}
		</div>
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

<!-- Scroll to top button -->
{#if showScrollTop}
	<button
		class="fixed bottom-6 right-6 z-30 w-10 h-10 rounded-full bg-white dark:bg-gray-800 shadow-lg border border-gray-200 dark:border-gray-700 flex items-center justify-center text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
		onclick={scrollToTop}
		aria-label="Scroll to top"
	>
		<span class="i-lucide-chevron-up text-lg"></span>
	</button>
{/if}

<ConfirmDialog
	open={showBulkDeleteDialog}
	title="Delete {selectedIds.size} Documents"
	message="This will soft-delete the selected documents. They won't appear in search results anymore. Are you sure?"
	confirmLabel={bulkProcessing ? 'Deleting...' : 'Delete All'}
	onconfirm={handleBulkDelete}
	oncancel={() => (showBulkDeleteDialog = false)}
/>
