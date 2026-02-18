<script lang="ts">
	import type { DocumentListItem } from '$lib/types/index.js';
	import { formatFileSize, formatDate, formatDocumentType } from '$lib/utils/format.js';
	import TagBadge from '$lib/components/tags/TagBadge.svelte';

	interface Props {
		document: DocumentListItem;
		selected?: boolean;
		focused?: boolean;
	}

	let { document: doc, selected = false, focused = false }: Props = $props();

	let displayName = $derived(doc.ai_generated_name || doc.original_name);

	const typeIcons: Record<string, string> = {
		bill: 'i-lucide-receipt',
		bank_statement: 'i-lucide-landmark',
		medical: 'i-lucide-heart-pulse',
		insurance: 'i-lucide-shield',
		tax: 'i-lucide-calculator',
		invoice: 'i-lucide-file-text',
		receipt: 'i-lucide-receipt',
		legal: 'i-lucide-scale',
		correspondence: 'i-lucide-mail',
		report: 'i-lucide-bar-chart-3',
		other: 'i-lucide-file',
	};

	let isImage = $derived(doc.mime_type?.startsWith('image/') ?? false);
	let typeIcon = $derived(
		isImage ? 'i-lucide-image' : (typeIcons[doc.document_type ?? ''] ?? 'i-lucide-file'),
	);
</script>

<a
	href="/documents/{doc.id}"
	class="flex items-center gap-3 px-4 py-2.5 no-underline text-inherit hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors
		{selected ? 'bg-brand-50 dark:bg-brand-900/20' : ''}
		{focused ? 'bg-brand-50/50 dark:bg-brand-900/10 ring-1 ring-inset ring-brand-400' : ''}"
>
	<div
		class="flex-shrink-0 w-8 h-8 rounded-md bg-brand-50 dark:bg-brand-900/30 flex items-center justify-center"
	>
		<span class="{typeIcon} text-sm text-brand-600 dark:text-brand-400"></span>
	</div>

	<div class="flex-1 min-w-0 truncate text-sm font-medium text-gray-900 dark:text-gray-100">
		{displayName}
	</div>

	{#if doc.document_type}
		<span
			class="hidden sm:inline-block flex-shrink-0 badge bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300 text-xs"
		>
			{formatDocumentType(doc.document_type)}
		</span>
	{/if}

	<span
		class="hidden md:inline-block flex-shrink-0 text-xs text-gray-500 dark:text-gray-400 w-16 text-right"
	>
		{formatFileSize(doc.file_size)}
	</span>

	<span class="flex-shrink-0 text-xs text-gray-500 dark:text-gray-400 w-24 text-right">
		{formatDate(doc.upload_date)}
	</span>

	{#if doc.tags.length > 0}
		<div class="hidden lg:flex flex-shrink-0 items-center gap-1 w-48">
			{#each doc.tags.slice(0, 3) as tag (tag.id)}
				<TagBadge {tag} />
			{/each}
			{#if doc.tags.length > 3}
				<span class="text-xs text-gray-400">+{doc.tags.length - 3}</span>
			{/if}
		</div>
	{/if}
</a>
