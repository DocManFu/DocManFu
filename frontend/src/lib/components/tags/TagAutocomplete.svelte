<script lang="ts">
	import { onMount } from 'svelte';
	import { listTags } from '$lib/api/tags.js';
	import type { TagWithCount } from '$lib/types/index.js';
	import TagBadge from './TagBadge.svelte';

	interface Props {
		selected: string[];
		onchange: (tags: string[]) => void;
	}

	let { selected, onchange }: Props = $props();

	let allTags = $state<TagWithCount[]>([]);
	let query = $state('');
	let open = $state(false);
	let highlightedIndex = $state(-1);
	let inputEl: HTMLInputElement;
	let containerEl: HTMLDivElement;

	let filtered = $derived(
		allTags
			.filter((t) => !selected.includes(t.name))
			.filter((t) => t.name.toLowerCase().includes(query.toLowerCase()))
	);

	onMount(async () => {
		try {
			allTags = await listTags();
		} catch {
			// silently fail — autocomplete just won't show suggestions
		}
	});

	function selectTag(name: string) {
		onchange([...selected, name]);
		query = '';
		highlightedIndex = -1;
		inputEl?.focus();
	}

	function removeTag(name: string) {
		onchange(selected.filter((t) => t !== name));
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'ArrowDown') {
			e.preventDefault();
			open = true;
			highlightedIndex = Math.min(highlightedIndex + 1, filtered.length - 1);
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			highlightedIndex = Math.max(highlightedIndex - 1, 0);
		} else if (e.key === 'Enter') {
			e.preventDefault();
			if (highlightedIndex >= 0 && highlightedIndex < filtered.length) {
				selectTag(filtered[highlightedIndex].name);
			}
		} else if (e.key === 'Escape') {
			open = false;
			highlightedIndex = -1;
		} else if (e.key === 'Backspace' && query === '' && selected.length > 0) {
			removeTag(selected[selected.length - 1]);
		}
	}

	function handleClickOutside(e: MouseEvent) {
		if (containerEl && !containerEl.contains(e.target as Node)) {
			open = false;
			highlightedIndex = -1;
		}
	}

	function handleInput() {
		open = query.length > 0 || true;
		highlightedIndex = -1;
	}

	// Get tag object for a selected name (for badge color display)
	function getTagObj(name: string) {
		const found = allTags.find((t) => t.name === name);
		return found ?? { id: name, name, color: '#6B7280' };
	}
</script>

<svelte:window onclick={handleClickOutside} />

<div class="relative" bind:this={containerEl}>
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_interactive_supports_focus -->
	<div
		class="input-base flex flex-wrap items-center gap-1 min-h-[2.25rem] cursor-text py-1 px-2"
		onclick={() => inputEl?.focus()}
		role="combobox"
		aria-controls="tag-autocomplete-list"
		aria-expanded={open}
		aria-haspopup="listbox"
	>
		{#each selected as tagName (tagName)}
			<TagBadge tag={getTagObj(tagName)} removable onremove={() => removeTag(tagName)} />
		{/each}
		<input
			bind:this={inputEl}
			type="text"
			class="flex-1 min-w-[80px] border-0 outline-none bg-transparent text-sm p-0 m-0 text-gray-900 dark:text-gray-100 placeholder:text-gray-400"
			placeholder={selected.length === 0 ? 'Filter by tags...' : ''}
			bind:value={query}
			oninput={handleInput}
			onfocus={() => (open = true)}
			onkeydown={handleKeydown}
		/>
	</div>

	{#if open && filtered.length > 0}
		<ul
			id="tag-autocomplete-list"
			class="absolute z-50 mt-1 w-full max-h-48 overflow-auto bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg"
			role="listbox"
		>
			{#each filtered as tag, i (tag.id)}
				<li
					class="flex items-center gap-2 px-3 py-2 text-sm cursor-pointer
						{i === highlightedIndex ? 'bg-brand-50 dark:bg-brand-900/30' : 'hover:bg-gray-50 dark:hover:bg-gray-800/50'}"
					role="option"
					aria-selected={i === highlightedIndex}
					onclick={() => selectTag(tag.name)}
					onmouseenter={() => (highlightedIndex = i)}
				>
					<span
						class="w-2.5 h-2.5 rounded-full flex-shrink-0"
						style="background-color: {tag.color};"
					></span>
					<span class="flex-1 text-gray-900 dark:text-gray-100">{tag.name}</span>
					<span class="text-xs text-gray-400">{tag.document_count}</span>
				</li>
			{/each}
		</ul>
	{/if}
</div>
