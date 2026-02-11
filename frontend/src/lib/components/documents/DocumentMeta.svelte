<script lang="ts">
	import type { DocumentDetail } from '$lib/types/index.js';
	import { formatFileSize, formatDate, formatDocumentType } from '$lib/utils/format.js';

	interface Props {
		document: DocumentDetail;
	}

	let { document: doc }: Props = $props();

	interface MetaItem {
		label: string;
		value: string;
		icon: string;
	}

	let metaItems = $derived<MetaItem[]>([
		{ label: 'Type', value: formatDocumentType(doc.document_type), icon: 'i-lucide-tag' },
		{ label: 'Size', value: formatFileSize(doc.file_size), icon: 'i-lucide-hard-drive' },
		{ label: 'Uploaded', value: formatDate(doc.upload_date), icon: 'i-lucide-calendar' },
		...(doc.processed_date
			? [{ label: 'Processed', value: formatDate(doc.processed_date), icon: 'i-lucide-check-circle' }]
			: []),
		{ label: 'MIME', value: doc.mime_type, icon: 'i-lucide-file-type' }
	]);

	let aiMeta = $derived(doc.ai_metadata as Record<string, unknown> | null);
</script>

<div class="space-y-4">
	<div class="grid grid-cols-2 sm:grid-cols-3 gap-3">
		{#each metaItems as item}
			<div class="text-sm">
				<div class="flex items-center gap-1 text-gray-500 dark:text-gray-400 mb-0.5">
					<span class="{item.icon} text-xs"></span>
					{item.label}
				</div>
				<div class="text-gray-900 dark:text-gray-100 font-medium">{item.value}</div>
			</div>
		{/each}
	</div>

	{#if aiMeta}
		<div class="border-t border-gray-100 dark:border-gray-700 pt-4">
			<h4 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-1">
				<span class="i-lucide-sparkles text-brand-500"></span>
				AI Analysis
			</h4>
			<div class="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
				{#if aiMeta.company}
					<div>
						<div class="text-gray-500 dark:text-gray-400">Company</div>
						<div class="text-gray-900 dark:text-gray-100 font-medium">{aiMeta.company}</div>
					</div>
				{/if}
				{#if aiMeta.date}
					<div>
						<div class="text-gray-500 dark:text-gray-400">Document Date</div>
						<div class="text-gray-900 dark:text-gray-100 font-medium">{aiMeta.date}</div>
					</div>
				{/if}
				{#if aiMeta.amount}
					<div>
						<div class="text-gray-500 dark:text-gray-400">Amount</div>
						<div class="text-gray-900 dark:text-gray-100 font-medium">{aiMeta.amount}</div>
					</div>
				{/if}
				{#if aiMeta.account_number}
					<div>
						<div class="text-gray-500 dark:text-gray-400">Account</div>
						<div class="text-gray-900 dark:text-gray-100 font-medium">{aiMeta.account_number}</div>
					</div>
				{/if}
				{#if aiMeta.summary}
					<div class="col-span-2 sm:col-span-3">
						<div class="text-gray-500 dark:text-gray-400">Summary</div>
						<div class="text-gray-900 dark:text-gray-100">{aiMeta.summary}</div>
					</div>
				{/if}
			</div>
		</div>
	{/if}
</div>
