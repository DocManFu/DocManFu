<script lang="ts">
	interface Props {
		progress: number;
	}

	let { progress }: Props = $props();
</script>

<div class="w-full bg-gray-200 rounded-full h-1.5 overflow-hidden">
	<div
		class="bg-brand-500 h-full rounded-full transition-all duration-500"
		style="width: {progress}%"
	></div>
</div>
