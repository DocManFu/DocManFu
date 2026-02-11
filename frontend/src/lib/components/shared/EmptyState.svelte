<script lang="ts">
	interface Props {
		icon?: string;
		title: string;
		description?: string;
	}

	let { icon = 'i-lucide-inbox', title, description }: Props = $props();
</script>

<div class="flex flex-col items-center justify-center py-16 text-center">
	<span class="{icon} text-5xl text-gray-300 dark:text-gray-600 mb-4"></span>
	<h3 class="text-lg font-medium text-gray-900 dark:text-gray-100 mb-1">{title}</h3>
	{#if description}
		<p class="text-sm text-gray-500 dark:text-gray-400">{description}</p>
	{/if}
</div>
