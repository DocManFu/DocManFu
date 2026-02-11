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
		other: 'i-lucide-file'
	};

	let typeIcon = $derived(typeIcons[doc.document_type ?? ''] ?? 'i-lucide-file');
</script>

<a
	href="/documents/{doc.id}"
	class="card hover:shadow-md transition-shadow p-4 block no-underline text-inherit
		{selected ? 'ring-2 ring-brand-500' : ''}
		{focused ? 'ring-2 ring-brand-400' : ''}"
>
	<div class="flex items-start gap-3">
		<div class="flex-shrink-0 w-10 h-10 rounded-lg bg-brand-50 dark:bg-brand-900/30 flex items-center justify-center">
			<span class="{typeIcon} text-brand-600 dark:text-brand-400"></span>
		</div>

		<div class="flex-1 min-w-0">
			<h3 class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{displayName}</h3>

			<div class="flex items-center gap-2 mt-1 text-xs text-gray-500 dark:text-gray-400">
				{#if doc.document_type}
					<span class="badge bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300">
						{formatDocumentType(doc.document_type)}
					</span>
				{/if}
				<span>{formatFileSize(doc.file_size)}</span>
				<span>{formatDate(doc.upload_date)}</span>
			</div>

			{#if doc.tags.length > 0}
				<div class="flex flex-wrap gap-1 mt-2">
					{#each doc.tags.slice(0, 5) as tag (tag.id)}
						<TagBadge {tag} />
					{/each}
					{#if doc.tags.length > 5}
						<span class="text-xs text-gray-400">+{doc.tags.length - 5}</span>
					{/if}
				</div>
			{/if}
		</div>
	</div>
</a>
