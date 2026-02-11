<script lang="ts">
	import type { DocumentType } from '$lib/types/index.js';
	import { formatDocumentType } from '$lib/utils/format.js';
	import TagAutocomplete from '$lib/components/tags/TagAutocomplete.svelte';

	interface Props {
		documentType: string;
		tags: string[];
		dateFrom: string;
		dateTo: string;
		onchange: () => void;
	}

	let { documentType = $bindable(), tags = $bindable(), dateFrom = $bindable(), dateTo = $bindable(), onchange }: Props = $props();

	const docTypes: DocumentType[] = [
		'bill', 'bank_statement', 'medical', 'insurance', 'tax',
		'invoice', 'receipt', 'legal', 'correspondence', 'report', 'other'
	];

	function clearFilters() {
		documentType = '';
		tags = [];
		dateFrom = '';
		dateTo = '';
		onchange();
	}

	function handleTagChange(newTags: string[]) {
		tags = newTags;
		onchange();
	}

	let hasFilters = $derived(documentType || tags.length > 0 || dateFrom || dateTo);
</script>

<div class="flex flex-wrap items-center gap-3">
	<select
		class="input-base w-auto"
		bind:value={documentType}
		onchange={() => onchange()}
	>
		<option value="">All types</option>
		{#each docTypes as dt}
			<option value={dt}>{formatDocumentType(dt)}</option>
		{/each}
	</select>

	<div class="w-56">
		<TagAutocomplete selected={tags} onchange={handleTagChange} />
	</div>

	<input
		type="date"
		class="input-base w-auto"
		bind:value={dateFrom}
		onchange={() => onchange()}
	/>
	<span class="text-gray-400 dark:text-gray-500 text-sm">to</span>
	<input
		type="date"
		class="input-base w-auto"
		bind:value={dateTo}
		onchange={() => onchange()}
	/>

	{#if hasFilters}
		<button class="btn-ghost btn-sm text-xs" onclick={clearFilters}>
			<span class="i-lucide-x mr-1"></span>Clear
		</button>
	{/if}
</div>
