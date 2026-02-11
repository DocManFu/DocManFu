<script lang="ts">
	interface Props {
		open: boolean;
		title: string;
		message: string;
		confirmLabel?: string;
		confirmClass?: string;
		onconfirm: () => void;
		oncancel: () => void;
	}

	let {
		open,
		title,
		message,
		confirmLabel = 'Confirm',
		confirmClass = 'btn-danger',
		onconfirm,
		oncancel
	}: Props = $props();
</script>

{#if open}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-50 flex items-center justify-center"
		onkeydown={(e) => e.key === 'Escape' && oncancel()}
	>
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<div class="absolute inset-0 bg-black/40" role="presentation" onclick={oncancel}></div>

		<div class="relative bg-white dark:bg-gray-800 rounded-xl shadow-xl p-6 max-w-md w-full mx-4">
			<h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">{title}</h3>
			<p class="text-sm text-gray-600 dark:text-gray-400 mb-6">{message}</p>
			<div class="flex justify-end gap-3">
				<button class="btn-secondary" onclick={oncancel}>Cancel</button>
				<button class={confirmClass} onclick={onconfirm}>{confirmLabel}</button>
			</div>
		</div>
	</div>
{/if}
