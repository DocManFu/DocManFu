<script lang="ts">
	import type { Toast } from '$lib/stores/toast.js';

	interface Props {
		toast: Toast;
	}

	let { toast }: Props = $props();

	const icons: Record<Toast['type'], string> = {
		success: 'i-lucide-check-circle',
		error: 'i-lucide-alert-circle',
		info: 'i-lucide-info'
	};

	const colors: Record<Toast['type'], string> = {
		success: 'bg-green-50 text-green-800 border-green-200 dark:bg-green-900/50 dark:text-green-300 dark:border-green-800',
		error: 'bg-red-50 text-red-800 border-red-200 dark:bg-red-900/50 dark:text-red-300 dark:border-red-800',
		info: 'bg-blue-50 text-blue-800 border-blue-200 dark:bg-blue-900/50 dark:text-blue-300 dark:border-blue-800'
	};
</script>

<div class="flex items-center gap-2 px-4 py-3 rounded-lg border shadow-lg text-sm {colors[toast.type]}">
	<span class={icons[toast.type]}></span>
	<span>{toast.message}</span>
</div>
