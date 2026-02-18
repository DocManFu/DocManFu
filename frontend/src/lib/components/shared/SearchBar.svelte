<script lang="ts">
	import { debounce } from '$lib/utils/debounce.js';

	interface Props {
		value: string;
		placeholder?: string;
		onSearch: (query: string) => void;
	}

	let { value = $bindable(), placeholder = 'Search documents...', onSearch }: Props = $props();

	const debouncedSearch = debounce((q: string) => onSearch(q), 300);

	function handleInput(e: Event) {
		const target = e.target as HTMLInputElement;
		value = target.value;
		debouncedSearch(value);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			onSearch(value);
		}
	}

	function clear() {
		value = '';
		onSearch('');
	}
</script>

<div class="relative">
	<span
		class="i-lucide-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500"
	></span>
	<input
		type="text"
		class="input-base pl-10 pr-8"
		{placeholder}
		{value}
		oninput={handleInput}
		onkeydown={handleKeydown}
	/>
	{#if value}
		<button
			class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 cursor-pointer"
			aria-label="Clear search"
			onclick={clear}
		>
			<span class="i-lucide-x text-sm"></span>
		</button>
	{/if}
</div>
