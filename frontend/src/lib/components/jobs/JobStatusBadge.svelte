<script lang="ts">
	interface Props {
		status: 'pending' | 'processing' | 'completed' | 'failed';
	}

	let { status }: Props = $props();

	const styles: Record<string, string> = {
		pending: 'bg-yellow-100 text-yellow-800',
		processing: 'bg-blue-100 text-blue-800',
		completed: 'bg-green-100 text-green-800',
		failed: 'bg-red-100 text-red-800'
	};

	const icons: Record<string, string> = {
		pending: 'i-lucide-clock',
		processing: 'i-lucide-loader-2 animate-spin',
		completed: 'i-lucide-check-circle',
		failed: 'i-lucide-x-circle'
	};
</script>

<span class="badge {styles[status]}">
	<span class="{icons[status]} mr-1 text-xs"></span>
	{status}
</span>
