<script lang="ts" generics="T">
	import { onMount } from 'svelte';
	import type { Snippet } from 'svelte';

	interface Props {
		items: T[];
		itemHeight: number;
		overscan?: number;
		children: Snippet<[T, number]>;
	}

	let { items, itemHeight, overscan = 5, children }: Props = $props();

	let containerEl: HTMLDivElement;
	let scrollY = $state(0);
	let containerTop = $state(0);

	let totalHeight = $derived(items.length * itemHeight);

	let startIndex = $derived.by(() => {
		const scrollOffset = Math.max(0, scrollY - containerTop);
		return Math.max(0, Math.floor(scrollOffset / itemHeight) - overscan);
	});

	let endIndex = $derived.by(() => {
		const scrollOffset = Math.max(0, scrollY - containerTop);
		const viewportHeight = typeof window !== 'undefined' ? window.innerHeight : 800;
		return Math.min(
			items.length,
			Math.ceil((scrollOffset + viewportHeight) / itemHeight) + overscan,
		);
	});

	let visibleItems = $derived(items.slice(startIndex, endIndex));
	let offsetY = $derived(startIndex * itemHeight);

	function onScroll() {
		requestAnimationFrame(() => {
			scrollY = window.scrollY;
		});
	}

	function updateContainerTop() {
		if (containerEl) {
			const rect = containerEl.getBoundingClientRect();
			containerTop = rect.top + window.scrollY;
		}
	}

	onMount(() => {
		updateContainerTop();
		window.addEventListener('scroll', onScroll, { passive: true });
		window.addEventListener('resize', updateContainerTop);
		return () => {
			window.removeEventListener('scroll', onScroll);
			window.removeEventListener('resize', updateContainerTop);
		};
	});

	export function scrollToIndex(index: number) {
		const targetY = containerTop + index * itemHeight - window.innerHeight / 3;
		window.scrollTo({ top: Math.max(0, targetY), behavior: 'smooth' });
	}
</script>

<div bind:this={containerEl} style="height: {totalHeight}px; position: relative;">
	<div style="transform: translateY({offsetY}px);">
		{#each visibleItems as item, i (startIndex + i)}
			{@render children(item, startIndex + i)}
		{/each}
	</div>
</div>
