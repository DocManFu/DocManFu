<script lang="ts">
	import { showShortcutsHelp } from '$lib/stores/shortcuts.js';

	function isInputFocused(): boolean {
		const el = document.activeElement;
		if (!el) return false;
		const tag = el.tagName.toLowerCase();
		return (
			tag === 'input' ||
			tag === 'textarea' ||
			tag === 'select' ||
			(el as HTMLElement).isContentEditable
		);
	}

	function handleKeydown(e: KeyboardEvent) {
		// Escape always works
		if (e.key === 'Escape') {
			if ($showShortcutsHelp) {
				showShortcutsHelp.set(false);
				return;
			}
			const active = document.activeElement as HTMLElement;
			if (active && active !== document.body) {
				active.blur();
			}
			return;
		}

		// All other shortcuts skip when input is focused
		if (isInputFocused()) return;

		if (e.key === '/') {
			e.preventDefault();
			const search = document.getElementById('global-search');
			if (search) search.focus();
			return;
		}

		if (e.key === '?') {
			e.preventDefault();
			showShortcutsHelp.update((v) => !v);
			return;
		}

		if (e.key === 'j') {
			document
				.querySelector('.page-container')
				?.dispatchEvent(
					new CustomEvent('docnavigate', { detail: { direction: 'next' }, bubbles: true }),
				);
			return;
		}

		if (e.key === 'k') {
			document
				.querySelector('.page-container')
				?.dispatchEvent(
					new CustomEvent('docnavigate', { detail: { direction: 'prev' }, bubbles: true }),
				);
			return;
		}

		if (e.key === 'Enter') {
			document
				.querySelector('.page-container')
				?.dispatchEvent(
					new CustomEvent('docnavigate', { detail: { direction: 'open' }, bubbles: true }),
				);
			return;
		}

		if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
			document
				.querySelector('.page-container')
				?.dispatchEvent(
					new CustomEvent('docnavigate', { detail: { direction: 'selectAll' }, bubbles: true }),
				);
			return;
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />
