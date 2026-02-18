<script lang="ts">
	import { onMount } from 'svelte';
	import { listTags, createTag, updateTag, deleteTag, mergeTags } from '$lib/api/tags.js';
	import type { TagWithCount } from '$lib/types/index.js';
	import ConfirmDialog from '$lib/components/shared/ConfirmDialog.svelte';
	import LoadingSpinner from '$lib/components/shared/LoadingSpinner.svelte';
	import EmptyState from '$lib/components/shared/EmptyState.svelte';
	import { toasts } from '$lib/stores/toast.js';

	let tags = $state<TagWithCount[]>([]);
	let loading = $state(true);

	// Create form
	let newName = $state('');
	let newColor = $state('#6B7280');
	let creating = $state(false);

	// Edit state
	let editingId = $state<string | null>(null);
	let editName = $state('');
	let editColor = $state('');

	// Delete state
	let deleteTarget = $state<TagWithCount | null>(null);

	// Merge state
	let mergeMode = $state(false);
	let mergeSelected = $state<Set<string>>(new Set());
	let mergeTargetId = $state<string | null>(null);
	let showMergeConfirm = $state(false);

	async function loadTags() {
		loading = true;
		try {
			tags = await listTags();
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to load tags');
		} finally {
			loading = false;
		}
	}

	async function handleCreate() {
		if (!newName.trim()) return;
		creating = true;
		try {
			await createTag({ name: newName.trim().toLowerCase(), color: newColor });
			newName = '';
			newColor = '#6B7280';
			toasts.success('Tag created');
			loadTags();
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to create tag');
		} finally {
			creating = false;
		}
	}

	function startEdit(tag: TagWithCount) {
		editingId = tag.id;
		editName = tag.name;
		editColor = tag.color;
	}

	async function saveEdit() {
		if (!editingId || !editName.trim()) return;
		try {
			await updateTag(editingId, { name: editName.trim(), color: editColor });
			editingId = null;
			toasts.success('Tag updated');
			loadTags();
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to update tag');
		}
	}

	function cancelEdit() {
		editingId = null;
	}

	async function handleDelete() {
		if (!deleteTarget) return;
		try {
			await deleteTag(deleteTarget.id);
			deleteTarget = null;
			toasts.success('Tag deleted');
			loadTags();
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to delete tag');
		}
	}

	function toggleMergeSelect(id: string) {
		const next = new Set(mergeSelected);
		if (next.has(id)) {
			next.delete(id);
		} else {
			next.add(id);
		}
		mergeSelected = next;
	}

	async function handleMerge() {
		if (!mergeTargetId || mergeSelected.size < 2) return;
		try {
			const sourceIds = [...mergeSelected].filter((id) => id !== mergeTargetId);
			await mergeTags({ source_tag_ids: sourceIds, target_tag_id: mergeTargetId });
			mergeMode = false;
			mergeSelected = new Set();
			mergeTargetId = null;
			showMergeConfirm = false;
			toasts.success('Tags merged');
			loadTags();
		} catch (e) {
			toasts.error(e instanceof Error ? e.message : 'Failed to merge tags');
		}
	}

	function exitMergeMode() {
		mergeMode = false;
		mergeSelected = new Set();
		mergeTargetId = null;
	}

	onMount(loadTags);
</script>

<svelte:head>
	<title>Tags - DocManFu</title>
</svelte:head>

<div class="page-container">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">Tags</h1>
		<button
			class="btn-secondary btn-sm"
			onclick={() => (mergeMode ? exitMergeMode() : (mergeMode = true))}
		>
			<span class="i-lucide-git-merge mr-1"></span>
			{mergeMode ? 'Cancel Merge' : 'Merge Tags'}
		</button>
	</div>

	<!-- Create form -->
	<div class="card p-4 mb-6">
		<h2 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Create Tag</h2>
		<div class="flex items-center gap-3">
			<input
				type="text"
				class="input-base flex-1"
				placeholder="Tag name"
				bind:value={newName}
				onkeydown={(e) => e.key === 'Enter' && handleCreate()}
			/>
			<input
				type="color"
				class="w-10 h-10 rounded-lg border border-gray-300 dark:border-gray-600 cursor-pointer"
				bind:value={newColor}
			/>
			<button
				class="btn-primary btn-sm"
				onclick={handleCreate}
				disabled={creating || !newName.trim()}
			>
				<span class="i-lucide-plus mr-1"></span>Create
			</button>
		</div>
	</div>

	{#if loading}
		<LoadingSpinner />
	{:else if tags.length === 0}
		<EmptyState
			icon="i-lucide-tags"
			title="No tags yet"
			description="Create your first tag above, or upload documents to auto-generate tags."
		/>
	{:else}
		{#if mergeMode && mergeSelected.size >= 2}
			<div class="card p-4 mb-4">
				<h3 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
					Select target tag to merge into:
				</h3>
				<div class="flex flex-wrap gap-2">
					{#each tags.filter((t) => mergeSelected.has(t.id)) as t (t.id)}
						<button
							class="badge cursor-pointer {mergeTargetId === t.id ? 'ring-2 ring-brand-500' : ''}"
							style="background-color: {t.color}20; color: {t.color}; border: 1px solid {t.color}40;"
							onclick={() => (mergeTargetId = t.id)}
						>
							{t.name}
						</button>
					{/each}
				</div>
				{#if mergeTargetId}
					<button class="btn-primary btn-sm mt-3" onclick={() => (showMergeConfirm = true)}>
						Merge {mergeSelected.size - 1} tag{mergeSelected.size - 1 === 1 ? '' : 's'} into target
					</button>
				{/if}
			</div>
		{/if}

		<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
			{#each tags as tag (tag.id)}
				<div
					class="card p-4 {mergeMode && mergeSelected.has(tag.id) ? 'ring-2 ring-brand-500' : ''}"
				>
					{#if editingId === tag.id}
						<div class="space-y-3">
							<input
								type="text"
								class="input-base"
								bind:value={editName}
								onkeydown={(e) => {
									if (e.key === 'Enter') saveEdit();
									if (e.key === 'Escape') cancelEdit();
								}}
							/>
							<div class="flex items-center gap-2">
								<input
									type="color"
									class="w-8 h-8 rounded border border-gray-300 dark:border-gray-600 cursor-pointer"
									bind:value={editColor}
								/>
								<button class="btn-primary btn-sm" onclick={saveEdit}>Save</button>
								<button class="btn-ghost btn-sm" onclick={cancelEdit}>Cancel</button>
							</div>
						</div>
					{:else}
						<div class="flex items-center justify-between">
							<div class="flex items-center gap-2 min-w-0">
								{#if mergeMode}
									<button
										class="w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 cursor-pointer
											{mergeSelected.has(tag.id)
											? 'bg-brand-600 border-brand-600'
											: 'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600'}"
										onclick={() => toggleMergeSelect(tag.id)}
									>
										{#if mergeSelected.has(tag.id)}
											<span class="i-lucide-check text-white text-xs"></span>
										{/if}
									</button>
								{/if}
								<span
									class="w-4 h-4 rounded-full flex-shrink-0"
									style="background-color: {tag.color};"
								></span>
								<span class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate"
									>{tag.name}</span
								>
								<span class="text-xs text-gray-500 dark:text-gray-400 flex-shrink-0">
									{tag.document_count} doc{tag.document_count === 1 ? '' : 's'}
								</span>
							</div>

							{#if !mergeMode}
								<div class="flex items-center gap-1">
									<button class="btn-icon" title="Edit tag" onclick={() => startEdit(tag)}>
										<span class="i-lucide-pencil text-sm"></span>
									</button>
									<button
										class="btn-icon text-red-500 hover:text-red-700"
										title="Delete tag"
										onclick={() => (deleteTarget = tag)}
									>
										<span class="i-lucide-trash-2 text-sm"></span>
									</button>
								</div>
							{/if}
						</div>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</div>

<ConfirmDialog
	open={deleteTarget !== null}
	title="Delete Tag"
	message="This will remove the tag '{deleteTarget?.name}' from all documents. Are you sure?"
	confirmLabel="Delete"
	onconfirm={handleDelete}
	oncancel={() => (deleteTarget = null)}
/>

<ConfirmDialog
	open={showMergeConfirm}
	title="Merge Tags"
	message="This will move all document associations from the source tags to the target tag, then delete the source tags. This cannot be undone."
	confirmLabel="Merge"
	confirmClass="btn-primary"
	onconfirm={handleMerge}
	oncancel={() => (showMergeConfirm = false)}
/>
