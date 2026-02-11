<script lang="ts">
	import type { ViewMode } from '$lib/stores/preferences.js';

	interface Props {
		value: ViewMode;
		onchange: (mode: ViewMode) => void;
	}

	let { value, onchange }: Props = $props();
</script>

<div class="flex items-center border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
	<button
		class="p-1.5 transition-colors {value === 'grid'
			? 'bg-brand-100 dark:bg-brand-900/40 text-brand-700 dark:text-brand-300'
			: 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'}"
		onclick={() => onchange('grid')}
		aria-label="Grid view"
		title="Grid view"
	>
		<span class="i-lucide-layout-grid text-base"></span>
	</button>
	<button
		class="p-1.5 transition-colors {value === 'list'
			? 'bg-brand-100 dark:bg-brand-900/40 text-brand-700 dark:text-brand-300'
			: 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'}"
		onclick={() => onchange('list')}
		aria-label="List view"
		title="List view"
	>
		<span class="i-lucide-list text-base"></span>
	</button>
</div>
