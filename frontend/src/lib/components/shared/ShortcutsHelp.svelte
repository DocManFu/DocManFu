<script lang="ts">
	import { showShortcutsHelp } from '$lib/stores/shortcuts.js';

	const shortcuts = [
		{ keys: ['/'], description: 'Focus search' },
		{ keys: ['?'], description: 'Toggle this help' },
		{ keys: ['Esc'], description: 'Blur / close' },
		{ keys: ['j'], description: 'Next document' },
		{ keys: ['k'], description: 'Previous document' },
		{ keys: ['Enter'], description: 'Open focused document' },
		{ keys: ['Ctrl', 'A'], description: 'Select all (in select mode)' },
	];
</script>

{#if $showShortcutsHelp}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-50 flex items-center justify-center"
		onkeydown={(e) => e.key === 'Escape' && showShortcutsHelp.set(false)}
	>
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<div
			class="absolute inset-0 bg-black/40"
			role="presentation"
			onclick={() => showShortcutsHelp.set(false)}
		></div>

		<div class="relative bg-white dark:bg-gray-800 rounded-xl shadow-xl p-6 max-w-md w-full mx-4">
			<div class="flex items-center justify-between mb-4">
				<h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100">Keyboard Shortcuts</h3>
				<button
					class="btn-icon"
					aria-label="Close shortcuts help"
					onclick={() => showShortcutsHelp.set(false)}
				>
					<span class="i-lucide-x"></span>
				</button>
			</div>

			<div class="space-y-3">
				{#each shortcuts as shortcut}
					<div class="flex items-center justify-between">
						<span class="text-sm text-gray-600 dark:text-gray-400">{shortcut.description}</span>
						<div class="flex items-center gap-1">
							{#each shortcut.keys as key}
								<kbd
									class="px-2 py-1 text-xs font-mono bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600 rounded"
									>{key}</kbd
								>
								{#if shortcut.keys.indexOf(key) < shortcut.keys.length - 1}
									<span class="text-gray-400 text-xs">+</span>
								{/if}
							{/each}
						</div>
					</div>
				{/each}
			</div>
		</div>
	</div>
{/if}
