<script lang="ts">
	interface Props {
		total: number;
		offset: number;
		limit: number;
		onchange: (offset: number) => void;
	}

	let { total, offset, limit, onchange }: Props = $props();

	let currentPage = $derived(Math.floor(offset / limit) + 1);
	let totalPages = $derived(Math.ceil(total / limit));
	let hasPrev = $derived(offset > 0);
	let hasNext = $derived(offset + limit < total);
</script>

{#if totalPages > 1}
	<div class="flex items-center justify-between">
		<p class="text-sm text-gray-600 dark:text-gray-400">
			Showing {offset + 1}–{Math.min(offset + limit, total)} of {total}
		</p>
		<div class="flex items-center gap-1">
			<button
				class="btn-ghost btn-sm"
				disabled={!hasPrev}
				aria-label="Previous page"
				onclick={() => onchange(Math.max(0, offset - limit))}
			>
				<span class="i-lucide-chevron-left"></span>
			</button>

			{#each Array.from({ length: totalPages }, (_, i) => i + 1) as pg}
				{#if totalPages <= 7 || pg === 1 || pg === totalPages || Math.abs(pg - currentPage) <= 1}
					<button
						class="btn-sm min-w-8 {pg === currentPage ? 'btn-primary' : 'btn-ghost'}"
						onclick={() => onchange((pg - 1) * limit)}
					>
						{pg}
					</button>
				{:else if pg === 2 || pg === totalPages - 1}
					<span class="px-1 text-gray-400">...</span>
				{/if}
			{/each}

			<button
				class="btn-ghost btn-sm"
				disabled={!hasNext}
				aria-label="Next page"
				onclick={() => onchange(offset + limit)}
			>
				<span class="i-lucide-chevron-right"></span>
			</button>
		</div>
	</div>
{/if}
