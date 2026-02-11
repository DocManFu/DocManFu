<script lang="ts">
	import type { DocumentType } from '$lib/types/index.js';
	import { formatDocumentType } from '$lib/utils/format.js';

	interface Props {
		documentType: string;
		tag: string;
		dateFrom: string;
		dateTo: string;
		onchange: () => void;
	}

	let { documentType = $bindable(), tag = $bindable(), dateFrom = $bindable(), dateTo = $bindable(), onchange }: Props = $props();

	const docTypes: DocumentType[] = [
		'bill', 'bank_statement', 'medical', 'insurance', 'tax',
		'invoice', 'receipt', 'legal', 'correspondence', 'report', 'other'
	];

	function clearFilters() {
		documentType = '';
		tag = '';
		dateFrom = '';
		dateTo = '';
		onchange();
	}

	let hasFilters = $derived(documentType || tag || dateFrom || dateTo);
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

	<input
		type="text"
		class="input-base w-40"
		placeholder="Filter by tag"
		bind:value={tag}
		onchange={() => onchange()}
	/>

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
