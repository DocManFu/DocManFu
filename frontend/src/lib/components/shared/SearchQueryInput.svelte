<script lang="ts">
	import { onDestroy, tick } from 'svelte';
	import { debounce } from '$lib/utils/debounce.js';
	import { formatDocumentType } from '$lib/utils/format.js';
	import {
		DOCUMENT_TYPES,
		OPERATORS,
		OPERATOR_ALIASES,
		quoteValue,
		tokenAt,
	} from '$lib/utils/searchQuery.js';

	interface Props {
		value: string;
		/** Tag names offered after `tag:` */
		tags?: string[];
		placeholder?: string;
		onSearch: (query: string) => void;
	}

	let {
		value = $bindable(),
		tags = [],
		placeholder = 'Search documents…',
		onSearch,
	}: Props = $props();

	interface Suggestion {
		label: string;
		hint: string;
		insert: string;
		/** Inserting an operator name keeps the menu open for its values */
		continues: boolean;
	}

	let input: HTMLInputElement;
	let suggestions = $state<Suggestion[]>([]);
	let active = $state(-1);
	let token = { start: 0, end: 0, text: '' };

	// Skip if the query changed since (e.g. a facet click replaced it)
	const debouncedSearch = debounce((q: string) => {
		if (q === value) onSearch(q);
	}, 350);
	onDestroy(() => debouncedSearch.cancel());

	function valuesFor(key: string): { value: string; hint: string }[] {
		if (key === 'tag') return tags.map((t) => ({ value: t, hint: 'tag' }));
		if (key === 'type')
			return DOCUMENT_TYPES.map((t) => ({ value: t, hint: formatDocumentType(t) }));
		const op = OPERATORS.find((o) => o.key === key);
		return (op?.values ?? []).map((v) => ({ value: v, hint: op!.description }));
	}

	function computeSuggestions() {
		token = tokenAt(value, input?.selectionStart ?? value.length);
		const neg = token.text.startsWith('-') ? '-' : '';
		const body = token.text.slice(neg.length);
		const opMatch = body.match(/^([A-Za-z_]+):"?([^"]*)"?$/);
		let next: Suggestion[] = [];

		if (opMatch) {
			const typed = opMatch[1].toLowerCase();
			const key = OPERATOR_ALIASES[typed] ?? typed;
			const partial = opMatch[2].toLowerCase();
			next = valuesFor(key)
				.filter((v) => v.value.toLowerCase().includes(partial) && v.value.toLowerCase() !== partial)
				.sort(
					(a, b) =>
						Number(!a.value.toLowerCase().startsWith(partial)) -
						Number(!b.value.toLowerCase().startsWith(partial)),
				)
				.slice(0, 8)
				.map((v) => ({
					label: `${neg}${typed}:${v.value}`,
					hint: v.hint,
					insert: `${neg}${typed}:${quoteValue(v.value)} `,
					continues: false,
				}));
		} else if (/^[A-Za-z_]+$/.test(body)) {
			const typed = body.toLowerCase();
			next = OPERATORS.filter((o) => o.key.startsWith(typed)).map((o) => ({
				label: `${neg}${o.key}:`,
				hint: `${o.description} — e.g. ${o.example}`,
				insert: `${neg}${o.key}:`,
				continues: true,
			}));
		}

		suggestions = next;
		active = -1;
	}

	async function accept(s: Suggestion) {
		const caret = token.start + s.insert.length;
		// Values end in a space, so drop the old separator; operator names keep it
		const rest = value.slice(token.end);
		value = value.slice(0, token.start) + s.insert + (s.continues ? rest : rest.trimStart());
		await tick();
		input.focus();
		input.setSelectionRange(caret, caret);
		if (s.continues) {
			computeSuggestions();
		} else {
			suggestions = [];
			debouncedSearch.cancel();
			onSearch(value);
		}
	}

	function handleInput(e: Event) {
		value = (e.target as HTMLInputElement).value;
		computeSuggestions();
		// Don't search half-typed operators like "tag:bi" while the menu is offering values
		if (suggestions.length === 0) debouncedSearch(value);
		else debouncedSearch.cancel();
	}

	function handleKeydown(e: KeyboardEvent) {
		const open = suggestions.length > 0;
		if (e.key === 'ArrowDown' && open) {
			e.preventDefault();
			active = (active + 1) % suggestions.length;
		} else if (e.key === 'ArrowUp' && open) {
			e.preventDefault();
			active = active <= 0 ? suggestions.length - 1 : active - 1;
		} else if (e.key === 'Tab' && !e.shiftKey && open) {
			e.preventDefault();
			accept(suggestions[Math.max(active, 0)]);
		} else if (e.key === 'Enter') {
			e.preventDefault();
			if (open && active >= 0) {
				accept(suggestions[active]);
			} else {
				suggestions = [];
				debouncedSearch.cancel();
				onSearch(value);
			}
		} else if (e.key === 'Escape' && open) {
			e.preventDefault();
			suggestions = [];
		}
	}

	function clear() {
		debouncedSearch.cancel();
		value = '';
		suggestions = [];
		onSearch('');
		input.focus();
	}

	export function focus() {
		input.focus();
	}
</script>

<div class="relative">
	<span
		class="i-lucide-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500"
	></span>
	<input
		bind:this={input}
		type="text"
		class="input-base pl-10 pr-8 font-mono text-sm"
		{placeholder}
		{value}
		role="combobox"
		aria-label="Search documents"
		aria-expanded={suggestions.length > 0}
		aria-controls="search-suggestions"
		aria-autocomplete="list"
		aria-activedescendant={suggestions.length > 0 && active >= 0
			? `search-suggestion-${active}`
			: undefined}
		autocomplete="off"
		spellcheck="false"
		oninput={handleInput}
		onkeydown={handleKeydown}
		onclick={computeSuggestions}
		onkeyup={(e) => {
			// Caret moved: suggestions must follow the token under it
			if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) computeSuggestions();
		}}
		onblur={() => (suggestions = [])}
	/>
	{#if value}
		<button
			class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 cursor-pointer"
			aria-label="Clear search"
			onclick={clear}
		>
			<span class="i-lucide-x text-sm"></span>
		</button>
	{/if}

	{#if suggestions.length > 0}
		<ul
			id="search-suggestions"
			role="listbox"
			class="absolute z-20 mt-1 w-full max-w-md card py-1 shadow-lg overflow-hidden"
		>
			{#each suggestions as s, i (s.label)}
				<li
					id="search-suggestion-{i}"
					role="option"
					aria-selected={i === active}
					class="flex items-baseline gap-3 px-3 py-1.5 text-sm cursor-pointer {i === active
						? 'bg-brand-50 dark:bg-brand-900/30'
						: 'hover:bg-gray-50 dark:hover:bg-gray-700/50'}"
					onmousedown={(e) => {
						e.preventDefault();
						accept(s);
					}}
				>
					<span class="font-mono text-gray-900 dark:text-gray-100">{s.label}</span>
					<span class="text-xs text-gray-500 dark:text-gray-400 truncate">{s.hint}</span>
				</li>
			{/each}
		</ul>
	{/if}
</div>
