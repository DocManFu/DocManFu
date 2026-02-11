<script lang="ts">
	interface Props {
		onfiles: (files: File[]) => void;
		disabled?: boolean;
	}

	let { onfiles, disabled = false }: Props = $props();
	let dragging = $state(false);
	let fileInput: HTMLInputElement;

	function handleDrop(e: DragEvent) {
		e.preventDefault();
		dragging = false;
		if (disabled || !e.dataTransfer) return;

		const files = Array.from(e.dataTransfer.files).filter(
			(f) => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf')
		);
		if (files.length > 0) onfiles(files);
	}

	function handleDragOver(e: DragEvent) {
		e.preventDefault();
		if (!disabled) dragging = true;
	}

	function handleDragLeave() {
		dragging = false;
	}

	function handleFileSelect(e: Event) {
		const target = e.target as HTMLInputElement;
		if (!target.files) return;
		const files = Array.from(target.files);
		if (files.length > 0) onfiles(files);
		target.value = '';
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<div
	class="border-2 border-dashed rounded-xl p-12 text-center transition-colors
		{dragging ? 'border-brand-400 bg-brand-50 dark:bg-brand-900/20' : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'}
		{disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}"
	role="button"
	tabindex="0"
	ondrop={handleDrop}
	ondragover={handleDragOver}
	ondragleave={handleDragLeave}
	onclick={() => !disabled && fileInput.click()}
	onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && !disabled && fileInput.click()}
>
	<span class="i-lucide-upload-cloud text-4xl {dragging ? 'text-brand-500' : 'text-gray-400'} mb-3 block mx-auto"></span>
	<p class="text-base font-medium text-gray-700 dark:text-gray-300">
		{dragging ? 'Drop PDF files here' : 'Drag & drop PDF files here'}
	</p>
	<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">or click to browse (max 50 MB per file)</p>
</div>

<input
	type="file"
	accept=".pdf,application/pdf"
	multiple
	class="hidden"
	bind:this={fileInput}
	onchange={handleFileSelect}
/>
