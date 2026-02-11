<script lang="ts">
	import type { Tag } from '$lib/types/index.js';

	interface Props {
		tag: Tag;
		removable?: boolean;
		onremove?: () => void;
	}

	let { tag, removable = false, onremove }: Props = $props();
</script>

<span
	class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
	style="background-color: {tag.color}20; color: {tag.color}; border: 1px solid {tag.color}40;"
>
	{tag.name}
	{#if removable && onremove}
		<button
			class="hover:opacity-70 cursor-pointer ml-0.5"
			aria-label="Remove tag {tag.name}"
			onclick={onremove}
		>
			<span class="i-lucide-x text-[10px]"></span>
		</button>
	{/if}
</span>
