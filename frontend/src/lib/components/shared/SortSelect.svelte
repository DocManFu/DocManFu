<script lang="ts">
	interface Props {
		sortBy: string;
		sortOrder: string;
		onchange: () => void;
	}

	let { sortBy = $bindable(), sortOrder = $bindable(), onchange }: Props = $props();

	const options = [
		{ value: 'upload_date', label: 'Upload Date' },
		{ value: 'name', label: 'Name' },
		{ value: 'size', label: 'Size' },
		{ value: 'type', label: 'Type' }
	];
</script>

<div class="flex items-center gap-2">
	<select class="input-base w-auto" bind:value={sortBy} onchange={() => onchange()}>
		{#each options as opt}
			<option value={opt.value}>{opt.label}</option>
		{/each}
	</select>

	<button
		class="btn-icon"
		title="Toggle sort order"
		onclick={() => {
			sortOrder = sortOrder === 'asc' ? 'desc' : 'asc';
			onchange();
		}}
	>
		<span class={sortOrder === 'asc' ? 'i-lucide-arrow-up' : 'i-lucide-arrow-down'}></span>
	</button>
</div>
