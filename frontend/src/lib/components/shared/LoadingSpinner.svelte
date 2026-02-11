<script lang="ts">
	interface Props {
		size?: 'sm' | 'md' | 'lg';
	}

	let { size = 'md' }: Props = $props();

	const sizes = { sm: 'text-lg', md: 'text-2xl', lg: 'text-4xl' };
</script>

<div class="flex items-center justify-center py-8">
	<span class="i-lucide-loader-2 animate-spin text-brand-500 {sizes[size]}"></span>
</div>
