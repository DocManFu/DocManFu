<script lang="ts">
	interface Props {
		untagged: boolean;
		untyped: boolean;
		onchange: () => void;
	}

	let { untagged = $bindable(), untyped = $bindable(), onchange }: Props = $props();
</script>

<div class="flex items-center gap-2">
	<span class="text-xs text-gray-500 dark:text-gray-400 mr-1">Quick:</span>
	<button
		class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border transition-colors
			{untagged
				? 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-700'
				: 'bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-700'}"
		onclick={() => { untagged = !untagged; onchange(); }}
	>
		<span class="i-lucide-tag text-[11px]"></span>
		Untagged
	</button>
	<button
		class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border transition-colors
			{untyped
				? 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-700'
				: 'bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-700'}"
		onclick={() => { untyped = !untyped; onchange(); }}
	>
		<span class="i-lucide-file-question text-[11px]"></span>
		Untyped
	</button>
</div>
