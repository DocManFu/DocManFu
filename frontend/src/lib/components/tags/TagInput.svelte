<script lang="ts">
	import type { Tag } from '$lib/types/index.js';
	import TagBadge from './TagBadge.svelte';

	interface Props {
		tags: Tag[];
		onchange: (tagNames: string[]) => void;
	}

	let { tags, onchange }: Props = $props();

	let input = $state('');

	function addTag() {
		const name = input.trim().toLowerCase();
		if (!name) return;
		if (tags.some((t) => t.name === name)) {
			input = '';
			return;
		}
		onchange([...tags.map((t) => t.name), name]);
		input = '';
	}

	function removeTag(name: string) {
		onchange(tags.filter((t) => t.name !== name).map((t) => t.name));
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			e.preventDefault();
			addTag();
		}
	}
</script>

<div class="space-y-2">
	<div class="flex flex-wrap gap-1.5">
		{#each tags as tag (tag.id)}
			<TagBadge {tag} removable onremove={() => removeTag(tag.name)} />
		{/each}
	</div>
	<div class="flex gap-2">
		<input
			type="text"
			class="input-base"
			placeholder="Add a tag..."
			bind:value={input}
			onkeydown={handleKeydown}
		/>
		<button class="btn-secondary btn-sm whitespace-nowrap" onclick={addTag}>
			<span class="i-lucide-plus mr-1"></span>Add
		</button>
	</div>
</div>
